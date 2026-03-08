# Operations Guide

## Health and Metrics

- Health: `GET /health`
- Metrics: `GET /metrics` (Prometheus text format)

Example:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8080/metrics | head
```

## Logging

Set in `config.yaml`:

- `log_format: text` (default)
- `log_format: json` (structured logs)

Logs are written to `logs/bunkermedia.log`.

## Backup and Restore

### CLI

```bash
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

`sync_windows` format examples:

- `"00:00-06:00"`
- `"21:00-23:59"`
- Overnight window: `"22:00-02:00"`

## Deployment

### Docker Compose

```bash
docker compose up --build -d
```

### systemd

Template service file:

- `deploy/systemd/bunkermedia.service`

Install by adapting paths/user, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bunkermedia
sudo systemctl start bunkermedia
```
