# Changelog

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
