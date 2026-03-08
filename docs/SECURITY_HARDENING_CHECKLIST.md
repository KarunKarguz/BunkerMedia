# Security Hardening Checklist

Use this checklist for pre-release and periodic hardening reviews.

## Runtime and Deployment

- [ ] Run as non-root user (systemd/Docker).
- [ ] Bind service to LAN-only interface unless explicitly exposed.
- [ ] Restrict firewall ingress to trusted subnets.
- [ ] Use read-only mount where possible for config and app code.
- [ ] Separate write paths for `media/`, `logs/`, `backups/`.

## Secrets and Credentials

- [ ] Do not store credentials in repository files.
- [ ] Use environment variables or host secret manager.
- [ ] Rotate credentials and tokens periodically.

## API Surface

- [ ] If exposed outside localhost/LAN, enable API authentication.
- [ ] Rate-limit external endpoints where possible.
- [ ] Validate all incoming payloads and paths.
- [ ] Avoid returning sensitive local filesystem details in errors.

## Supply Chain

- [ ] Pin dependencies and review updates before rollout.
- [ ] Run vulnerability scans (`pip-audit` or equivalent).
- [ ] Verify third-party provider plugins before enabling.

## Data Safety

- [ ] Schedule periodic `bunker backup` jobs.
- [ ] Verify restore process in staging (`bunker restore`).
- [ ] Protect backup archives with filesystem permissions.

## Observability and Incident Response

- [ ] Enable structured logs (`log_format: json`) in production.
- [ ] Scrape `/metrics` and alert on dead-letter growth.
- [ ] Track repeated download failures and provider errors.

## Release Gate

- [ ] CI green on all supported Python versions.
- [ ] Migration checks and schema version verified.
- [ ] Changelog and roadmap updates completed.
- [ ] SBOM (`bunkermedia-sbom.cdx.json`) and `sha256sums.txt` attached to release.
- [ ] Security checklist reviewed and signed off.
