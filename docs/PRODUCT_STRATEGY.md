# BunkerMedia Product Strategy

## Positioning

BunkerMedia is a `privacy-first local OTT` product.

That means:

- local-first instead of cloud-first,
- offline-capable instead of online-dependent,
- household-focused instead of single-admin-only,
- appliance-oriented instead of script-oriented.

## Primary User Types

1. Solo self-hoster
- wants one local box for acquisition and playback
- accepts some setup complexity
- values observability and control

2. Family/home user
- wants couch-safe, simple playback
- needs profiles, kids controls, and continue-watching
- should not need CLI knowledge

3. Off-grid or low-connectivity user
- needs watch-ready content when internet is unavailable
- needs resumable downloads, storage budgeting, and predictable sync windows

## Product Principles

1. LAN first
- local playback must remain the default operating mode

2. Privacy by architecture
- private content protection must rely on encrypted local storage plus profile controls
- the product should avoid false promises like “free compression with no tradeoffs”

3. Low-power respect
- Raspberry Pi and modest Linux boxes are first-class targets
- default features should avoid expensive background work unless explicitly enabled

4. Appliance UX over admin UX
- a household should experience Bunku as a streaming front end, not as a settings console

5. Explainable intelligence
- recommendation and autopilot behavior should be understandable, auditable, and reversible

## 1.0 Definition

`1.0` means BunkerMedia can honestly be described as:

`A self-hosted, privacy-first, offline-capable local OTT appliance for home use.`

That claim requires:

- polished playback and catalog browsing
- strong private-vault and kids controls
- stable long-running acquisition and offline behavior
- operational clarity for self-hosters
- public OSS release discipline

## What 1.0 Is Not

`1.0` does not require:

- cloud sync
- DRM
- piracy adapters
- internet-exposed auth as a core deployment assumption
- heavy default transcoding on Raspberry Pi

## Product Risks

1. Trying to become every kind of media app at once
- mitigation: keep `1.0` focused on local OTT fundamentals

2. Over-building “AI” before finishing OTT basics
- mitigation: polish playback, library, and controls before deeper sentiment features

3. Privacy claims outrunning real architecture
- mitigation: keep privacy rooted in encrypted storage and access controls

4. Pi support collapsing under feature weight
- mitigation: prefer optional enrichments and low-power defaults

## Near-Term Product Bets

1. Artwork and metadata enrichment
- raises perceived product quality quickly

2. Better household controls
- necessary for real family use, not just self-hosted demos

3. Continuous ingest and duplicate control
- turns the box into a real local media appliance

4. Strong CI and release gates
- converts the project from promising to trustworthy
