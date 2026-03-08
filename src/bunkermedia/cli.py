from __future__ import annotations

import argparse
import asyncio
import json

from bunkermedia.service import BunkerService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bunker", description="BunkerMedia CLI")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")

    sub = parser.add_subparsers(dest="command", required=True)

    add_cmd = sub.add_parser("add", help="Queue a URL for download")
    add_cmd.add_argument("url", help="YouTube URL")
    add_cmd.add_argument("--type", default="auto", choices=["auto", "single", "playlist", "channel", "trending"])
    add_cmd.add_argument("--priority", default=0, type=int)
    add_cmd.add_argument("--immediate", action="store_true", help="Run one queue cycle after adding")

    sync_cmd = sub.add_parser("sync", help="Run one-shot sync")
    sync_cmd.add_argument("--download-queue", action="store_true", help="Process pending downloads")

    rec_cmd = sub.add_parser("recommend", help="Show top recommendations")
    rec_cmd.add_argument("--limit", type=int, default=20)
    rec_cmd.add_argument("--explain", action="store_true", help="Show scoring explanation")

    jobs_cmd = sub.add_parser("jobs", help="Inspect download job queue")
    jobs_cmd.add_argument("--status", default=None, choices=["pending", "processing", "done", "failed", "dead"])
    jobs_cmd.add_argument("--limit", type=int, default=50)

    dead_cmd = sub.add_parser("deadletters", help="Inspect dead-letter download jobs")
    dead_cmd.add_argument("--limit", type=int, default=50)

    retry_dead_cmd = sub.add_parser("retry-dead", help="Retry one or all dead-letter jobs")
    retry_dead_cmd.add_argument("--id", type=int, default=None, help="Dead-letter id to retry")
    retry_dead_cmd.add_argument("--all", action="store_true", help="Retry all non-retried dead-letter jobs")

    serve_cmd = sub.add_parser("serve", help="Run FastAPI server")
    serve_cmd.add_argument("--host", default=None)
    serve_cmd.add_argument("--port", type=int, default=None)

    return parser


async def _cmd_add(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    job_id = await service.add_url(args.url, target_type=args.type, priority=args.priority)
    print(f"Queued job id={job_id} url={args.url}")
    if args.immediate:
        await service.workers.process_download_queue_once()
        await service.recommender.refresh_scores()
        print("Processed one download queue cycle")
    await service.shutdown()


async def _cmd_sync(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    await service.sync_once()
    if args.download_queue:
        await service.workers.process_download_queue_once()
    print("Sync completed")
    await service.shutdown()


async def _cmd_recommend(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    recs = await service.recommend(limit=args.limit, explain=args.explain)
    if not recs:
        print("No recommendations available")
    for idx, rec in enumerate(recs, start=1):
        marker = "[DL]" if rec.downloaded else "[META]"
        print(f"{idx:02d}. {marker} {rec.score:0.3f} | {rec.channel} | {rec.title} ({rec.video_id})")
        if args.explain and rec.explanation:
            print(f"    {json.dumps(rec.explanation, separators=(',', ':'), ensure_ascii=True)}")
    await service.shutdown()


async def _cmd_jobs(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    jobs = service.list_download_jobs(status=args.status, limit=args.limit)
    if not jobs:
        print("No download jobs found")
    for job in jobs:
        print(json.dumps(job, separators=(",", ":"), ensure_ascii=True))
    await service.shutdown()


async def _cmd_deadletters(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    items = service.list_dead_letter_jobs(limit=args.limit)
    if not items:
        print("No dead-letter jobs found")
    for item in items:
        print(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
    await service.shutdown()


async def _cmd_retry_dead(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()

    retried = 0
    if args.all:
        items = service.list_dead_letter_jobs(limit=500)
        for item in items:
            if item.get("retried_at"):
                continue
            dead_id = int(item["id"])
            job_id = service.retry_dead_letter(dead_id)
            if job_id:
                retried += 1
                print(f"Retried dead-letter id={dead_id} -> job_id={job_id}")
    elif args.id is not None:
        job_id = service.retry_dead_letter(int(args.id))
        if job_id:
            retried = 1
            print(f"Retried dead-letter id={args.id} -> job_id={job_id}")
        else:
            print(f"Dead-letter id={args.id} not found")
    else:
        print("Specify either --id <dead_letter_id> or --all")

    if retried == 0 and (args.all or args.id is not None):
        print("No dead-letter jobs retried")
    await service.shutdown()


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from bunkermedia.server import create_app

    app = create_app(config_path=args.config)
    host = args.host
    port = args.port

    if host is None or port is None:
        service = BunkerService(config_path=args.config)
        host = host or service.config.server.host
        port = port or service.config.server.port

    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "add":
        asyncio.run(_cmd_add(args))
        return
    if args.command == "sync":
        asyncio.run(_cmd_sync(args))
        return
    if args.command == "recommend":
        asyncio.run(_cmd_recommend(args))
        return
    if args.command == "jobs":
        asyncio.run(_cmd_jobs(args))
        return
    if args.command == "deadletters":
        asyncio.run(_cmd_deadletters(args))
        return
    if args.command == "retry-dead":
        asyncio.run(_cmd_retry_dead(args))
        return
    if args.command == "serve":
        _cmd_serve(args)
        return

    parser.error("Unknown command")
