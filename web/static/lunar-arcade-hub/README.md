# Lunar Arcade Hub — AURA-Bio integration

The published Pygbag 0.9.3 game visuals, timing and scoring are preserved. Open **Check-in → Open games in a new tab** in the existing FastAPI console. The hub launches at `/lunar-arcade-hub/?crew=<selected-id>&ts=<mission-time>`; the crew and mission time are captured when it opens. Opening the hub opts into saving completed sessions for that crew. The existing 90-second reaction check-in remains separate and unchanged.

The Pygbag 0.9.3 / CPython 3.12 runtime is vendored under `runtime/`, including the pinned wasm/data pack, bootstrap, local package index and pygame-ce wheel. A cold launch needs only the local game origin; the core service is still required for AURA session saves. Click the Pygbag start overlay once to unlock audio. Browser databases are namespaced by the selected crew; old standalone progress is not exported or assigned to an assumed crew. Launching `/lunar-arcade-hub/` without a crew is standalone play and never uploads results to AURA.

## What is saved

Six games share one completion hook: `lunar_alien_reaction`, `coloring_shapes`, `memory_test`, `reaction_test`, `speed_click`, `number_hunt`. The hook exports score, percentage accuracy, mistakes, hits, average reaction/response milliseconds when present, duration seconds, display stats, and raw per-game `extra` trial arrays/metadata. Local game assessments, feedback, physiology and wellbeing records are not exported.

`POST /game-sessions` validates a UUID `session_id`, crew ID, known game ID, `easy|normal|hard` difficulty, optional timezone-aware `ts`, and bounded finite `result`. Results are limited to 64 KiB. Identical UUID retries are idempotent; changing crew, performance or a supplied timestamp for the same UUID returns 409 rather than overwriting data. A missing timestamp uses the crew's newest mission reading, or UTC wall time when no readings exist; the first timestamp is retained on retry. `GET /crew/<id>/game-sessions?limit=20` returns recent saved records (limit 1–100), their UTC mission timestamps, receipt timestamps and a demo-data label.

Sessions live in a separate SQLite `game_session` table and are labelled `provenance: simulated` in this simulated-crew demo. They do **not** write canonical health readings, change health baselines/bands/alerts, call the anomaly model, or supply mood or the 90-second PVT lapse percentage. Different games measure different response tasks; those timings must not be treated as interchangeable health measurements. Mapping game data into a health/model feature requires a separately agreed and validated protocol.

## Save feedback and retries

The game tab shows **Saved for CM…** only after the core acknowledges the matching UUID. Failed sends stay in a per-crew, per-UUID localStorage outbox; choose **Retry sending** in that tab. Per-session keys prevent separate game tabs from overwriting each other's pending records. Reloading the same crew's hub offers pending sessions for manual retry; opening another crew does not send them. If browser storage is denied/full, the tab warns that the result is held only in memory: keep it open until sending succeeds. Clearing browser storage can remove unsent results.

Return to Check-in to see recent raw sessions; returning focus or choosing **Refresh sessions** reloads the list. No background polling is added. Scenario replay preserves game history. Explicit `DELETE /crew/<id>` clears that crew's game sessions along with their health/demo records; it does not erase another crew.

These APIs inherit the existing trusted, unauthenticated local-demo boundary. Do not expose them publicly with real crew data without authentication, authorization, retention controls and privacy review.

## Rebuild the archives

Runtime source is committed under `games/lunar_arcade_hub/`. From the repository root:

```bash
python tools/build_game_bundle.py
uv run pytest tests/test_game_bundle.py tests/test_game_sessions.py tests/test_game_bridge.py -q
node tests/test_game_bridge.cjs   # optional Node self-check, no npm dependencies
```

The standard-library packer reproducibly writes both `lunar_arcade_hub.tar.gz` (ordinary web hosts) and `lunar_arcade_hub.apk` (ZIP, itch.zone loader). Both preserve the published `assets/` paths and contain identical source bytes. The JS bridge is loaded by the existing HTML loader outside its protected Python/HTML separator. The alternative `/static/lunar-arcade-hub/index.html` route remains available.

The runtime source URLs, licenses, and SHA-256 checksums are recorded in `runtime/SOURCES.json`; notices are in `runtime/LICENSES.md`. Verify the committed mirror with `python tools/refresh_pygbag_runtime.py`. To refresh it deliberately, use `python tools/refresh_pygbag_runtime.py --refresh`; the script fails if any pinned upstream byte changes, so a dependency update must repin the manifest in review.

## Integration checks

Automated tests cover all six game IDs, finite/bounded input, JSON-safe errors, immutable UUID/crew/time retries, storage restart/reset behavior, archive parity/determinism, performance-only export, and browser outbox recovery/isolation/multiple tabs. Node is optional for Python-only environments. A real browser Speed Click round also completed through the Pygbag runtime and saved via the shared Python → JS → core path, while `/health` remained at zero canonical readings. This is a transport/data-capture check, not a validated reaction-performance measurement.

A later cold-offline check blocked all public origins with enforced CSP and no-store responses. Required runtime/index/wheel/game assets loaded same-origin, an actual Speed Click round saved its matching UUID once, and the separate populated core stayed at 424 readings/0 rejects. Evidence is in `docs/offline-and-wokwi-verification.md` from the repository root. This does not claim six gameplay trials or mobile testing.

A pre-existing console PVT deadline bug was repaired during integration: the 90-second test now stops even if its final stimulus is never answered and cannot accept a late response. The 90-second duration, 355 ms lapse cutoff, stimulus delays and health check-in payload are unchanged. This does not replace the separate games with the PVT protocol.
