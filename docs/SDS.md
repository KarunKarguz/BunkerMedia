# System Design Specification

## Overview

This document now covers two major design slices:

- privacy-aware control and vault behavior,
- local artwork enrichment and poster caching for the OTT catalog.

## Design Decisions

1. Encrypted storage over app-side encrypted blobs
- The design uses encrypted filesystem/volume detection plus a marker-file override.
- This preserves normal file streaming, seek behavior, and Raspberry Pi performance.
- It avoids building a fragile custom media-blob crypto format into the application.

2. Privacy state in metadata
- Each video stores `privacy_level`:
  - `standard`
  - `private`
  - `explicit`
- Each profile stores:
  - `can_access_private`
  - optional `pin_hash`
  - `is_kids`

3. Service-layer enforcement
- Visibility filtering is applied in the service layer before data is returned to the UI or API clients.
- Recommendation generation also filters private media for unauthorized profiles.
- Stream path resolution uses the filtered video lookup path so hidden items cannot be streamed by ID from non-vault profiles.

4. Local artwork over client-side remote fetches
- Artwork should be served from the BunkerMedia server, not fetched directly by the browser from third-party providers.
- This avoids leaking client devices directly to external thumbnail hosts.
- When no cached artwork exists, the service may download and store a thumbnail server-side or generate a local SVG fallback.

## Schema Changes

Migration `v6` adds:

- `videos.privacy_level`
- `profiles.can_access_private`
- `profiles.pin_hash`

Migration `v8` adds:

- `videos.thumbnail_url`
- `videos.artwork_path`

## Runtime Components

1. `storage_privacy.py`
- Detects mount information from `/proc/mounts`
- Flags obvious encrypted filesystems and known encrypted mount sources
- Accepts a configured marker file for cases like LUKS-backed ext4 where encryption is not directly inferable

2. `service.py`
- hashes profile PINs
- validates profile selection against optional PINs
- exposes privacy state
- filters private/explicit content for unauthorized profiles

3. `server.py`
- exposes `/privacy`
- supports profile creation/update/select with private-access and PIN fields
- exposes `/videos/{video_id}/privacy`

4. `ui/`
- shows privacy-vault state in the appliance dashboard
- allows private-vault profile creation
- prompts for a PIN when selecting a locked profile
- allows private-vault profiles to mark media as `private` or `explicit`

5. `artwork.py`
- downloads remote thumbnail metadata into a local artwork cache
- generates fallback SVG posters for titles without source artwork
- preserves the local-only privacy model by giving Bunku a stable local artwork route

## Testing Strategy

- Integration tests verify:
  - privacy endpoint availability
  - PIN-protected profile selection
  - private media visibility filtering
  - local artwork route availability
  - resumable sidecar/local artwork behavior through local provider discovery
- Unit tests verify:
  - storage privacy marker compliance
  - service-level hidden/visible behavior across profiles

## Known Constraints

- Mount detection is heuristic; marker-file confirmation exists for uncertain cases.
- Re-encoding/compression is not part of this privacy slice because it conflicts with low-power operation and can degrade quality.
