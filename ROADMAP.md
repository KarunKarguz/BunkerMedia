# BunkerMedia Product Roadmap

BunkerMedia is evolving toward a complete local-first home media system.

## Product Vision

BunkerMedia should feel like an offline-first "local Netflix" for self-hosters:

- Works fully on LAN without internet.
- Automatically syncs and curates when internet is available.
- Learns user interests and feedback signals.
- Pre-downloads relevant content in the background.

## Source Policy (Public OSS Requirement)

To keep this project safe and maintainable for public open-source use, provider integrations must target:

- user-owned content,
- publicly available/free-to-access content,
- or sources users are authorized to access.

No built-in piracy-focused workflows will be added.

## Current State Snapshot

### Completed

- Downloader with dedupe archive and queue workers.
- Scraper for trending/channel/playlist metadata.
- SQLite metadata, watch history, preferences.
- Transcript+metadata intelligence embeddings.
- Hybrid recommendation engine with explain mode.
- Retry backoff + dead-letter queue.
- FastAPI server and CLI surface.

### Key Gaps to "Complete Home Media Server"

- Visual local-first app experience (Bunku Mode UI).
- Multi-provider ingestion plugin architecture.
- Offline availability planner (what to pre-download, when).
- More robust recommendation feedback loops.
- Full observability, backups, and upgrade tooling.

## Phase A: MVP Baseline (Now -> v0.2)

### Objective

Solid single-user CLI/API with stable acquisition and ranking.

### Scope

- [x] Download queue + retry/dead-letter.
- [x] Recommendation explainability.
- [x] Metrics endpoint (queue depth, retries, dead-letter, recommendation latency).
- [x] Structured log mode (JSON).
- [x] Backup/restore for DB/archive state.
- [ ] Integration tests for queue/reco/api flow.

### Exit Criteria

- 24h soak test without worker crashes.
- Dead-letter flows recoverable via CLI/API.
- Basic metrics visible from one endpoint.

## Phase B: Off-Grid Readiness (v0.3)

### Objective

Usable in intermittent/no-internet environments.

### Scope

- [ ] Network state detector (offline/online transitions).
- [ ] Sync windows and bandwidth-aware scheduling.
- [ ] Download planner for "offline horizon" (e.g., next 3 days).
- [ ] Storage budget policies (keep/watch/evict strategy).
- [ ] Resumable background download batches.

### Exit Criteria

- System continues serving and ranking with internet disconnected.
- On reconnect, system performs staged sync and resumes queue automatically.
- User can configure storage cap and offline target hours.

## Phase C: Bunku Mode UI (v0.4)

### Objective

Deliver a local "Bunker Mode Netflix" interface for family-friendly usage.

### Scope

- [x] Web UI shell with TV-friendly browsing.
- [ ] Home screen rails: Continue Watching, Downloaded, Recommended, New.
- [ ] Search + filters (duration, channel, freshness, downloaded-only).
- [ ] Recommendation cards with "Why this" explanation.
- [ ] Feedback controls: Like, Dislike, Not Interested, Hide Channel.
- [ ] Queue controls: Prioritize, Pause, Retry Dead-letter, Clear Failed.

### Exit Criteria

- User can operate without CLI for common tasks.
- End-to-end playback and queue ops from UI only.
- UI responsive on desktop/mobile LAN clients.

## Phase D: Multi-Source Acquisition (v0.5)

### Objective

Support pluggable acquisition from multiple authorized sources.

### Scope

- [ ] Provider interface: discover/metadata/download methods.
- [x] Provider interface: discover/metadata/download methods.
- [ ] Built-in providers: YouTube, RSS/video feeds, local watch folders.
- [ ] Optional community provider adapters via plugin registry.
- [ ] Unified source priority and dedupe strategy.

### Exit Criteria

- New provider can be added without touching core queue engine.
- Same recommendation pipeline works across providers.

## Phase E: Emotion/Intent-Aware Personalization (v0.6)

### Objective

Track user intent and sentiment-like signals responsibly.

### Scope

- [ ] Add explicit intent signals in feedback (`focus`, `relax`, `learn`, `entertain`).
- [ ] Session-level mood tags (manual opt-in, privacy-first).
- [ ] Context-aware ranking profiles (time-of-day, session type).
- [ ] "Autopilot" mode: selected interests are auto-queued for background download.

### Exit Criteria

- Recommendations adapt by selected intent profile.
- Autopilot queue behavior is deterministic and auditable.
- All sensitive personalization toggles are opt-in and reversible.

## Phase F: v1.0 Public Release

### Objective

Production-grade open-source release for broad self-hosting.

### Scope

- [x] Migration system and compatibility guarantees.
- [x] Backups, restore verification, and disaster recovery guide.
- [x] Docker Compose and systemd deployment profiles.
- [ ] Security hardening and release checklist.
- [ ] Maintainer workflow and release cadence.

### Exit Criteria

- Versioned upgrade path across minor releases.
- One-command deploy for Linux and Raspberry Pi profiles.
- Published governance and support expectations.

## Next 4-Week Execution Plan

1. Add metrics endpoint + structured logs.
2. Build network/offline state manager and sync windows.
3. Implement storage/offline planner with configurable target hours.
4. Create first Bunku Mode UI skeleton (home rails, playback, queue panel).
