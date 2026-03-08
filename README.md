# BunkerMedia

BunkerMedia is a self-hosted intelligent media acquisition and streaming system designed for Linux, WSL, and Raspberry Pi.

## Project Status

- Roadmap: `ROADMAP.md`
- Contributing guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Architecture notes: `docs/ARCHITECTURE.md`
- Bunku Mode UI spec: `docs/BUNKU_MODE_UI.md`
- Operations guide: `docs/OPERATIONS.md`
- Security hardening checklist: `docs/SECURITY_HARDENING_CHECKLIST.md`
- Security CI workflow: `.github/workflows/security.yml`

## Features

- yt-dlp API downloader (single videos, playlists, channels)
- Metadata scraping (trending, channel feeds, playlist metadata)
- Transcript + metadata intelligence pipeline with lightweight hashed embeddings
- SQLite-backed metadata, watch history, and preferences
- Hybrid recommendation engine (semantic + behavioral + trending) with diversity rerank
- Bunku Mode local-first web UI (`/bunku`) with rails, queue panel, and feedback controls
- FastAPI media server
- Async background workers for sync and queued downloads
- Prometheus-style metrics endpoint (`/metrics`) and queue/dead-letter observability
- Schema migration/version tracking (`schema_migrations`)
- Provider plugin framework with built-in `youtube` provider
- Additional built-in providers: `rss` and `local`
- CLI commands: `bunker add`, `bunker sync`, `bunker recommend`, `bunker serve`, `bunker status`, `bunker backup`, `bunker restore`, `bunker providers`, `bunker discover`, `bunker schema`

## Install

```bash
cd BunkerMedia
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you prefer non-editable install:

```bash
pip install .
```

## Configuration

Edit `config.yaml`:

- `download_path`
- `max_parallel_downloads`
- `update_intervals`
- `embedding_dim`
- `intelligence_batch_size`
- `transcript_max_chars`
- `max_download_attempts`
- `retry_base_seconds`
- `retry_max_seconds`
- `retry_jitter`
- `log_format` (`text` or `json`)
- `force_offline_mode`
- `connectivity_check_host` / `connectivity_check_port`
- `sync_windows` (e.g. `["00:00-06:00","21:00-23:59"]`)
- `backup_path`
- `rss_feeds`
- `local_watch_folders`

Optional feed seeds:

- `channel_feeds`
- `playlist_feeds`

## Usage

```bash
bunker add "https://www.youtube.com/watch?v=..."
bunker sync
bunker recommend --limit 20
bunker recommend --limit 10 --explain
bunker jobs --status pending --limit 50
bunker deadletters --limit 50
bunker retry-dead --all
bunker status --json
bunker providers
bunker discover --provider youtube --source trending --limit 20
bunker discover --provider rss --source https://example.com/feed.xml --limit 20
bunker discover --provider local --source default --limit 20
bunker backup --output-dir ./backups
bunker restore ./backups/bunkermedia-backup-YYYYMMDDTHHMMSSZ.tar.gz --force
bunker schema --json
bunker serve --host 0.0.0.0 --port 8080
# open http://localhost:8080/bunku
```

## API Endpoints

- `GET /health`
- `GET /metrics`
- `GET /schema`
- `GET /providers`
- `GET /discover?provider=youtube&source=trending&limit=20`
- `POST /acquire`
- `GET /bunku`
- `GET /bunku/data/home`
- `POST /bunku/data/sync`
- `POST /backup`
- `POST /restore`
- `GET /videos?limit=100&search=keyword`
- `GET /videos/{video_id}`
- `GET /jobs?status=pending&limit=100`
- `GET /deadletters?limit=100`
- `POST /deadletters/{dead_letter_id}/retry`
- `GET /recommendations?limit=20&explain=true`
- `GET /stream/{video_id}`
- `POST /videos/{video_id}/watched`

## Notes for Raspberry Pi

- Keep `max_parallel_downloads` low (1-2).
- Use conservative update intervals to reduce CPU/network churn.
- Use the default low-power downloader format selection.
- Keep `embedding_dim` between `64` and `128` for low-power devices.

## Deployment

- Docker: `docker compose up --build`
- systemd unit template: `deploy/systemd/bunkermedia.service`
