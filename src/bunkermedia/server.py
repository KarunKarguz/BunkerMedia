from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bunkermedia.service import BunkerService


class MarkWatchedPayload(BaseModel):
    watch_seconds: int = 0
    completed: bool = True
    liked: bool | None = None
    disliked: bool | None = None
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    notes: str | None = None


def create_app(config_path: str | Path = "config.yaml") -> FastAPI:
    service = BunkerService(config_path=config_path)
    app = FastAPI(title="BunkerMedia", version="0.1.0")

    @app.on_event("startup")
    async def on_startup() -> None:
        await service.initialize()
        if service.config.auto_start_workers:
            await service.workers.start()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await service.shutdown()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
