# Soak Validation

BunkerMedia includes a deterministic soak harness for validating queue stability, batch completion, import watching, and restart recovery without depending on live network providers.

## Harness

- Script: `scripts/run_soak_validation.py`
- Workflow: `.github/workflows/soak.yml`

Example:

```bash
python scripts/run_soak_validation.py --cycles 45 --seed-jobs 12 --batch-jobs 4 --restarts 1
```

The harness:

- seeds single and batch download jobs,
- exercises playlist/channel batch reconciliation,
- writes import-folder media during the run,
- restarts the service mid-run,
- refreshes recommendation/offline-planner cycles,
- and fails if dead letters remain or the queue does not drain.

## Latest Recorded Local Run

Run date: `2026-03-28`

Command:

```bash
python3 scripts/run_soak_validation.py --cycles 24 --seed-jobs 8 --batch-jobs 2 --restarts 1 --output /tmp/bunkermedia-soak-summary.json
```

Result summary:

- status: `ok`
- restarts: `1`
- videos retained: `48`
- downloaded titles: `48`
- completed batches: `4`
- pending queue items at end: `0`
- dead letters at end: `0`
- imports written during run: `8`
- recommendation sample size after soak: `12`

Recorded JSON summary:

```json
{
  "batches": {
    "completed": 4,
    "count": 4,
    "partial": 0
  },
  "cycles_per_phase": 24,
  "deadletters": 0,
  "downloaded_count": 48,
  "drain_loops": 0,
  "health": {
    "import_watch_enabled": true,
    "schema_version": 8,
    "status": "ok"
  },
  "imports_written": 8,
  "offline_inventory": {
    "downloaded_storage_bytes": 2278,
    "private_items": 0,
    "total_downloaded_items": 48,
    "unwatched_duration_seconds": 52050
  },
  "queue": {
    "dead": 0,
    "done": 22,
    "paused": 0,
    "pending": 0,
    "processing": 0
  },
  "recommendation_count": 12,
  "restart_count": 1,
  "seed_batch_jobs_per_phase": 2,
  "seed_jobs_per_phase": 8,
  "status": "ok",
  "video_count": 48
}
```

## Scope Limits

This soak pass does not replace:

- long-duration real-network downloads,
- device codec playback validation,
- Raspberry Pi thermal throttling checks on actual hardware.

It is intended to catch queue-state drift, import-loop regressions, and restart stability problems before release.
