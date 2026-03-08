# Governance and Support

This document defines how BunkerMedia is maintained as a public open-source project.

## Maintainers

- Current maintainer: `@KarunKarguz`.
- Maintainers are responsible for:
  - release decisions and tagging,
  - roadmap prioritization,
  - security and dependency posture,
  - final review for high-risk changes.

## Decision Model

- Normal changes: merge after at least one maintainer approval and green CI.
- High-risk changes (schema, queue semantics, downloader behavior, security): require explicit maintainer sign-off.
- Security incidents follow `SECURITY.md` and private disclosure flow.

## Issue and PR Triage

- New issues are triaged on a weekly cadence.
- Pull requests are reviewed on a best-effort basis.
- Priority order:
  - security defects,
  - data corruption/regression risks,
  - reliability/performance regressions,
  - feature work.

## Support Expectations

- Community support is provided through GitHub issues.
- Bug reports should include:
  - environment details (OS, Python version),
  - config snippets (without secrets),
  - logs and reproducible steps.
- Maintainers aim to acknowledge:
  - security-related reports within 72 hours,
  - regular issues within 7 days.

## Contributor Path to Maintainer

- Consistent high-quality contributions (code, tests, docs, reviews).
- Demonstrated reliability in triage and release quality.
- Agreement to follow this governance and release policy.
