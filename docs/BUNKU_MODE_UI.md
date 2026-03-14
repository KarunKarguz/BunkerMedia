# Bunku Mode UI Specification

Bunku Mode is the local-first end-user interface for BunkerMedia.

## Core UX Goal

A household user should open one local URL and immediately:

- browse downloaded media,
- get personalized recommendations,
- play media smoothly,
- and trust background sync to prepare future content.

## Primary Screens

1. Home
- Continue Watching
- Downloaded Now
- Recommended for You
- Fresh Sync Results

2. Library
- Downloaded-only filter
- Channel filter
- Duration and freshness filters

3. Player
- Resume position
- Fullscreen OTT playback shell
- Subtitle/audio selection
- Like/Dislike/Not Interested controls

4. Queue & Sync
- Active downloads
- Retry/backoff state
- Dead-letter list with one-click retry
- Dead-letter bulk clear for cleaned-up failures
- Source sync status (online/offline)

5. Profile/Intent
- Interests and channels
- Intent presets: `focus`, `relax`, `learn`, `entertain`
- Autopilot toggle for selected interests
- Private vault profile selection and optional PIN challenge
- Active-profile PIN rotation/removal with current-PIN confirmation
- Channel allow/block editing for kids-safe and vault-capable profiles

## Background Behavior

When network is available:

- discover and score new items,
- prefetch top recommendations within storage budget,
- process retries and dead-letter review queue.

When network is unavailable:

- serve local content only,
- continue recommendations from local metadata,
- preserve queue state and resume on reconnect.

## Autopilot Rules (Initial)

- User selects interests and max storage budget.
- System reserves a configurable percentage for autopilot downloads.
- Downloads are prioritized by recommendation score and novelty.
- If storage is low, evict lowest-value unwatched cache candidates first.

## Privacy Defaults

- LAN-first, local DB by default.
- No external telemetry by default.
- All intent/mood features are opt-in.
- Private-vault mode hides marked media from non-vault profiles.
- UI should surface encrypted-storage health as an appliance status signal.
- Sensitive content protection is based on encrypted storage plus profile/vault visibility rules, not on misleading “zero-cost compression” claims.
- TV/keyboard mode should preserve focus memory across rail refreshes and player open/close cycles.
