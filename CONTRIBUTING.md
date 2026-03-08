# Contributing to BunkerMedia

Thanks for contributing.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

## Local Checks

```bash
python3 -m compileall -q src tests
python3 -m pytest -q
python3 -m bunkermedia --help
```

## Branch and PR Flow

1. Create a feature branch from `main`.
2. Keep commits focused and atomic.
3. Add tests for behavior changes.
4. Open a PR with problem statement, approach, and validation output.

## Coding Guidelines

- Python 3.10+ compatible.
- Prefer low-memory, low-CPU algorithms for Raspberry Pi.
- Keep external dependencies minimal.
- Document config and API changes in `README.md`.

## Pull Request Checklist

- [ ] Code compiles and tests pass locally.
- [ ] New behavior has tests.
- [ ] No secrets or local artifacts committed.
- [ ] Docs updated where relevant.

## Project Policies

- Governance and support: `docs/GOVERNANCE.md`
- Release cadence and version policy: `docs/RELEASE_POLICY.md`
- Security reporting: `SECURITY.md`
