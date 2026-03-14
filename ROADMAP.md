# BunkerMedia 1.0 Roadmap Reassessment

BunkerMedia is not just a downloader plus player. The `1.0` target is a privacy-first local OTT appliance: a self-hosted, LAN-native media system that feels closer to a personal Netflix than a toolbox.

## Product North Star

BunkerMedia should become `LocalOTT`:

- fully useful on a home LAN with no internet,
- privacy-first by default,
- optimized for Raspberry Pi and low-power Linux boxes,
- opinionated enough to feel like a real consumer product,
- open enough for public self-hosters and contributors.

## Product Promise

For `1.0`, a household user should be able to:

1. open one local URL on TV, phone, tablet, or laptop,
2. browse a polished local catalog,
3. watch smoothly with per-profile progress and recommendations,
4. trust that private media stays hidden behind local controls,
5. trust that downloads, imports, retries, and offline caching continue in the background,
6. operate the system as an appliance, not as a development project.

## Scope Boundaries

To keep the public OSS project safe and maintainable:

- built-in providers must target authorized, public, or user-owned content,
- no piracy-focused workflows will be added to core,
- no DRM or cloud trust model is part of `1.0`,
- no default heavy transcoding pipeline is required for `1.0`,
- internet-facing auth is not a `1.0` requirement if the primary deployment remains LAN-first.

## Current Assessment

### Already strong

- download queue, retries, dead letters, and resumable batch recovery
- SQLite metadata, migrations, backups, and restore flow
- YouTube/RSS/local providers
- recommendation engine and offline planner
- Pi-friendly deployment profile
- Bunku UI with TV mode, PWA shell, profiles, and private-vault controls
- encrypted-storage-aware privacy model

### Not yet `1.0`

The project is currently closer to a strong public beta than a final `1.0` product.

Main reasons:

- the OTT experience is functional but not yet premium,
- parental and private-vault controls need hardening,
- metadata enrichment and catalog presentation are still incomplete,
- CI quality gates and release validation are not yet strict enough,
- the roadmap has been phase-driven, but `1.0` needs to be release-bar driven.

## 1.0 Product Pillars

### Pillar 1: LocalOTT User Experience

The system must feel like a local streaming product, not an admin dashboard.

`1.0` requirements:

- polished home screen rails
- rich media cards with poster/thumb artwork
- fullscreen-first playback flow
- continue-watching per profile
- strong TV remote / keyboard navigation
- mobile and tablet LAN usability
- recommendation explanations available but non-intrusive

### Pillar 2: Privacy-First Household Use

The system must support family/shared-home use without weakening local privacy.

`1.0` requirements:

- vault-capable profiles
- PIN-protected profile switching
- kids mode with stronger allow/block behavior
- private and explicit content hidden from unauthorized profiles
- encrypted storage verification surfaced clearly in the UI
- no external telemetry by default

### Pillar 3: Reliable Off-Grid Media Acquisition

The system must remain useful when connectivity is poor or unavailable.

`1.0` requirements:

- resumable playlist/channel/trending batch downloads
- offline watch-horizon planning
- storage-budget enforcement
- continuous local/NAS ingest
- queue retry and recovery across restarts
- staged sync when network returns

### Pillar 4: Library Intelligence and Organization

The catalog must become easier to browse and more meaningful than a raw file list.

`1.0` requirements:

- richer library classification
- movie/show/episode heuristics for local imports
- channel/topic grouping
- artwork and preview metadata caching
- duplicate awareness across imports and downloads

### Pillar 5: Public OSS Release Quality

The repo must meet a real open-source `1.0` bar.

`1.0` requirements:

- clean install and upgrade path
- migration validation from prior schema versions
- multi-arch distribution artifacts
- enforced lint/type/test gates
- release notes, governance, security checklist, and ops docs kept current

## 1.0 Release Bar

`1.0` is complete only when all sections below are true.

### UX and Playback

- [x] poster/thumb enrichment exists and is cached locally
- [ ] fullscreen playback flow exists in Bunku
- [ ] continue-watching is prominent and profile-aware
- [ ] TV remote / keyboard flow is stable on couch-distance displays
- [ ] search, filters, and recommendation actions are complete in the UI

### Privacy and Household Controls

- [ ] PIN rotation/change flow exists
- [ ] kids mode supports explicit allow/block controls
- [ ] vault state is visible and understandable from the UI
- [ ] private/explicit media cannot leak through search, rails, recommendations, or direct stream access

### Acquisition and Library

- [x] resumable batch downloads exist
- [ ] continuous NAS/import watcher exists
- [ ] duplicate detection is strengthened across providers/imports
- [ ] unified source prioritization and dedupe policy exists
- [ ] richer local library classification exists

### Reliability and Offline Operation

- [x] retry/dead-letter queue exists
- [x] offline planner exists
- [x] storage policy exists
- [ ] startup/upgrade validation across multiple prior DB versions exists
- [ ] long-run soak results are documented

### Public Release Engineering

- [ ] `ruff` gate in CI
- [ ] `mypy` gate in CI
- [ ] coverage threshold in CI
- [ ] multi-arch container publishing
- [ ] clean fresh-install verification on Linux and Raspberry Pi

## Execution Plan to Reach 1.0

### Track A: OTT Polish

1. Add fullscreen playback and stronger focus-memory behavior.
2. Add recommendation actions: `not interested`, `hide channel`.
3. Improve continue-watching and per-profile shelves.
4. Refine artwork quality policy and lightweight refresh rules.

### Track B: Privacy and Family Controls

1. Add PIN rotation/change flow.
2. Add channel allow/block controls for kids mode and vault profiles.
3. Surface clearer vault-health messaging in Bunku.

### Track C: Acquisition and Off-Grid Appliance

1. Add continuous NAS/import folder watcher.
2. Improve duplicate detection across imports/downloads/providers.
3. Add source-priority policy and smarter autoplay/offline autopilot rules.

### Track D: 1.0 Release Hardening

1. Add `ruff`, `mypy`, and coverage gates in CI.
2. Add migration-upgrade validation for older database states.
3. Publish multi-arch images and verify fresh Pi/Linux installs.
4. Document a formal `1.0` release checklist.

## Best-In-Class Differentiators

If BunkerMedia is going to be more than "yet another self-hosted media app", these are the differentiators to keep:

- LAN-first and offline-first, not cloud-first
- privacy model grounded in encrypted local storage and profile isolation
- Pi-friendly and low-power aware
- intelligent acquisition instead of passive file serving only
- one local web app that works across TV, mobile, and desktop

## Explicit `1.0` Blockers Right Now

These are the top blockers preventing a clean `1.0.0` release today:

1. no fullscreen-first premium playback flow yet
2. no PIN rotation or stronger parental allow/block controls yet
3. no continuous NAS watcher yet
4. no CI quality-gate stack (`ruff` / `mypy` / coverage) yet
5. no documented upgrade-validation matrix yet

## After 1.0

These are valid post-`1.0` opportunities, but they should not block the release:

- casting integrations
- optional mobile companion flows
- plugin registry with community adapters
- deeper intent/mood models
- optional transcoding or storage optimization profiles

## Status

Current status: `public beta`, not `1.0`.

The core platform is real. The `1.0` work now is about turning it into a polished, household-ready, privacy-first local OTT product.
