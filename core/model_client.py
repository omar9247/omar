"""Data layer: calls the model service (plan 3.6). Never raises: when the model is down the score shows as
unavailable and rule alerts carry on (NFR-4). Env AURA_MODEL_URL (default http://localhost:8001)."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("aura.core")
URL = os.environ.get("AURA_MODEL_URL", "http://localhost:8001")
RETRY_S = 10  # after a failure, don't call again for this long, so a dead model can't slow every reading
_down_until = 0.0
_cache: dict[tuple, dict] = {}  # shortcut: never evicted; fine for a demo run, add an LRU for long runs


def score(crew_id: str, window: dict[str, list[float]]) -> dict:
    """Readings of one day arrive one by one; repeat calls with the same window hit the cache."""
    global _down_until
    key = (crew_id, json.dumps(window, sort_keys=True))
    if key in _cache:
        return _cache[key]
    if time.monotonic() < _down_until:
        return {"available": False, "reason": "model service unreachable"}
    req = urllib.request.Request(f"{URL}/score", json.dumps({"crew_id": crew_id, "window": window}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1) as r:
            _cache[key] = json.load(r) | {"available": True}
            return _cache[key]
    except Exception as e:  # noqa: BLE001
        log.warning("model service unreachable: %s", e)
        _down_until = time.monotonic() + RETRY_S
        return {"available": False, "reason": "model service unreachable"}
