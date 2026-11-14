"""Small opt-in boundary for the public simulated demo.

The default local app is deliberately unchanged. When enabled, this middleware
keeps reads public, protects every other mutating HTTP route with the admin
bearer token, and limits mutation bodies before FastAPI parses them.
"""
from __future__ import annotations

import hmac
import json
import math
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

PUBLIC_BODY_LIMIT = 64 * 1024
SHOWCASE_COOLDOWN_SECONDS = 60.0
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_cooldown_lock = threading.Lock()
_showcase_claims: dict[str, float] = {}


def enabled() -> bool:
    return os.environ.get("AURA_PUBLIC_DEMO") == "1"


def _is_public_showcase(scope: dict[str, Any]) -> bool:
    if scope.get("method") != "POST":
        return False
    parts = scope.get("path", "").split("/")
    return len(parts) == 3 and parts[1] == "showcase" and bool(parts[2])


def _is_mutation(scope: dict[str, Any]) -> bool:
    return scope.get("method", "").upper() in _MUTATING_METHODS


def _authorized(scope: dict[str, Any]) -> bool:
    configured = os.environ.get("AURA_ADMIN_TOKEN", "")
    raw = dict(scope.get("headers", ())).get(b"authorization", b"").decode("latin-1")
    scheme, separator, supplied = raw.partition(" ")
    matches = hmac.compare_digest(supplied, configured)
    return bool(configured) and scheme.lower() == "bearer" and bool(separator) and matches


def _response(status: int, detail: str, send: Callable[[dict[str, Any]], Awaitable[None]],
              headers: list[tuple[bytes, bytes]] | None = None) -> Awaitable[None]:
    body = json.dumps({"detail": detail}).encode()
    response_headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    if headers:
        response_headers.extend(headers)

    async def write() -> None:
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

    return write()


def _content_length(scope: dict[str, Any]) -> int | None:
    values = [value for key, value in scope.get("headers", ()) if key.lower() == b"content-length"]
    if not values:
        return None
    try:
        lengths = {int(value) for value in values}
    except (TypeError, ValueError):
        raise ValueError("invalid Content-Length") from None
    if len(lengths) != 1 or next(iter(lengths)) < 0:
        raise ValueError("invalid Content-Length")
    return next(iter(lengths))


async def _read_limited_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"".join(chunks)
        if message["type"] != "http.request":
            continue
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > PUBLIC_BODY_LIMIT:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks)


def reserve_showcase(name: str) -> tuple[float | None, int]:
    """Atomically claim a scenario, returning a claim and retry seconds."""
    now = time.monotonic()
    with _cooldown_lock:
        previous = _showcase_claims.get(name)
        if previous is not None:
            remaining = SHOWCASE_COOLDOWN_SECONDS - (now - previous)
            if remaining > 0:
                return None, math.ceil(remaining)
        _showcase_claims[name] = now
    return now, 0


def release_showcase(name: str, claim: float | None) -> None:
    if claim is None:
        return
    with _cooldown_lock:
        if _showcase_claims.get(name) == claim:
            _showcase_claims.pop(name, None)


def reset_cooldowns() -> None:
    with _cooldown_lock:
        _showcase_claims.clear()


class PublicDemoMiddleware:
    """Authorize and bound public-demo mutations without buffering huge bodies."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]],
                       send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if not enabled() or scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        mutation = _is_mutation(scope)
        if mutation and not _is_public_showcase(scope) and not _authorized(scope):
            await _response(401, "admin bearer token required for this mutation", send,
                            [(b"www-authenticate", b"Bearer")])
            return

        if mutation:
            try:
                length = _content_length(scope)
            except ValueError as exc:
                await _response(400, str(exc), send)
                return
            if length is not None and length > PUBLIC_BODY_LIMIT:
                await _response(413, f"request body must be at most {PUBLIC_BODY_LIMIT} bytes", send)
                return

            body = await _read_limited_body(receive)
            if body is None:
                await _response(413, f"request body must be at most {PUBLIC_BODY_LIMIT} bytes", send)
                return

            sent = False

            async def replay() -> dict[str, Any]:
                nonlocal sent
                if sent:
                    return {"type": "http.disconnect"}
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}

            receive = replay

        async def public_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", [])
                    if not key.lower().startswith(b"access-control-")
                ]
            await send(message)

        await self.app(scope, receive, public_send)
