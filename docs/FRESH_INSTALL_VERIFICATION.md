# Fresh Install Verification

BunkerMedia includes automated clean-install verification for Linux and the Raspberry Pi preset.

## Assets

- Linux verification script: `scripts/verify_fresh_install.sh`
- Raspberry Pi preset verification script: `deploy/raspberrypi/verify_pi_install.sh`
- Workflow: `.github/workflows/install-verify.yml`

## Linux Verification

Command:

```bash
bash scripts/verify_fresh_install.sh
```

Checks performed:

- install package into an isolated target directory,
- create a clean config and empty media state,
- run CLI commands:
  - `status`
  - `schema`
  - `providers`
- start the HTTP server,
- verify `/health` and `/bunku` respond.

## Raspberry Pi Preset Verification

Command:

```bash
bash deploy/raspberrypi/verify_pi_install.sh
```

Checks performed:

- stage a clean copy of the repo payload,
- run `deploy/raspberrypi/setup_pi.sh`,
- verify the Pi preset config boots cleanly,
- run CLI `status` and `schema`,
- start the HTTP server,
- verify `/health` and `/bunku` respond.

## Important Boundary

The Pi verification validates the preset bootstrap and startup path from a clean environment. It does not claim to replace validation on real Raspberry Pi hardware for:

- thermal behavior,
- USB/storage quirks,
- HDMI/TV browser playback behavior,
- low-power network conditions.
