# Model-container integration

This branch stages the finalized anomaly model as a separate `model` service in the root
`compose.yaml`. The service name, port (`8001`), core URL (`http://model:8001`), broker
service, core service, and core data volume remain unchanged. The old host artifact mount is
removed because `deploy/model/Dockerfile` bakes the model artifacts into the image.

## Model contract

The model source and tests are the finalized two-detector implementation from
`origin/anomalies-detection-model` commit `070ed6d`: a 2-day autoencoder plus one-sided EWMA.
`POST /score` requires 3--14 days and returns `detector`, both detector scores, per-signal
contributions, signed drift, and `model_version`. The core continues to treat model errors or
unavailability as an unavailable anomaly score; rule-based health bands and alerts continue
without the model.

For this integration, live model inputs are normalized from raw readings in each crew member's
first 14 calendar days. The core uses `model.dataset.baseline_stats` and its shared `BLEND_K = 6`,
`typical_sd`, and `Z_CAP = 8` values, including missing, constant, and partial signal handling.
These model baselines are deliberately separate from the existing persisted health baseline
rows: health means/SDs, charts, rules, and their one-time persistence are unchanged, so no DB
migration or silent reinterpretation of old rows is required.

The verification image `aura-bio/model:local` was built locally from the published deployment
at model commit `070ed6d` using the user's supplied `deploy/model/build.sh` path (image SHA
`sha256:7e94f504fc76e43ee7b002d539d54e8698405eb5c0f0ed380a2c62e909043ea8`,
`model_version` `8d30c5cab8db`). The script created the missing default seed-0 artifacts;
no model redesign or tuning was performed. This core compatibility change does not alter that artifact.

## Fresh clone and model updates

From a fresh clone, run the provided script from the repository root:

```bash
deploy/model/build.sh
```

The script trains the default reproducible seed only when the git-ignored artifact files are
absent, then builds `aura-bio/model:local`. It is the supported build path; do not add arbitrary
training or tuning options to deployment. Rebuild after an intentional, reviewed model update
and verify the resulting `model_version` before staging it in Compose.

The standalone model container passed 43 finite runtime checks, including input validation,
capping, stateless repeatability, artifact version and restart to healthy in 5518 ms. This is
local simulated-data verification, not clinical validation.

The combined root stack passed acceptance on 2026-11-14: the built core's score matched a
direct `/score` call to the unchanged image for the exact normalized 14-day input. With the
model stopped, a new uncached window showed the score unavailable while CO₂ red bands and
rule alerts continued; scoring recovered after the existing retry backoff. Raw game saves
left health readings, persisted baselines, alerts and model output unchanged, survived core
restart, and survived a 40-day built-in simulated scenario replay. The full merged regression
suite passed 148 tests with one trained-local-artifact test skipped; the actual image was
verified separately. Root Compose retains the standalone model's read-only rootfs, `/tmp`
tmpfs, dropped capabilities and no-new-privileges setting.
