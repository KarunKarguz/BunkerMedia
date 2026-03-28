from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from bunkermedia import __version__
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


class ProviderAcquirePayload(BaseModel):
    provider: str = "youtube"
    source: str
    mode: str = Field(default="auto", pattern="^(auto|single|playlist|channel|trending)$")


class JobPriorityPayload(BaseModel):
    priority: int = Field(default=0, ge=-10, le=20)


class ProfileCreatePayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=48)
    is_kids: bool = False
    can_access_private: bool = False
    pin: str | None = Field(default=None, min_length=4, max_length=32)
    allow_channels: list[str] | None = None
    block_channels: list[str] | None = None


class ProfileUpdatePayload(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=48)
    is_kids: bool | None = None
    can_access_private: bool | None = None
    current_pin: str | None = Field(default=None, min_length=4, max_length=32)
    pin: str | None = Field(default=None, min_length=4, max_length=32)
    clear_pin: bool = False
    allow_channels: list[str] | None = None
    block_channels: list[str] | None = None


class ProfileSelectPayload(BaseModel):
    pin: str | None = Field(default=None, min_length=4, max_length=32)


class VideoPrivacyPayload(BaseModel):
    privacy_level: str = Field(default="standard", pattern="^(standard|private|explicit)$")


class VideoRejectPayload(BaseModel):
    reason: str = Field(default="not_interested", pattern="^[a-z_]{3,32}$")


class ChannelRulePayload(BaseModel):
    channel: str = Field(min_length=1, max_length=160)


def create_app(config_path: str | Path = "config.yaml") -> FastAPI:
    service = BunkerService(config_path=config_path)
    ui_root = Path(__file__).resolve().parent / "ui"
    sync_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await service.initialize()
        if service.config.auto_start_workers:
            await service.workers.start()
        try:
            yield
        finally:
            await service.shutdown()

    app = FastAPI(title="BunkerMedia", version=__version__, lifespan=lifespan)
    app.state.service = service

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
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/bunku/styles.css", include_in_schema=False)
    async def bunku_styles():
        css = ui_root / "styles.css"
        if not css.exists():
            raise HTTPException(status_code=404, detail="UI stylesheet not found")
        return Response(content=css.read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/bunku/app.js", include_in_schema=False)
    async def bunku_script():
        js = ui_root / "app.js"
        if not js.exists():
            raise HTTPException(status_code=404, detail="UI script not found")
        return Response(content=js.read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/bunku/manifest.webmanifest", include_in_schema=False)
    async def bunku_manifest():
        manifest = ui_root / "manifest.webmanifest"
        if not manifest.exists():
            raise HTTPException(status_code=404, detail="UI manifest not found")
        return Response(content=manifest.read_text(encoding="utf-8"), media_type="application/manifest+json")

    @app.get("/bunku/sw.js", include_in_schema=False)
    async def bunku_service_worker():
        script = ui_root / "sw.js"
        if not script.exists():
            raise HTTPException(status_code=404, detail="UI service worker not found")
        return Response(content=script.read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/bunku/icon.svg", include_in_schema=False)
    async def bunku_icon():
        icon = ui_root / "icon.svg"
        if not icon.exists():
            raise HTTPException(status_code=404, detail="UI icon not found")
        return Response(content=icon.read_text(encoding="utf-8"), media_type="image/svg+xml")

    @app.get("/bunku/data/home")
    async def bunku_home(limit: int = Query(16, ge=4, le=60)):
        await service.refresh_network_state()
        active_profile = service.get_active_profile()
        videos = service.list_videos(limit=max(200, limit * 8), search=None)
        video_by_id = {str(item["video_id"]): item for item in videos if item.get("video_id")}

        continue_candidates = [
            _serialize_video(item)
            for item in videos
            if int(item.get("downloaded") or 0) == 1
            and int(item.get("completed") or 0) == 0
            and int(item.get("total_watch_seconds") or 0) > 0
        ]
        continue_watching = continue_candidates[:limit]
        if not continue_watching:
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
                    "privacy_level": existing.get("privacy_level") or "standard",
                    "artwork_url": existing.get("artwork_url"),
                    "explanation": rec.explanation,
                }
            )

        queue = service.list_download_jobs(status=None, limit=40)
        batches = service.list_download_batches(limit=20)
        deadletters = service.list_dead_letter_jobs(limit=20)
        return {
            "continue_watching": continue_watching,
            "downloaded": downloaded,
            "recommended": recommended,
            "fresh": fresh,
            "queue": queue,
            "batches": batches,
            "deadletters": deadletters,
            "offline_mode": not service.network.is_online,
            "offline_inventory": service.get_offline_inventory(),
            "system": service.get_system_state(),
            "privacy": service.get_privacy_state(),
            "active_profile": active_profile,
            "profiles": service.list_profiles(),
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

    @app.get("/offline/inventory")
    async def offline_inventory():
        return service.get_offline_inventory()

    @app.get("/system")
    async def system_state():
        return service.get_system_state()

    @app.get("/privacy")
    async def privacy_state():
        return service.get_privacy_state()

    @app.get("/artwork/{video_id}")
    async def artwork(video_id: str):
        resolved = await service.get_artwork_bytes(video_id)
        if not resolved:
            raise HTTPException(status_code=404, detail="Artwork not found")
        payload, media_type = resolved
        return Response(content=payload, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})

    @app.post("/offline/plan")
    async def offline_plan():
        return await service.plan_offline_queue()

    @app.post("/storage/enforce")
    async def storage_enforce():
        return service.enforce_storage_policy()

    @app.post("/imports/organize")
    async def imports_organize():
        return await service.organize_imports()

    @app.get("/schema")
    async def schema():
        return {
            "schema_version": service.get_schema_version(),
            "migrations": service.list_schema_migrations(),
        }

    @app.get("/metrics")
    async def metrics():
        if not service.config.server.enable_metrics:
            raise HTTPException(status_code=404, detail="Metrics disabled")
        payload = service.render_metrics()
        return PlainTextResponse(payload, media_type="text/plain")

    @app.get("/videos")
    async def list_videos(
        limit: int = Query(100, ge=1, le=1000),
        search: str | None = None,
        channel: str | None = None,
        downloaded_only: bool = False,
        freshness_days: int | None = Query(default=None, ge=1, le=3650),
        duration_min: int | None = Query(default=None, ge=0, le=86400),
        duration_max: int | None = Query(default=None, ge=0, le=86400),
    ):
        return service.list_videos(
            limit=limit,
            search=search,
            channel=channel,
            downloaded_only=downloaded_only,
            freshness_days=freshness_days,
            duration_min=duration_min,
            duration_max=duration_max,
        )

    @app.get("/videos/{video_id}")
    async def get_video(video_id: str):
        video = service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return video

    @app.get("/search")
    async def search_videos(
        q: str,
        limit: int = Query(100, ge=1, le=1000),
        channel: str | None = None,
        downloaded_only: bool = False,
        freshness_days: int | None = Query(default=None, ge=1, le=3650),
        duration_min: int | None = Query(default=None, ge=0, le=86400),
        duration_max: int | None = Query(default=None, ge=0, le=86400),
    ):
        return service.list_videos(
            limit=limit,
            search=q,
            channel=channel,
            downloaded_only=downloaded_only,
            freshness_days=freshness_days,
            duration_min=duration_min,
            duration_max=duration_max,
        )

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

    @app.get("/providers")
    async def providers():
        return {"providers": service.list_providers()}

    @app.get("/profiles")
    async def profiles():
        return {"active_profile": service.get_active_profile(), "profiles": service.list_profiles()}

    @app.post("/profiles")
    async def create_profile(payload: ProfileCreatePayload):
        profile = service.create_profile(
            display_name=payload.display_name,
            is_kids=payload.is_kids,
            can_access_private=payload.can_access_private,
            pin=payload.pin,
            allow_channels=payload.allow_channels,
            block_channels=payload.block_channels,
        )
        return {"status": "created", "profile": profile}

    @app.patch("/profiles/{profile_id}")
    async def update_profile(profile_id: str, payload: ProfileUpdatePayload):
        profile = service.update_profile(
            profile_id,
            display_name=payload.display_name,
            is_kids=payload.is_kids,
            can_access_private=payload.can_access_private,
            current_pin=payload.current_pin,
            pin=payload.pin,
            clear_pin=payload.clear_pin,
            allow_channels=payload.allow_channels,
            block_channels=payload.block_channels,
        )
        if not profile:
            raise HTTPException(status_code=403, detail="Profile not found or PIN invalid")
        return {"status": "updated", "profile": profile}

    @app.post("/profiles/{profile_id}/channels/block")
    async def block_profile_channel(profile_id: str, payload: ChannelRulePayload):
        profile = service.block_channel(payload.channel, profile_id=profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found or channel invalid")
        return {"status": "updated", "profile": profile, "channel": payload.channel.strip().lower()}

    @app.post("/profiles/{profile_id}/select")
    async def select_profile(profile_id: str, payload: ProfileSelectPayload | None = None):
        profile = service.select_profile(profile_id, pin=(payload.pin if payload else None))
        if not profile:
            raise HTTPException(status_code=403, detail="Profile not found or PIN invalid")
        return {"status": "selected", "profile": profile}

    @app.get("/discover")
    async def discover(provider: str = "youtube", source: str = "", limit: int = Query(20, ge=1, le=200)):
        if not source.strip() and provider.strip().lower() != "local":
            raise HTTPException(status_code=400, detail="source is required")
        discover_source = source if source.strip() else "default"
        try:
            items = await service.discover(provider=provider, source=discover_source, limit=limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [asdict(item) for item in items]

    @app.post("/acquire")
    async def acquire(payload: ProviderAcquirePayload):
        if not payload.source.strip() and payload.provider.strip().lower() != "local":
            raise HTTPException(status_code=400, detail="source is required")
        acquire_source = payload.source if payload.source.strip() else "default"
        try:
            items = await service.acquire(provider=payload.provider, source=acquire_source, mode=payload.mode)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [asdict(item) for item in items]

    @app.get("/jobs")
    async def list_jobs(
        status: str | None = Query(default=None, pattern="^(pending|processing|paused|done|failed|dead)?$"),
        limit: int = Query(100, ge=1, le=1000),
    ):
        return service.list_download_jobs(status=status, limit=limit)

    @app.get("/batches")
    async def list_batches(
        status: str | None = Query(default=None, pattern="^(queued|running|partial|completed|failed)?$"),
        limit: int = Query(100, ge=1, le=1000),
    ):
        return service.list_download_batches(status=status, limit=limit)

    @app.get("/batches/{batch_id}")
    async def get_batch(batch_id: int):
        batch = service.get_download_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return batch

    @app.post("/jobs/{job_id}/pause")
    async def pause_job(job_id: int):
        if not service.pause_download_job(job_id):
            raise HTTPException(status_code=400, detail="Job is not pending or was not found")
        return {"status": "paused", "job_id": job_id}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(job_id: int):
        if not service.resume_download_job(job_id):
            raise HTTPException(status_code=400, detail="Job is not paused or was not found")
        return {"status": "pending", "job_id": job_id}

    @app.post("/jobs/{job_id}/priority")
    async def prioritize_job(job_id: int, payload: JobPriorityPayload):
        if not service.set_download_job_priority(job_id, payload.priority):
            raise HTTPException(status_code=404, detail="Job not found")
        return {"status": "updated", "job_id": job_id, "priority": payload.priority}

    @app.get("/deadletters")
    async def list_deadletters(limit: int = Query(100, ge=1, le=1000)):
        return service.list_dead_letter_jobs(limit=limit)

    @app.delete("/deadletters")
    async def clear_deadletters(retried_only: bool = False):
        cleared = service.clear_dead_letter_jobs(retried_only=retried_only)
        return {"status": "cleared", "deleted": cleared, "retried_only": retried_only}

    @app.post("/deadletters/{dead_letter_id}/retry")
    async def retry_deadletter(dead_letter_id: int):
        job_id = service.retry_dead_letter(dead_letter_id)
        if job_id is None:
            raise HTTPException(status_code=404, detail="Dead-letter job not found")
        return {"status": "queued", "job_id": job_id, "dead_letter_id": dead_letter_id}

    @app.get("/recommendations")
    async def recommendations(limit: int = Query(20, ge=1, le=100), explain: bool = False):
        recs = await service.recommend(limit=limit, explain=explain)
        return [asdict(rec) for rec in recs]

    @app.post("/videos/{video_id}/watched")
    async def mark_watched(video_id: str, payload: MarkWatchedPayload):
        if not service.get_video(video_id):
            raise HTTPException(status_code=404, detail="Video not found")
        service.mark_watched(video_id=video_id, **payload.model_dump())
        return {"status": "updated", "video_id": video_id}

    @app.post("/videos/{video_id}/privacy")
    async def set_video_privacy(video_id: str, payload: VideoPrivacyPayload):
        if not service.set_video_privacy(video_id, payload.privacy_level):
            raise HTTPException(status_code=403, detail="Video not found or private access denied")
        return {"status": "updated", "video_id": video_id, "privacy_level": payload.privacy_level}

    @app.post("/videos/{video_id}/reject")
    async def reject_video(video_id: str, payload: VideoRejectPayload):
        if not service.reject_video(video_id, reason=payload.reason):
            raise HTTPException(status_code=404, detail="Video not found")
        return {"status": "updated", "video_id": video_id, "reason": payload.reason}

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
        "completed": bool(item.get("completed")),
        "duration_seconds": item.get("duration_seconds"),
        "total_watch_seconds": item.get("total_watch_seconds"),
        "rejected_reason": item.get("rejected_reason"),
        "privacy_level": item.get("privacy_level") or "standard",
        "artwork_url": item.get("artwork_url"),
    }
