# Architecture Overview

BunkerMedia is organized into these runtime layers:

1. Ingestion:
- `downloader.py`: yt-dlp download pipeline
- `scraper.py`: metadata-only ingestion for trending/feeds

2. Storage:
- `database.py`: SQLite schema and query layer
- `migrations.py`: schema migration/version management
- `download_batches` / `download_batch_items`: persisted batch progress for resumable long-running acquisition jobs

3. Intelligence:
- `intelligence.py`: transcript/metadata extraction and embedding generation
- `recommender.py`: hybrid ranking and diversity reranking

4. Runtime:
- `workers.py`: background loops for sync, intelligence, recommendations, queue, and continuous import watching
- `service.py`: orchestration and lifecycle
- `artwork.py`: local artwork cache, thumbnail fetch, and generated poster fallback
- `network.py`: online/offline detection and sync-window checks
- `planner.py`: offline horizon queue planning
- `storage_policy.py`: storage budget enforcement and eviction policy
- `storage_privacy.py`: encrypted-storage/private-vault health detection
- `system_monitor.py`: low-overhead appliance telemetry for disk, memory, load, and Pi temperature
- `import_organizer.py`: NAS/local drop-folder ingest and library auto-organization
- `metrics.py`: in-process counters/gauges/timers for observability
- `maintenance.py`: backup and restore operations

5. Interfaces:
- `cli.py`: command line workflow
- `server.py`: FastAPI endpoints

6. Providers:
- `providers/base.py`: provider contract
- `providers/registry.py`: provider registration and lookup
- `providers/youtube.py`: built-in YouTube provider
- `providers/rss.py`: RSS/Atom discovery and acquisition
- `providers/local.py`: local-folder discovery provider

## Data Flow

1. URL/feeds are queued or scraped.
2. Playlist/channel/trending queue jobs materialize resumable batch state before download.
3. Downloaded and scraped video metadata is upserted, including thumbnail/artwork references when available.
4. Artwork is served locally from cached thumbnails or generated fallback posters.
5. Intelligence worker generates embeddings from transcript/metadata.
6. Profile-aware policy filters remove private/explicit items for unauthorized profiles.
7. Continuous import watch loops organize local drops and trigger local discovery without a manual sync cycle.
8. Recommender combines preference, history, trending, semantic similarity.
9. API and CLI expose ranked recommendations, batch state, artwork, and media playback.

## Privacy Model

- At-rest privacy is expected to come from encrypted storage at the filesystem or volume layer.
- `storage_privacy.py` provides best-effort detection and a marker-file override for encrypted stores whose mount type is not directly visible.
- Videos carry a `privacy_level` of `standard`, `private`, or `explicit`.
- Profiles carry:
  - `can_access_private`
  - optional `pin_hash`
  - `is_kids`
- Service-layer filtering ensures unauthorized profiles cannot see or stream private items.

## Storage Guidance

- BunkerMedia does not treat app-managed re-compression as the primary privacy mechanism.
- Compression/transcoding is a separate future storage policy concern because reducing footprint while keeping quality identical is not generally realistic for already-compressed media.
