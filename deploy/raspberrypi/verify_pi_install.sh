#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_ROOT="$(mktemp -d)"
TARGET_ROOT="$WORK_ROOT/BunkerMedia"
trap 'rm -rf "$WORK_ROOT"' EXIT

mkdir -p "$TARGET_ROOT"
cp -R "$SOURCE_ROOT/src" "$TARGET_ROOT/src"
cp -R "$SOURCE_ROOT/deploy" "$TARGET_ROOT/deploy"
cp "$SOURCE_ROOT/README.md" "$TARGET_ROOT/README.md"
cp "$SOURCE_ROOT/setup.py" "$TARGET_ROOT/setup.py"
cp "$SOURCE_ROOT/pyproject.toml" "$TARGET_ROOT/pyproject.toml"
cp "$SOURCE_ROOT/MANIFEST.in" "$TARGET_ROOT/MANIFEST.in"
cp "$SOURCE_ROOT/requirements.txt" "$TARGET_ROOT/requirements.txt"

python3 -m pip install --upgrade pip
python3 -m pip install --target "$WORK_ROOT/site" "$TARGET_ROOT"
export PYTHONPATH="$WORK_ROOT/site${PYTHONPATH:+:$PYTHONPATH}"

bash "$TARGET_ROOT/deploy/raspberrypi/setup_pi.sh" >/dev/null
bash -n "$TARGET_ROOT/deploy/raspberrypi/setup_pi.sh"

pushd "$TARGET_ROOT" >/dev/null
python3 -m bunkermedia --config "$TARGET_ROOT/config.yaml" status --json >/dev/null
python3 -m bunkermedia --config "$TARGET_ROOT/config.yaml" schema --json >/dev/null

python3 -m bunkermedia --config "$TARGET_ROOT/config.yaml" serve --host 127.0.0.1 --port 18081 >"$WORK_ROOT/pi-server.log" 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:18081/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

curl -fsS "http://127.0.0.1:18081/health" >/dev/null
curl -fsS "http://127.0.0.1:18081/bunku" >/dev/null
cleanup
trap 'rm -rf "$WORK_ROOT"' EXIT
popd >/dev/null

echo "Raspberry Pi preset install verification passed."
