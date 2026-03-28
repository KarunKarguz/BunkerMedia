#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_ROOT="$(mktemp -d)"
trap 'rm -rf "$WORK_ROOT"' EXIT

python3 -m pip install --upgrade pip
python3 -m pip install --target "$WORK_ROOT/site" "$SOURCE_ROOT"
export PYTHONPATH="$WORK_ROOT/site${PYTHONPATH:+:$PYTHONPATH}"

cat > "$WORK_ROOT/config.yaml" <<'EOF'
download_path: ./media
database_path: ./bunkermedia.db
download_archive: ./archive.txt
auto_start_workers: false
force_offline_mode: true
EOF

mkdir -p "$WORK_ROOT/media" "$WORK_ROOT/logs" "$WORK_ROOT/backups"
touch "$WORK_ROOT/archive.txt"

pushd "$WORK_ROOT" >/dev/null
python3 -m bunkermedia --config "$WORK_ROOT/config.yaml" status --json >/dev/null
python3 -m bunkermedia --config "$WORK_ROOT/config.yaml" schema --json >/dev/null
python3 -m bunkermedia --config "$WORK_ROOT/config.yaml" providers >/dev/null

python3 -m bunkermedia --config "$WORK_ROOT/config.yaml" serve --host 127.0.0.1 --port 18080 >"$WORK_ROOT/server.log" 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:18080/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

curl -fsS "http://127.0.0.1:18080/health" >/dev/null
curl -fsS "http://127.0.0.1:18080/bunku" >/dev/null
cleanup
trap 'rm -rf "$WORK_ROOT"' EXIT
popd >/dev/null

echo "Fresh Linux install verification passed."
