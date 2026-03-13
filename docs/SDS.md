# System Design Specification

## Overview

This slice adds a privacy-aware control plane to BunkerMedia without changing the fundamental storage and playback architecture.

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

## Schema Changes

Migration `v6` adds:

- `videos.privacy_level`
- `profiles.can_access_private`
- `profiles.pin_hash`

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

## Testing Strategy

- Integration tests verify:
  - privacy endpoint availability
  - PIN-protected profile selection
  - private media visibility filtering
- Unit tests verify:
  - storage privacy marker compliance
  - service-level hidden/visible behavior across profiles

## Known Constraints

- Mount detection is heuristic; marker-file confirmation exists for uncertain cases.
- Re-encoding/compression is not part of this privacy slice because it conflicts with low-power operation and can degrade quality.
