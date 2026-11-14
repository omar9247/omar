# Model handover

For whoever takes over the anomaly model. The data side (datasets, simulator, scenarios,
validation) is finished. Data questions go to the data owner; see "Rules" below.

## Get running

```bash
unset VIRTUAL_ENV            # if your shell exports one
uv sync
uv run pytest -q             # 23 tests, ~10 s
uv run python -m model.train # trains + calibrates both detectors, prints detection per scenario over 3 seeds
uv run uvicorn model.service:app --port 8001
```

Read first: `CLAUDE.md`, `docs/model-decisions.md` (how and why the model got here), plan sections 4.3 (model), 5.3 (simulator values and validation),
6.2 (scenarios) and 6.3 (current model performance).

## What exists

| File                   | Does                                                                                                                         |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `model/dataset.py`     | Per-astronaut z-scores against their first 14 days; windows; `confirmed()` (alarm needs 2 days in a row) |
| `model/autoencoder.py` | Dense autoencoder (flatten → 32 → 6 → 32) on 2-day windows: sudden change |
| `model/ewma.py`        | One-sided EWMA drift score (λ 0.2): slow drift; only the `harmful` direction in `signals.yaml` counts |
| `model/train.py`       | Trains on normal days only; alarm lines = 99.5th percentile over 1,000 validation astronauts; `evaluate()` runs 200 astronauts per scenario over `--seeds` training seeds |
| `model/service.py`     | FastAPI `/score`, `/health`. Score > 1 = anomalous. Returns the top detector, per-signal contributions and signed drift |
| `generator/sim.py`     | The simulator and the 7 scenarios. Your training data comes from here                                                        |
| `deploy/model/`        | Docker image for the scoring service (multi-stage, CPU torch, non-root, healthcheck); see its README                          |

## Where the model stands (plan 6.3)

| Scenario              | Flagged (combined, mean of 3 seeds)          | Median days to flag |
| --------------------- | -------------------------------------------- | ------------------- |
| Normal (false alarms) | under 0.1% of days, 4% of astronauts over 19 days | —              |
| Sleep debt            | 100%                                         | 5                   |
| Deconditioning        | 96%                                          | 4                   |
| Solar particle event  | 99%                                          | 1 (confirmation)    |
| CO₂ creep             | 23% (rules catch it)                         | —                   |
| Immune                | 5% (= normal)                                | —                   |
| Sensor loss           | 4% (= normal)                                | —                   |

Also evaluated every run: 6 research-doc patterns and a 60-scenario single-signal sweep (`model/eval_scenarios.py`,
plan 6.3). Weak spots: one signal drifting alone (24% at 1 spread vs 10% healthy over the same 39 days, 79% at 3: the rules' job;
see docs/model-decisions.md section 14), the sleep + HRV pattern (47%), anything CO₂-only. Retraining moves the autoencoder by several points; compare
changes over seeds (`--seeds`, default 3).

## What you must know about the data

1. **Normal days have few links between signals.** Sleep duration and sleep efficiency vary together
   (r 0.59, real BIDSleep data), and mood follows last night's sleep (Jones 2022 Table 1). Everything else
   is independent (a bad night does not raise the next day's heart rate or lapses), so multi-signal scenarios are easier to spot than in real life. Treat detection rates as
   optimistic.
2. **Inputs: 10 daily signals**, in the order of `model: true` in `contract/signals.yaml`. Weekly lab
   values (lymphocytes, IL-6, NK, viral shedding) are _not_ inputs; rules and the immune-risk score
   handle them.
3. **Scaling is shared with the core service.** The core service owns the baselines and sends z-scores
   to `/score`. If you change the scaling (e.g. robust scaling), the core service must change the same
   way, or live scores won't match training.
4. **Heavy tails and drift.** Reaction lapses have rare very high days; exercise and sleep efficiency
   sit just under 100% with a long tail down; cabin CO₂ drifts slowly (persistence 0.87), so a 14-day
   baseline often misses its current level.
5. **How much to trust each input:**

   | Trust                | Signals                                                                                          |
   | -------------------- | ------------------------------------------------------------------------------------------------ |
   | Real data, validated | Resting HR, sleep duration, sleep efficiency, cabin CO₂, dose                                    |
   | From papers          | HRV, systolic BP, lapse level, mood level                                                        |
   | Assumptions          | Mood day-to-day spread, all exercise values, persistence 0.4 for HRV, BP, lapses, mood, exercise |

6. **What the model should catch:** sleep debt, deconditioning, solar event. **Not:** CO₂ creep (inside
   natural drift; rules catch it), immune (lab values aren't inputs), sensor loss (stale marking).
   Don't tune toward those three; you would be fitting noise.
7. **Deconditioning sizes are the plan's proposal**, not published (HR +12 bpm over 21 days, exercise
   70%, HRV −10%).
8. **Missing values** are filled with 0 (= baseline); the core service marks them stale separately.
9. **Replay** (`generator.publish --replay`) feeds real ISS CO₂ and dose for cm1/cm2. Check false alarms
   on replayed runs too: real data has glitches the simulator doesn't.

## Rules

- **Don't change `contract/signals.yaml` values to improve model numbers.** They are calibrated to real
  data; `tests/test_validation.py` fails if a spread moves > 15%. Any data change goes to the data owner.
- Adding, removing or reordering a model input changes the shared contract: team agreement needed.
- Thresholds and patterns go in config files, not code (NFR-12).
- Keep evaluation honest: seeds 1 (train) and 2 (threshold) are used; `evaluate()` uses 1000+. Use a
  separate seed range for tuning, not the evaluation seeds.

## Two-detector design (Nov 13) and follow-up checks

Done: 2-day autoencoder (sudden change, alarm confirmed on 2 days in a row) + one-sided EWMA drift score
(`model/ewma.py`, slow drift, λ 0.2, only the `harmful` direction in `signals.yaml` counts); 7- and 14-day
autoencoders removed; alarm lines at 99.5% of 1,000 validation astronauts. Reasoning and numbers: plan 6.3.
`/score` returns `score`, `anomalous`, `detector` (`2d` or `ewma`), `scores`, `contributions`, `drift`
(signed, per signal) and needs 3–14 days. Tests: `tests/test_ewma.py`, `tests/test_service.py`.

| Follow-up | Status |
| --- | --- |
| Remove the 7- and 14-day autoencoders | Done: the pair beat them on detection and false alarms over 3 seeds |
| Harmful directions in `contract/signals.yaml` | Done (`harmful: high\|low\|both`) |
| Alarm only after 2 days in a row | Done for the autoencoder: healthy flagged 19% → 7% with the 99.5% line |
| Blend each astronaut's baseline spread with the population spread | Done, k = 6 fitted on real data (plan 4.3, 6.3); fixed CO₂ scaling |
| Cap deviations | Done at ±8 (±6 flattened the solar event) |
| Median-based scaling | Tested, rejected: solar 57% vs 100%, deconditioning flagged 4–5 days later |
| Slower EWMA (λ 0.1) | Tested, rejected: gains within noise, deconditioning flagged a day later |
| Untracked scenarios | Done: per-signal sweep + research-doc patterns run in every `model.train` |
| Score only the signals present and report missing ones, instead of filling 0 | Waits for the core service and its handling of missing data |
| Core service scaling | Written on local branch `core-scaling` (backend + model): core baseline and model window now use `model/dataset.py`'s blend and cap; a test checks live z-scores equal training's. Awaiting backend owner's review |
| Bad input at `/score` | Done: NaN/inf rejected with a clean 422 (the default error reply crashed with a 500); values clipped at ±8 like training |
| Model version | Done: `model_version` (hash of the trained files) in `/health` and every `/score` reply |
| Alarm-line stability | 1,000 validation astronauts (was 300): detection ranges tightened; the EWMA line's number still differs by seed because the per-signal scale is fitted per seed, which doesn't change detection |
| Slow sweep under-measured | Done: sweep runs 60 days, so a 21-day slow ramp holds full size for ~19 days (40-day runs stopped at 90% of size and read low); `sweep_normal` is the 60-day healthy reference, 10% flagged over 39 days. Details: decisions 16.4 |
| Container image | Done: `deploy/model/` builds a self-contained image (trained artifacts baked in, CPU-only, non-root, healthcheck; Compose runs it read-only); measured 1.34 GB, `/score` p50 2.1 ms, restart to healthy 4.5 s. See `deploy/model/README.md` |

## Deploying the service

```bash
deploy/model/build.sh                                   # trains artifacts/ if missing, then builds
docker compose -f deploy/model/compose.yaml up -d      # or: docker run -p 8001:8001 ...
curl -s localhost:8001/health
```

The core reaches it at `http://model:8001` (`AURA_MODEL_URL`) on the team's Compose network. The image
contains the trained files, so it needs no host volume; `AURA_ARTIFACTS` can point at a mount to swap
models without rebuilding. Rebuild after every retrain so `model_version` changes with the files.
