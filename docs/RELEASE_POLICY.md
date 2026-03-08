# Release Policy

This policy defines versioning, release cadence, and support windows for BunkerMedia.

## Versioning

- BunkerMedia follows semantic versioning (`MAJOR.MINOR.PATCH`).
- `PATCH`: bug fixes, security fixes, and non-breaking operational updates.
- `MINOR`: backward-compatible features and improvements.
- `MAJOR`: breaking changes or compatibility resets.

## Cadence

- Patch releases: as needed, with a target at least once per month when fixes are pending.
- Minor releases: target every 6 to 8 weeks.
- Critical security fix releases: target within 72 hours of validated report.

## Release Workflow

- All releases are tag-driven (`v*`) through `.github/workflows/release.yml`.
- A release must pass compile and test gates in CI before artifacts are published.
- Each release publishes:
  - source distribution and wheel,
  - CycloneDX SBOM (`bunkermedia-sbom.cdx.json`),
  - dependency manifest (`dependencies.txt`),
  - checksum manifest (`sha256sums.txt`).

## Branching and Stability

- `main` is the only release branch for current development.
- Release tags must point to commits already validated by CI.
- Hotfixes are merged to `main` and released as patch versions.

## Compatibility and Deprecation

- Migrations must preserve upgrade safety across minor releases.
- Deprecations should be documented at least one minor release before removal.
- Breaking changes are only introduced in a major release and must include upgrade notes.

## Support Window

- Active support is provided for:
  - the latest minor release line,
  - and the immediately previous minor release line.
- Older releases are best-effort and may not receive patch backports.
