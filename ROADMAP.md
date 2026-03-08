# BunkerMedia Roadmap

This roadmap tracks the project direction for a public open-source release.

## Vision

BunkerMedia should become a private, intelligent, resource-efficient media acquisition and recommendation system that anyone can self-host.

## Success Metrics

- Recommendation quality: improve watch-through rate and reduce skip/dislike events.
- Reliability: stable background workers with clear retry/failure behavior.
- Portability: Linux, WSL, Raspberry Pi support with low memory footprint.
- Operability: one-command setup, observability, and reproducible upgrades.

## Phase 1: OSS Foundation (Current)

- [x] Downloader (single/playlist/channel) with archive dedupe
- [x] Scraper (trending/channel/playlist metadata)
- [x] SQLite metadata and watch data
- [x] FastAPI media endpoints
- [x] Async worker loops
- [x] CLI (`add`, `sync`, `recommend`, `serve`)
- [x] Transcript + embedding intelligence layer
- [x] Hybrid ranking + diversity rerank + explanation output
- [x] Open-source governance baseline (contributing, code of conduct, security)

## Phase 2: Reliability and Observability

- [ ] Add job retry backoff and dead-letter queue for failed downloads
- [ ] Add metrics endpoint (Prometheus) and request/job latency histograms
- [ ] Add structured JSON logging mode
- [ ] Add DB backup/restore commands
- [ ] Add smoke integration tests for downloader/scraper/recommender flow

## Phase 3: Recommendation Quality

- [ ] Add user profile vectors by topic clusters
- [ ] Add explicit negative feedback commands (`not interested`, `hide channel`)
- [ ] Add freshness controls and long-tail discovery knobs
- [ ] Add evaluation harness (`precision@k`, `ndcg@k`, diversity index)
- [ ] Add A/B switch for ranker weight configurations

## Phase 4: Ecosystem and Extensibility

- [ ] Add provider plugin interface (YouTube, RSS, podcasts, PeerTube)
- [ ] Add web UI for queue management and recommendation explanations
- [ ] Add export/import for preferences and history
- [ ] Add optional auth and multi-user mode
- [ ] Add packaged Docker + compose deployment profiles

## Phase 5: Stable v1.0

- [ ] Migration system and release process
- [ ] Backward compatibility policy
- [ ] Performance budgets for Raspberry Pi profile
- [ ] Security hardening checklist and periodic review
- [ ] Community maintainer model and release cadence

## Near-Term Priorities (Next 4 Weeks)

1. Reliability: retry backoff and dead-letter queue.
2. Observability: metrics endpoint and structured logs.
3. Testing: integration tests and CI coverage expansion.
4. UX: richer recommendation explanations and CLI feedback tools.
