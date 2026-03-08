from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from bunkermedia.config import AppConfig
from bunkermedia.maintenance import backup_state, restore_state
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

    backup_cmd = sub.add_parser("backup", help="Create state backup archive")
    backup_cmd.add_argument("--output-dir", default=None, help="Output directory for backup archive")

    restore_cmd = sub.add_parser("restore", help="Restore state backup archive")
    restore_cmd.add_argument("archive", help="Path to backup archive (.tar.gz)")
    restore_cmd.add_argument("--force", action="store_true", help="Overwrite existing database state")

    status_cmd = sub.add_parser("status", help="Show runtime status")
    status_cmd.add_argument("--json", action="store_true", help="Output JSON")

    plan_cmd = sub.add_parser("plan-offline", help="Queue downloads to satisfy offline target horizon")
    plan_cmd.add_argument("--json", action="store_true", help="Output JSON")

    storage_cmd = sub.add_parser("storage-enforce", help="Enforce storage budget policy")
    storage_cmd.add_argument("--json", action="store_true", help="Output JSON")

    providers_cmd = sub.add_parser("providers", help="List configured source providers")

    discover_cmd = sub.add_parser("discover", help="Discover metadata via provider")
    discover_cmd.add_argument("--provider", default="youtube")
    discover_cmd.add_argument("--source", default="", help="Source selector (e.g. trending, URL, or folder)")
    discover_cmd.add_argument("--limit", type=int, default=20)

    acquire_cmd = sub.add_parser("acquire", help="Acquire content via provider")
    acquire_cmd.add_argument("--provider", default="youtube")
    acquire_cmd.add_argument("--source", default="", help="Source URL, selector, or folder")
    acquire_cmd.add_argument("--mode", default="auto", choices=["auto", "single", "playlist", "channel", "trending"])

    schema_cmd = sub.add_parser("schema", help="Show DB schema version and migrations")
    schema_cmd.add_argument("--json", action="store_true", help="Output JSON")

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


async def _cmd_backup(args: argparse.Namespace) -> None:
    config = AppConfig.from_yaml(args.config)
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    backup_file = backup_state(config, output_dir=output_dir)
    print(f"Backup created: {backup_file}")


async def _cmd_restore(args: argparse.Namespace) -> None:
    config = AppConfig.from_yaml(args.config)
    archive = Path(args.archive).expanduser()
    restore_state(config, archive_path=archive, force=bool(args.force))
    print(f"Restore completed from: {archive}")


async def _cmd_status(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    await service.refresh_network_state()
    status = service.get_health_state()
    status["jobs_pending"] = len(service.list_download_jobs(status="pending", limit=5000))
    status["jobs_processing"] = len(service.list_download_jobs(status="processing", limit=5000))
    status["jobs_dead"] = len(service.list_download_jobs(status="dead", limit=5000))
    status["deadletters"] = len(service.list_dead_letter_jobs(limit=5000))
    status["offline_inventory"] = service.get_offline_inventory()
    if args.json:
        print(json.dumps(status, separators=(",", ":"), ensure_ascii=True))
    else:
        for key in [
            "status",
            "online",
            "in_sync_window",
            "schema_version",
            "jobs_pending",
            "jobs_processing",
            "jobs_dead",
            "deadletters",
        ]:
            print(f"{key}: {status[key]}")
    await service.shutdown()


async def _cmd_plan_offline(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    result = await service.plan_offline_queue()
    if args.json:
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=True))
    else:
        print(f"status: {result.get('status')}")
        print(f"queued_jobs: {result.get('queued_jobs', 0)}")
        print(f"queued_duration_seconds: {result.get('queued_duration_seconds', 0)}")
    await service.shutdown()


async def _cmd_storage_enforce(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    result = service.enforce_storage_policy()
    if args.json:
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=True))
    else:
        print(f"status: {result.get('status')}")
        print(f"evicted_files: {result.get('evicted_files', 0)}")
        print(f"freed_bytes: {result.get('freed_bytes', 0)}")
    await service.shutdown()


async def _cmd_providers(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    providers = service.list_providers()
    for provider in providers:
        print(provider)
    await service.shutdown()


async def _cmd_discover(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    if not str(args.source).strip() and str(args.provider).strip().lower() != "local":
        print("source is required")
        await service.shutdown()
        return
    source = args.source if str(args.source).strip() else "default"
    try:
        items = await service.discover(provider=args.provider, source=source, limit=int(args.limit))
    except KeyError as exc:
        print(str(exc))
        await service.shutdown()
        return

    if not items:
        print("No items discovered")
    for item in items[: args.limit]:
        print(f"{item.video_id} | {item.channel} | {item.title}")
    await service.shutdown()


async def _cmd_acquire(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    if not str(args.source).strip() and str(args.provider).strip().lower() != "local":
        print("source is required")
        await service.shutdown()
        return
    source = args.source if str(args.source).strip() else "default"
    try:
        items = await service.acquire(provider=args.provider, source=source, mode=args.mode)
    except KeyError as exc:
        print(str(exc))
        await service.shutdown()
        return

    print(f"Acquired items: {len(items)}")
    for item in items[:20]:
        print(f"{item.video_id} | {item.channel} | {item.title}")
    await service.shutdown()


async def _cmd_schema(args: argparse.Namespace) -> None:
    service = BunkerService(config_path=args.config)
    await service.initialize()
    payload = {
        "schema_version": service.get_schema_version(),
        "migrations": service.list_schema_migrations(),
    }
    if args.json:
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
    else:
        print(f"schema_version: {payload['schema_version']}")
        for migration in payload["migrations"]:
            print(f"{migration['version']}: {migration['name']} @ {migration['applied_at']}")
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
    if args.command == "backup":
        asyncio.run(_cmd_backup(args))
        return
    if args.command == "restore":
        asyncio.run(_cmd_restore(args))
        return
    if args.command == "status":
        asyncio.run(_cmd_status(args))
        return
    if args.command == "plan-offline":
        asyncio.run(_cmd_plan_offline(args))
        return
    if args.command == "storage-enforce":
        asyncio.run(_cmd_storage_enforce(args))
        return
    if args.command == "providers":
        asyncio.run(_cmd_providers(args))
        return
    if args.command == "discover":
        asyncio.run(_cmd_discover(args))
        return
    if args.command == "acquire":
        asyncio.run(_cmd_acquire(args))
        return
    if args.command == "schema":
        asyncio.run(_cmd_schema(args))
        return
    if args.command == "serve":
        _cmd_serve(args)
        return

    parser.error("Unknown command")
