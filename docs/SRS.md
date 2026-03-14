# Software Requirements Specification

## Purpose

BunkerMedia provides a local-first media acquisition and playback system for self-hosted environments, with special emphasis on Raspberry Pi and home-LAN appliance usage.

## Functional Requirements

1. Media acquisition
- The system shall download supported sources through authorized providers.
- The system shall avoid duplicate downloads using archive tracking and metadata dedupe.

2. Media serving
- The system shall list, search, and stream locally stored media over the LAN.
- The system shall track watch, like, dislike, and rating signals.
- The system shall expose local artwork URLs for supported catalog items.
- The system shall generate fallback artwork when source artwork is unavailable.

3. Profiles
- The system shall support multiple local profiles.
- A profile may be marked as kids-safe.
- A profile may be granted private-vault access.
- A profile with vault access may optionally require a PIN for selection.

4. Private vault
- The system shall support marking media as `standard`, `private`, or `explicit`.
- The system shall hide `private` and `explicit` items from profiles without vault access.
- The system shall block `explicit` items from kids-safe profiles.
- The system shall expose private-storage health through the API and UI.

5. Storage privacy
- The system shall support a private mode that verifies whether the media store appears to be on encrypted storage.
- The system shall support a marker-file override when encrypted storage cannot be inferred from mount metadata.

6. Offline operation
- The system shall remain usable when internet access is unavailable.
- The system shall support offline inventory planning and storage enforcement.

7. Catalog presentation
- The system shall cache artwork locally when remote thumbnail metadata is available.
- The system shall preserve local sidecar artwork when organizing imported media.

## Non-Functional Requirements

1. Performance
- The system shall run on low-power Linux devices, including Raspberry Pi.
- Privacy features shall avoid heavy transcoding or custom encrypted blob storage in the default path.

2. Security and privacy
- The system shall be LAN-first and local by default.
- The system shall not require external telemetry.
- At-rest privacy shall rely on encrypted storage verification rather than claiming transparent, no-cost media compression.

3. Maintainability
- The system shall track schema versions and migrations.
- Product, design, and operational documentation shall be updated alongside implemented features.

## Out of Scope for This Slice

- True transparent re-compression with identical quality guarantees for already-compressed video.
- Full DRM, cloud sync, or non-local trust models.
- Internet-facing auth hardening beyond the current LAN-first deployment model.
