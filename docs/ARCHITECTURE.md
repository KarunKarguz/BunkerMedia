# Architecture Overview

BunkerMedia is organized into these runtime layers:

1. Ingestion:
- `downloader.py`: yt-dlp download pipeline
- `scraper.py`: metadata-only ingestion for trending/feeds

2. Storage:
- `database.py`: SQLite schema and query layer

3. Intelligence:
- `intelligence.py`: transcript/metadata extraction and embedding generation
- `recommender.py`: hybrid ranking and diversity reranking

4. Runtime:
- `workers.py`: background loops for sync, intelligence, recommendations, queue
- `service.py`: orchestration and lifecycle
- `network.py`: online/offline detection and sync-window checks
- `metrics.py`: in-process counters/gauges/timers for observability
- `maintenance.py`: backup and restore operations

5. Interfaces:
- `cli.py`: command line workflow
- `server.py`: FastAPI endpoints

## Data Flow

1. URL/feeds are queued or scraped.
2. Downloaded and scraped video metadata is upserted.
3. Intelligence worker generates embeddings from transcript/metadata.
4. Recommender combines preference, history, trending, semantic similarity.
5. API and CLI expose ranked recommendations and media playback.
