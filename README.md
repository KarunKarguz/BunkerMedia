# BunkerMedia

BunkerMedia is a self-hosted intelligent media acquisition and streaming system designed for Linux, WSL, and Raspberry Pi.

## Project Status

- Roadmap: `ROADMAP.md`
- Contributing guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Architecture notes: `docs/ARCHITECTURE.md`

## Features

- yt-dlp API downloader (single videos, playlists, channels)
- Metadata scraping (trending, channel feeds, playlist metadata)
- Transcript + metadata intelligence pipeline with lightweight hashed embeddings
- SQLite-backed metadata, watch history, and preferences
- Hybrid recommendation engine (semantic + behavioral + trending) with diversity rerank
- FastAPI media server
- Async background workers for sync and queued downloads
- CLI commands: `bunker add`, `bunker sync`, `bunker recommend`, `bunker serve`

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

Optional feed seeds:

- `channel_feeds`
- `playlist_feeds`

## Usage

```bash
bunker add "https://www.youtube.com/watch?v=..."
bunker sync
bunker recommend --limit 20
bunker recommend --limit 10 --explain
bunker serve --host 0.0.0.0 --port 8080
```

## API Endpoints

- `GET /health`
- `GET /videos?limit=100&search=keyword`
- `GET /videos/{video_id}`
- `GET /recommendations?limit=20&explain=true`
- `GET /stream/{video_id}`
- `POST /videos/{video_id}/watched`

## Notes for Raspberry Pi

- Keep `max_parallel_downloads` low (1-2).
- Use conservative update intervals to reduce CPU/network churn.
- Use the default low-power downloader format selection.
- Keep `embedding_dim` between `64` and `128` for low-power devices.
