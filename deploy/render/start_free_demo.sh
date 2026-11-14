#!/bin/sh
# Free-demo state is ephemeral. Only the core binds a public interface.
set -eu
mkdir -p /tmp/aura-demo
broker_pid= model_pid= core_pid=
cleanup() {
  for pid in ${core_pid:-} ${model_pid:-} ${broker_pid:-}; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in ${core_pid:-} ${model_pid:-} ${broker_pid:-}; do
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 143' TERM INT
mosquitto -c /app/mosquitto.conf &
broker_pid=$!
uvicorn model.service:app --host 127.0.0.1 --port 8001 --workers 1 --no-server-header &
model_pid=$!
python - <<'PY'
import json,time,urllib.request
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=1) as response:
            if json.load(response).get('status') == 'ok':
                break
    except OSError:
        pass
    time.sleep(0.25)
else:
    raise SystemExit('Model did not become ready within 30 seconds')
PY
python seed_demo.py
uvicorn core.app:app --host 0.0.0.0 --port "${PORT:-10000}" --workers 1 --no-server-header &
core_pid=$!
wait "$core_pid"
