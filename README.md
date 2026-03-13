# BunkerMedia

BunkerMedia is a self-hosted intelligent media acquisition and streaming system designed for Linux, WSL, and Raspberry Pi.

## Project Status

- Roadmap: `ROADMAP.md`
- Contributing guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Architecture notes: `docs/ARCHITECTURE.md`
- Product requirements: `docs/SRS.md`
- System design spec: `docs/SDS.md`
- Governance and support policy: `docs/GOVERNANCE.md`
- Bunku Mode UI spec: `docs/BUNKU_MODE_UI.md`
- Operations guide: `docs/OPERATIONS.md`
- Release cadence policy: `docs/RELEASE_POLICY.md`
- Security hardening checklist: `docs/SECURITY_HARDENING_CHECKLIST.md`
- Security CI workflow: `.github/workflows/security.yml`
- Release security artifacts: SBOM + checksums in tagged releases

## Features

- yt-dlp API downloader (single videos, playlists, channels)
- Metadata scraping (trending, channel feeds, playlist metadata)
- Transcript + metadata intelligence pipeline with lightweight hashed embeddings
- SQLite-backed metadata, watch history, and preferences
- Hybrid recommendation engine (semantic + behavioral + trending) with diversity rerank
- Multi-user profiles with active-profile switching and kids-safe mode
- Private-vault mode with encrypted-storage health checks, profile PINs, and hidden private media
- Bunku Mode local-first web UI (`/bunku`) with TV-friendly rails, queue panel, recommendation reasoning, feedback controls, inline playback, and installable app-shell behavior
- FastAPI media server
- Async background workers for sync and queued downloads
- Offline horizon planner for auto-queuing watch-ready content
- Storage budget policy with automated eviction
- Appliance telemetry for disk, memory, load, and Pi temperature
- NAS/local import organizer for auto-sorting dropped media files
- Prometheus-style metrics endpoint (`/metrics`) and queue/dead-letter observability
- Schema migration/version tracking (`schema_migrations`)
- Provider plugin framework with built-in `youtube` provider
- Additional built-in providers: `rss` and `local`
- CLI commands: `bunker add`, `bunker sync`, `bunker recommend`, `bunker serve`, `bunker status`, `bunker backup`, `bunker restore`, `bunker providers`, `bunker discover`, `bunker schema`
- CLI commands: `bunker add`, `bunker sync`, `bunker recommend`, `bunker serve`, `bunker status`, `bunker imports-organize`, `bunker backup`, `bunker restore`, `bunker providers`, `bunker discover`, `bunker schema`

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
- `import_watch_folders`
- `auto_organize_imports`
- `import_move_mode` (`move` or `copy`)
- `import_scan_limit`
- `offline_target_hours`
- `offline_planner_max_candidates`
- `offline_planner_batch_size`
- `offline_default_video_minutes`
- `offline_estimated_mbps`
- `offline_queue_priority`
- `storage_max_gb`
- `storage_reserve_gb`
- `storage_eviction_policy` (`watched_oldest` or `low_score`)
- `storage_protect_liked`
- `storage_eviction_batch_size`
- `private_mode_enabled`
- `private_require_encrypted_store`
- `private_storage_marker_file`
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
bunker imports-organize --json
bunker discover --provider local --source default --limit 20
bunker plan-offline --json
bunker storage-enforce --json
bunker providers
bunker discover --provider youtube --source trending --limit 20
bunker discover --provider rss --source https://example.com/feed.xml --limit 20
bunker backup --output-dir ./backups
bunker restore ./backups/bunkermedia-backup-YYYYMMDDTHHMMSSZ.tar.gz --force
bunker schema --json
bunker serve --host 0.0.0.0 --port 8080
# open http://localhost:8080/bunku
```

Inside Bunku, TV mode is enabled by default:

- Arrow keys move focus across controls and media rails
- `Enter` plays local titles or queues discovered items
- `Esc` closes the inline player overlay
- Profiles can be switched from the top bar, including kids-safe profiles
- Private-vault profiles can require a PIN and hide marked media from normal profiles
- Queue rows support pause/resume and priority tuning directly from the UI
- On supported browsers, `Install App` pins Bunku to a phone/tablet/TV home screen

## API Endpoints

- `GET /health`
- `GET /metrics`
- `GET /schema`
- `GET /system`
- `GET /privacy`
- `GET /bunku/manifest.webmanifest`
- `GET /bunku/sw.js`
- `GET /bunku/icon.svg`
- `GET /providers`
- `GET /profiles`
- `POST /profiles`
- `PATCH /profiles/{profile_id}`
- `POST /profiles/{profile_id}/select`
- `POST /imports/organize`
- `GET /offline/inventory`
- `POST /offline/plan`
- `POST /storage/enforce`
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
- `POST /jobs/{job_id}/pause`
- `POST /jobs/{job_id}/resume`
- `POST /jobs/{job_id}/priority`
- `GET /deadletters?limit=100`
- `POST /deadletters/{dead_letter_id}/retry`
- `GET /recommendations?limit=20&explain=true`
- `GET /stream/{video_id}`
- `POST /videos/{video_id}/watched`
- `POST /videos/{video_id}/privacy`

## Notes for Raspberry Pi

- Keep `max_parallel_downloads` low (1-2).
- Use conservative update intervals to reduce CPU/network churn.
- Use the default low-power downloader format selection.
- Keep `embedding_dim` between `64` and `128` for low-power devices.
- Use the tuned preset: `deploy/raspberrypi/config.pi.yaml`
- Quick bootstrap: `deploy/raspberrypi/setup_pi.sh`
- Pi Docker profile: `deploy/raspberrypi/docker-compose.pi.yml`
- Use `media/nas-import` or `media/imports` as the drop folder for local/NAS ingest
- Use the Bunku TV mode UI for keyboard/remote-first operation on HDMI-attached displays
- For private mode, put `download_path` on an encrypted volume where possible and add the configured marker file if mount heuristics cannot confirm encryption

## Private Mode

- BunkerMedia does not claim transparent “smaller and identical quality” compression for downloaded video.
- Private mode is built around encrypted storage verification plus app-level private media visibility controls.
- Mark sensitive items as `private` or `explicit` from a vault-capable profile.
- Normal profiles will not see those items in rails, search, recommendations, or stream endpoints.
- For best results, enable:
  - `private_mode_enabled: true`
  - `private_require_encrypted_store: true`
  - store media on LUKS/fscrypt/gocryptfs/cryfs or add the configured marker file on the verified encrypted store

## Deployment

- Docker: `docker compose up --build`
- systemd unit template: `deploy/systemd/bunkermedia.service`
