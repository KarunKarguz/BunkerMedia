#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$ROOT_DIR/media" "$ROOT_DIR/media/nas-import" "$ROOT_DIR/media/imports" "$ROOT_DIR/logs" "$ROOT_DIR/backups"
touch "$ROOT_DIR/archive.txt"

if [ ! -f "$ROOT_DIR/config.yaml" ]; then
  cp "$ROOT_DIR/deploy/raspberrypi/config.pi.yaml" "$ROOT_DIR/config.yaml"
fi

echo "BunkerMedia Raspberry Pi directories prepared."
echo "Config: $ROOT_DIR/config.yaml"
echo "Start with:"
echo "  cd $ROOT_DIR"
echo "  docker compose -f deploy/raspberrypi/docker-compose.pi.yml up --build -d"
echo "Then open:"
echo "  http://<pi-ip>:8080/bunku"
