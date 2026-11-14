"""Small, optional bridge from a completed game to the Aura web shell."""
import json
import math
import sys


_FIELDS = (
    "score",
    "accuracy",
    "mistakes",
    "hits",
    "avg_reaction_ms",
    "duration",
    "stats",
    "extra",
)


def _json_safe(value):
    """Keep payloads JSON-compatible and never emit NaN or infinity."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return None


def _payload(game_id, difficulty, result):
    performance = {
        key: result.get(key)
        for key in _FIELDS
        if key in result
    }
    return _json_safe({
        "game_id": game_id,
        "difficulty": difficulty,
        "result": performance,
    })


def send_session(game_id, difficulty, result):
    """Send one completed game's performance result to the Aura page.

    Desktop/native launches are intentionally a no-op. The browser shell owns
    queueing, session IDs, timestamps, and health-data boundaries.
    """
    if sys.platform != "emscripten":
        return False
    try:
        from platform import window
        callback = getattr(window, "auraGameSession", None)
        if not callback:
            return False
        encoded = json.dumps(_payload(game_id, difficulty, result),
                             allow_nan=False, separators=(",", ":"))
        callback(encoded)
        return True
    except Exception as exc:
        print(f"[AURA] game-session export failed: {exc}",
              file=sys.stderr)
        return False
