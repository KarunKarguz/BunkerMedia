# Changelog

## [0.2.2] - 2026-03-13

### Added

- Multi-user profiles with persistent active-profile selection and optional kids-safe mode.
- Profile-aware watch, like, dislike, and rating state via `profiles` and `profile_video_state`.
- Queue job controls for pause, resume, and priority changes through the API and Bunku UI.
- Recommendation card "Why this" explanations inside Bunku.

### Changed

- Video listing, search, recommendation ranking, and offline inventory now resolve against the active profile.
- Kids-mode profiles now filter obviously mature metadata from Bunku rails and recommendations.

## [0.2.1] - 2026-03-13

### Added

- TV-mode navigation for Bunku with keyboard/D-pad movement between controls, rails, and queue items.
- Inline playback modal for local media with quick actions for mark-watched and external stream opening.
- Couch-friendly visual focus treatment and horizontal media rails tuned for Pi/TV screens.

### Changed

- Bunku now defaults to a remote-friendly interaction model while still supporting mouse and touch input.

## [0.2.0] - 2026-03-13

### Added

- NAS/local import organizer for classifying and moving dropped media into the managed library tree.
- `POST /imports/organize` API endpoint and Bunku UI control for manual import runs.
- Configurable import watch folders, move/copy mode, and scan limits.

### Changed

- Managed library folders are now part of local discovery so organized imports appear automatically in Bunku.

## [0.1.9] - 2026-03-13

### Added

- Appliance telemetry endpoint for disk, memory, load, and Raspberry Pi CPU temperature.
- Bunku dashboard controls for offline top-up and storage cleanup actions.
- Raspberry Pi deployment preset, compose profile, and bootstrap script.

### Changed

- Bunku UI now exposes system health as part of the home screen, making it usable as a Pi/NAS appliance dashboard.

## [0.1.8] - 2026-03-08

### Added

- Offline horizon planner to queue recommended content toward configurable target hours.
- Storage budget policy manager with watched/low-score eviction modes and liked-content protection.
- New CLI/API controls for offline planning and storage enforcement.
- Schema migration for `duration_seconds` and `file_size_bytes` video metadata.

### Changed

- Downloader/scraper/local provider now persist duration/file-size metadata used by planner and eviction logic.
- Service sync and worker recommendation cycles now run planner + storage policy maintenance.

## [0.1.7] - 2026-03-08

### Added

- Maintainer release cadence and semantic versioning policy (`docs/RELEASE_POLICY.md`).
- Governance and support expectations document (`docs/GOVERNANCE.md`).

### Changed

- Marked Phase F roadmap release policy scope complete and declared v1 core baseline complete.
- Updated contributing and PR template to require policy/doc updates when release/support model changes.

## [0.1.5] - 2026-03-08

### Changed

- Migrated FastAPI startup/shutdown lifecycle from deprecated `on_event` hooks to lifespan handlers.
- Expanded integration test harness to cover API queue -> worker -> videos/recommendations flow with mocked downloader/network behavior.

### Added

- Release artifact hardening with CycloneDX SBOM, dependency manifest, and SHA256 checksum generation in release workflow.

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
