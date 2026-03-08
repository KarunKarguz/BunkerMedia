# Changelog

## [0.1.4] - 2026-03-08

### Added

- RSS provider and local-folder provider via plugin architecture.
- Integration test harness (`tests/test_integration.py`) with mocked downloader/network components.
- Security hardening checklist document.
- Tag-triggered release workflow for build/test/build artifacts and GitHub releases.
- Security CI workflow (`pip-audit`) for dependency vulnerability scans.

## [0.1.3] - 2026-03-08

### Added

- Schema migration/version tracking with `schema_migrations`.
- Provider plugin framework and built-in `youtube` provider.
- New provider and schema interfaces in CLI and API (`providers`, `discover`, `acquire`, `schema`).
- Additional integration-oriented tests for migrations and provider registration.

## [0.1.2] - 2026-03-08

### Added

- Prometheus-style metrics registry and `/metrics` endpoint.
- Structured logging mode (`log_format: json`).
- Network-aware offline detection and sync-window gating.
- Backup and restore tooling (CLI and API).
- Deployment artifacts (`Dockerfile`, `docker-compose.yml`, `systemd` template).

## [0.1.1] - 2026-03-08

### Added

- Download retry backoff policy with configurable limits and jitter.
- Dead-letter queue storage for exhausted download jobs.
- Queue inspection CLI commands: `jobs`, `deadletters`, `retry-dead`.
- Queue and dead-letter API endpoints for operational visibility.
- Bunku Mode UI skeleton at `/bunku` with home rails, queue panel, feedback, and sync trigger.

## [0.1.0] - 2026-03-08

### Added

- Initial BunkerMedia project structure and CLI.
- yt-dlp downloader for videos, playlists, and channels with archive dedupe.
- Scraper for trending, channel feeds, and playlist metadata.
- SQLite database layer for videos, watch history, and preferences.
- FastAPI server for listing, searching, streaming, and watched updates.
- Async worker system for sync and download queue processing.
- Transcript/metadata intelligence pipeline with lightweight embeddings.
- Hybrid recommendation engine with diversity reranking and explain mode.
- Open-source project documentation baseline.
