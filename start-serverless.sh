#!/usr/bin/env bash
set -euo pipefail

# Run RunPod's official ComfyUI initialization/startup script in the background.
# It creates/syncs /workspace/runpod-slim/ComfyUI and starts ComfyUI on :8188.
/start.sh &
BASE_START_PID=$!

# Wait until ComfyUI's API is actually reachable before starting the Serverless handler.
python3.12 - <<'PY'
import sys, time
import requests

url = "http://127.0.0.1:8188/system_stats"
for i in range(180):
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            print("[start-serverless] ComfyUI API ready", flush=True)
            break
    except Exception:
        pass
    time.sleep(1)
else:
    print("[start-serverless] ComfyUI did not become ready in 180s", flush=True)
    sys.exit(1)
PY

exec /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/python -u /handler.py
