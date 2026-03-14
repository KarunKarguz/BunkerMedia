# Operations Guide

## Health and Metrics

- Health: `GET /health`
- Metrics: `GET /metrics` (Prometheus text format)
- Schema: `GET /schema`

Example:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8080/metrics | head
curl -s http://localhost:8080/schema
curl -s http://localhost:8080/system
curl -s http://localhost:8080/privacy
```

## Logging

Set in `config.yaml`:

- `log_format: text` (default)
- `log_format: json` (structured logs)

Logs are written to `logs/bunkermedia.log`.

## Backup and Restore

### CLI

```bash
bunker status --json
bunker schema --json
bunker providers
bunker discover --provider youtube --source trending --limit 10
bunker backup --output-dir ./backups
bunker restore ./backups/bunkermedia-backup-YYYYMMDDTHHMMSSZ.tar.gz --force
```

### API

```bash
curl -X POST http://localhost:8080/backup -H 'content-type: application/json' -d '{}'
curl -X POST http://localhost:8080/restore -H 'content-type: application/json' \
  -d '{"archive_path":"/path/to/backup.tar.gz","force":true}'
```

## Offline and Sync Windows

Use these config keys:

- `force_offline_mode`
- `connectivity_check_host`
- `connectivity_check_port`
- `connectivity_check_timeout_seconds`
- `sync_windows`
- `offline_target_hours`
- `offline_planner_batch_size`
- `storage_max_gb`
- `storage_eviction_policy`
- `private_mode_enabled`
- `private_require_encrypted_store`
- `private_storage_marker_file`
- `import_watch_folders`
- `auto_organize_imports`
- `import_move_mode`

`sync_windows` format examples:

- `"00:00-06:00"`
- `"21:00-23:59"`
- Overnight window: `"22:00-02:00"`

## Offline Planner and Storage Policy

Manual controls:

```bash
bunker plan-offline --json
bunker storage-enforce --json
```

API controls:

```bash
curl -s http://localhost:8080/offline/inventory
curl -s -X POST http://localhost:8080/offline/plan
curl -s -X POST http://localhost:8080/storage/enforce
```

These operations are also run in background worker recommendation cycles.

## Resumable Download Batches

Long-running playlist, channel, and trending downloads are tracked as resumable batches.

Operational behavior:

- batch progress is persisted in SQLite,
- completed items are reconciled from the local library on retry,
- interrupted `processing` jobs are reset to `pending` on startup,
- partially completed batches remain resumable until finished or dead-lettered.

Inspection:

```bash
bunker jobs --status pending --limit 50
bunker batches --json
curl -s http://localhost:8080/batches?status=partial&limit=20
```

## Artwork Cache

Bunku artwork is served through the local API:

```bash
curl -I http://localhost:8080/artwork/<video_id>
```

Behavior:

- remote thumbnails are cached locally when available,
- local sidecar artwork is reused for local/imported media,
- titles without source artwork receive generated SVG posters,
- profile visibility rules still apply because artwork is resolved through the service layer.

## NAS Import Organization

Drop media files into configured import folders such as:

- `media/imports`
- `media/nas-import`

Then trigger ingest:

```bash
bunker imports-organize --json
curl -s -X POST http://localhost:8080/imports/organize
```

Files are auto-classified into:

- `media/library/video/<collection>/`
- `media/library/audio/<collection>/`

Organized folders are included in local discovery, so imported files appear in Bunku after refresh/sync.

## Private Vault Mode

Recommended config:

```yaml
private_mode_enabled: true
private_require_encrypted_store: true
private_storage_marker_file: .bunkermedia-private-store
```

Operational model:

- Put `download_path` on an encrypted filesystem or encrypted-mounted path where possible.
- If encrypted storage is real but mount heuristics cannot prove it, create the configured marker file in the media root.
- Use a vault-capable profile with an optional PIN to mark content as `private` or `explicit`.
- Non-vault profiles will not see those items in search, rails, recommendations, or playback endpoints.

Important:

- BunkerMedia does not use app-level “compressed hidden blobs” as the default privacy model.
- At-rest protection should come from the underlying encrypted store.
- Re-encoding/compression is a separate future storage optimization concern and can trade quality or CPU time.

## Deployment

### Docker Compose

```bash
docker compose up --build -d
```

### Raspberry Pi Appliance Profile

Bootstrap:

```bash
./deploy/raspberrypi/setup_pi.sh
docker compose -f deploy/raspberrypi/docker-compose.pi.yml up --build -d
```

Preset files:

- `deploy/raspberrypi/config.pi.yaml`
- `deploy/raspberrypi/docker-compose.pi.yml`
- `deploy/raspberrypi/setup_pi.sh`

This profile:

- lowers concurrency for Pi stability,
- stretches background intervals,
- pre-creates NAS import folders,
- enables a container healthcheck,
- and tunes offline/storage defaults for small ARM systems.

### systemd

Template service file:

- `deploy/systemd/bunkermedia.service`

Install by adapting paths/user, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bunkermedia
sudo systemctl start bunkermedia
```

## Release Automation

- GitHub workflow: `.github/workflows/release.yml`
- Policy reference: `docs/RELEASE_POLICY.md`
- Trigger: push tag matching `v*` (for example `v0.1.4`).
- Actions:
  - compile and run test suite gate,
  - build source and wheel artifacts,
  - generate CycloneDX SBOM and dependency manifest,
  - generate SHA256 checksums for release files,
  - upload CI artifacts,
  - publish GitHub release with generated notes.
- Release artifacts now include:
  - `bunkermedia-sbom.cdx.json`
  - `dependencies.txt`
  - `sha256sums.txt`

## Security Review

Before release, run through:

- `docs/SECURITY_HARDENING_CHECKLIST.md`
- `.github/workflows/security.yml` (`pip-audit` on PR/push + weekly schedule)
