# Upgrade Validation Matrix

This document tracks the database upgrade paths that are automatically validated before release.

Current target schema:

- `8`

Automated validation source:

- `tests/test_upgrade_matrix.py`

Validated paths:

| Source state | Coverage | Result |
| --- | --- | --- |
| Fresh baseline schema (`0`) | full migration chain to current | automated |
| Schema `1` | migration to current | automated |
| Schema `2` | migration to current | automated |
| Schema `3` | migration to current | automated |
| Schema `4` | migration to current | automated |
| Schema `5` | migration to current | automated |
| Schema `6` | migration to current | automated |
| Schema `7` | migration to current | automated |
| Current schema (`8`) | no-op initialize path | covered by normal test suite |

Validation assertions:

- database initializes without startup SQL/index failures
- `schema_migrations` reaches the current schema version
- seeded legacy video metadata survives the upgrade
- profile defaults remain available after migration

Execution command:

```bash
python -m pytest -q tests/test_upgrade_matrix.py
```

Release expectation:

- any schema-changing pull request must update this matrix
- any new migration must add a validated source-state row covering the previous schema version
- tagged releases should only be cut after CI passes this matrix and the standard backup/restore checks
