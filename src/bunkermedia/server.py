from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from bunkermedia.service import BunkerService


class MarkWatchedPayload(BaseModel):
    watch_seconds: int = 0
    completed: bool = True
    liked: bool | None = None
    disliked: bool | None = None
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    notes: str | None = None


class QueuePayload(BaseModel):
    url: str
    target_type: str = Field(default="auto", pattern="^(auto|single|playlist|channel|trending)$")
    priority: int = 0


class BackupPayload(BaseModel):
    output_dir: str | None = None


class RestorePayload(BaseModel):
    archive_path: str
    force: bool = False


def create_app(config_path: str | Path = "config.yaml") -> FastAPI:
    service = BunkerService(config_path=config_path)
    app = FastAPI(title="BunkerMedia", version="0.1.0")
    ui_root = Path(__file__).resolve().parent / "ui"
    sync_lock = asyncio.Lock()

    @app.on_event("startup")
    async def on_startup() -> None:
        await service.initialize()
        if service.config.auto_start_workers:
            await service.workers.start()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await service.shutdown()

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        service.metrics.inc("http_requests_total")
        service.metrics.observe("http_request_duration_seconds", elapsed)
        return response

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/bunku")

    @app.get("/bunku", include_in_schema=False)
    async def bunku_ui():
        page = ui_root / "index.html"
        if not page.exists():
            raise HTTPException(status_code=404, detail="Bunku UI files not found")
        return FileResponse(str(page), media_type="text/html")

    @app.get("/bunku/styles.css", include_in_schema=False)
    async def bunku_styles():
        css = ui_root / "styles.css"
        if not css.exists():
            raise HTTPException(status_code=404, detail="UI stylesheet not found")
        return FileResponse(str(css), media_type="text/css")

    @app.get("/bunku/app.js", include_in_schema=False)
    async def bunku_script():
        js = ui_root / "app.js"
        if not js.exists():
            raise HTTPException(status_code=404, detail="UI script not found")
        return FileResponse(str(js), media_type="application/javascript")

    @app.get("/bunku/data/home")
    async def bunku_home(limit: int = Query(16, ge=4, le=60)):
        await service.refresh_network_state()
        videos = service.list_videos(limit=max(200, limit * 8), search=None)
        video_by_id = {str(item["video_id"]): item for item in videos if item.get("video_id")}

        continue_watching = [
            _serialize_video(item)
            for item in videos
            if int(item.get("watched") or 0) == 1 and int(item.get("downloaded") or 0) == 1
        ][:limit]

        downloaded = [_serialize_video(item) for item in videos if int(item.get("downloaded") or 0) == 1][:limit]
        fresh = [_serialize_video(item) for item in videos][:limit]

        recs = await service.recommend(limit=limit, explain=True)
        recommended: list[dict[str, Any]] = []
        for rec in recs:
            existing = video_by_id.get(rec.video_id) or service.get_video(rec.video_id) or {}
            recommended.append(
                {
                    "video_id": rec.video_id,
                    "title": rec.title,
                    "channel": rec.channel,
                    "score": rec.score,
                    "downloaded": rec.downloaded,
                    "local_path": rec.local_path,
                    "source_url": existing.get("source_url"),
                    "upload_date": existing.get("upload_date"),
                    "explanation": rec.explanation,
                }
            )

        queue = service.list_download_jobs(status=None, limit=40)
        deadletters = service.list_dead_letter_jobs(limit=20)
        return {
            "continue_watching": continue_watching,
            "downloaded": downloaded,
            "recommended": recommended,
            "fresh": fresh,
            "queue": queue,
            "deadletters": deadletters,
            "offline_mode": not service.network.is_online,
        }

    @app.post("/bunku/data/sync")
    async def bunku_sync() -> dict[str, str]:
        if sync_lock.locked():
            return {"status": "busy"}
        async with sync_lock:
            await service.sync_once()
        return {"status": "ok", "online": str(service.network.is_online).lower()}

    @app.get("/health")
    async def health() -> dict[str, object]:
        await service.refresh_network_state()
        return service.get_health_state()

    @app.get("/metrics")
    async def metrics():
        if not service.config.server.enable_metrics:
            raise HTTPException(status_code=404, detail="Metrics disabled")
        payload = service.render_metrics()
        return PlainTextResponse(payload, media_type="text/plain")

    @app.get("/videos")
    async def list_videos(limit: int = Query(100, ge=1, le=1000), search: str | None = None):
        return service.list_videos(limit=limit, search=search)

    @app.get("/videos/{video_id}")
    async def get_video(video_id: str):
        video = service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return video

    @app.get("/search")
    async def search_videos(q: str, limit: int = Query(100, ge=1, le=1000)):
        return service.list_videos(limit=limit, search=q)

    @app.post("/queue")
    async def queue_video(payload: QueuePayload):
        url = payload.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        job_id = await service.add_url(url, target_type=payload.target_type, priority=payload.priority)
        return {"status": "queued", "job_id": job_id}

    @app.post("/backup")
    async def create_backup(payload: BackupPayload):
        target = Path(payload.output_dir).expanduser() if payload.output_dir else None
        backup_path = await asyncio.to_thread(service.backup, target)
        return {"status": "ok", "backup_path": str(backup_path)}

    @app.post("/restore")
    async def restore_backup(payload: RestorePayload):
        archive = Path(payload.archive_path).expanduser()
        try:
            await asyncio.to_thread(service.restore, archive, payload.force)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.get("/jobs")
    async def list_jobs(
        status: str | None = Query(default=None, pattern="^(pending|processing|done|failed|dead)?$"),
        limit: int = Query(100, ge=1, le=1000),
    ):
        return service.list_download_jobs(status=status, limit=limit)

    @app.get("/deadletters")
    async def list_deadletters(limit: int = Query(100, ge=1, le=1000)):
        return service.list_dead_letter_jobs(limit=limit)

    @app.post("/deadletters/{dead_letter_id}/retry")
    async def retry_deadletter(dead_letter_id: int):
        job_id = service.retry_dead_letter(dead_letter_id)
        if job_id is None:
            raise HTTPException(status_code=404, detail="Dead-letter job not found")
        return {"status": "queued", "job_id": job_id, "dead_letter_id": dead_letter_id}

    @app.get("/recommendations")
    async def recommendations(limit: int = Query(20, ge=1, le=100), explain: bool = False):
        recs = await service.recommend(limit=limit, explain=explain)
        return [rec.__dict__ for rec in recs]

    @app.post("/videos/{video_id}/watched")
    async def mark_watched(video_id: str, payload: MarkWatchedPayload):
        if not service.get_video(video_id):
            raise HTTPException(status_code=404, detail="Video not found")
        service.mark_watched(video_id=video_id, **payload.model_dump())
        return {"status": "updated", "video_id": video_id}

    @app.get("/stream/{video_id}")
    async def stream_video(video_id: str):
        video_path = service.get_stream_path(video_id)
        if not video_path:
            raise HTTPException(status_code=404, detail="Video file not found")
        return FileResponse(str(video_path), filename=video_path.name)

    return app


def _serialize_video(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": item.get("video_id"),
        "title": item.get("title"),
        "channel": item.get("channel"),
        "upload_date": item.get("upload_date"),
        "local_path": item.get("local_path"),
        "downloaded": bool(item.get("downloaded")),
        "source_url": item.get("source_url"),
        "watched": bool(item.get("watched")),
    }
