# Integrated demo handoff — 2026-11-14

## Delivered scope

The backend-served calm timeline console is preserved. This integration combines the host Serial/capture/stdin → MQTT bridge, the published Lunar Arcade Hub raw check-ins, and the finalized anomaly-model deployment with compatible core scaling. It does not import the retired main/frontend/model-branch UI. The later [offline-game and actual-Wokwi follow-up](offline-and-wokwi-verification.md) also includes the narrowly ported firmware component and supersedes the original CDN/token limitations.

Source baseline: `backend` `45811995bfbf62016921bccd292c1753c2b85e34` (refetched before final save). Components: hardware `a7c67916ad9ae734ec181f5d28c8243b68fcb018`, games `efa97792e956671a91390e342ea4c1c373934258`, narrow model port `438e91dd1f1a4ae087b30c4645f1051b7720c07a`. The actual combined core runtime was built from `44dc461834054cfe05f1ac0f42d30e8eefd1c68f`; later vendored static assets were checked separately and copied into the preview without rebuilding that image. Hardware and games also have open component PRs #1 and #2. Review the combined PR as the full-stack entry point; no PR was merged during this work.

## Observed checks

The exact combined source passed **148 pytest tests, 1 skipped, 1 existing Starlette/httpx deprecation warning**, in 82.22 seconds. The skipped test requires local trained artifacts; the baked model image was checked separately. Node outbox and PVT fake-clock checks, JavaScript/Python/shell syntax, source/bundle parity tests, Git whitespace checks and Compose validation passed. A separate read-only integration review found no confirmed blockers.

A real isolated root-Compose broker/core/model stack passed the following checks, using synthetic fixtures rather than live crew data:

- The real host bridge delivered 106 seven-signal firmware-format readings; duplicate replay added zero rows. REST status/trend/timeline, provenance, WebSocket delivery, core restart persistence, one queued QoS 1 reading while core was stopped (107 total), broker-down visible nonzero failure and reconnection passed.
- Core anomaly output exactly matched a direct call to the actual model container for the core's normalized 14-day window, including version, detector scores, contributions and drift. Missing hardware-only features were zero; all values were finite and capped at ±8. Health baseline rows stayed separate from model-only blended normalization.
- All six game IDs saved bounded raw sessions, repeated UUIDs added zero rows, conflicting crew payloads returned 409, explicit timestamps normalized to UTC, and a game-only crew was not registered as a health crew. Game saves left readings, persisted baselines, alerts and model output unchanged.
- Six game sessions survived a combined-core restart and a 40-day built-in `co2_creep` simulated replay. Explicit deletion of a separate isolated game-only fixture cleared its history.
- Canonical check-in still generated exercise, mood and PVT-lapse readings with the published 355 ms cutoff; these are separate from game data. The existing console's 90-second test deadline has deterministic coverage.
- With the model actually stopped and a new uncached window, anomaly scoring became unavailable while the CO₂ red band and rule alerts continued. Model scoring recovered after the existing 10-second retry backoff.
- Root model runtime was non-root/read-only with `/tmp` tmpfs, dropped capabilities and no-new-privileges. Final core health: MQTT connected, **424 simulated readings, 0 rejects**. Model healthy, version `8d30c5cab8db`.

Before this combined check, actual browser Speed Click completion and a genuine core-down failed send/manual retry saved the same retained UUID once. Those three actual game sessions remain in a separate preserved preview database; the six combined acceptance sessions above are synthetic API fixtures, not six gameplay trials. Both ESP32 PlatformIO environments and all three Wokwi custom chips compiled successfully. The standalone model container passed 43 runtime checks; its measured restart reached healthy in 5518 ms.

## Model provenance

The model source, deployment and calibrated signal configuration match published model commit `070ed6dc581bc2d0ba69f0d5ee9efb20c73b8746`. The user's supplied `deploy/model/build.sh` was run: on a fresh checkout it **trained the missing default seed-0 artifacts**, then built the image. No model redesign, tuning or pre-existing registry-image pull was performed. The combined test reused that image without rebuilding or retraining it.

Model image `aura-bio/model:local`: `sha256:7e94f504fc76e43ee7b002d539d54e8698405eb5c0f0ed380a2c62e909043ea8`.

Combined core image: `sha256:70d93dfaf1fb28514d8cdc5d1b8a8838c29159b3282e15c47ba0fbc54ddb81b8`.

## Start the project

From the repository root, with Docker/Compose and uv available:

```bash
uv sync
# Creates default artifacts only if missing, then builds the model image.
deploy/model/build.sh
docker compose up --build
```

Open the core console on port 8000; model health is on port 8001 and the broker is on 1883. Use the Mission dialog's built-in demo replay if empty; all demo crew data is simulated. Run only one core per broker because its MQTT client ID is fixed. Hardware optional serial setup and failed-send replay instructions are in `hardware/README.md`; game consent/context, storage, manual retry and bundle rebuild instructions are in `web/static/lunar-arcade-hub/README.md`.

Sandbox acceptance used a separate Docker socket, project name, ports and volumes, plus a test-only host build network override required by that sandbox. These do not change repository networking or the normal commands above. Original user `core.db` was not changed. Temporary hardware test containers/image were removed after evidence was saved; their test volume and all game preview data were preserved.

## Honest limits

Actual Wokwi execution and a cold-offline game launch are now verified in the follow-up report; the original synthetic transport fixtures above remain explicitly synthetic. Physical serial capture, device flashing and hardware calibration were not completed. No real crew or clinical validation, production authentication/TLS or load/security certification is claimed. Games require a reachable local AURA-Bio server, but no public CDN; Wokwi itself still requires its online service and token. Desktop/projector rendering was inspected; mobile and assistive-technology testing were not completed. The sandbox runtime is a temporary verification preview, not a published always-on deployment.
