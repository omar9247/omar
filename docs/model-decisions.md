# Anomaly model: decision log (Nov 13–14, 2026)

How the AURA-Bio anomaly model got from three autoencoders to its current form, step by step: what was
questioned, what was measured, the numbers, what was kept or rejected and why. All detection numbers come
from simulated astronauts (`generator/sim.py`), not real crews. Unless stated, "flagged" means the share of
simulated astronauts whose score crossed the alarm line at least once in the 19 days after a scenario starts
(day 21); "healthy flagged" is the same for astronauts with no scenario, i.e. false alarms.

Where things live: design in plan 4.3, results in plan 6.3, how to work on the model in
`docs/model-handover.md`. This file is the history and the reasoning.

---

## Contents

1. Starting point
2. Is an autoencoder the right model?
3. Can the datasets be combined into one training set?
4. Relations between signals
5. Two timescales: which detector for which job
6. One-sided scoring: only harmful drift counts
7. First implementation and the 3-seed comparison
8. Why healthy astronauts were flagged, and the fix
9. Removing the 7- and 14-day models; contract and service changes
10. Clarifications that shaped later steps
11. Untracked scenarios: the sweep and the research-doc patterns
12. Fixing the baseline scaling (blending, k, cap, median, slower EWMA)
13. Final state
14. Is the single-signal result good enough?
15. Open items and limits
16. Hardening, measurement fixes and the core scaling change

---

## 1. Starting point

**Repo state (commit 7605d13).** The data workstream had delivered:

- a simulator (`generator/sim.py`) calibrated per signal against real data or papers: level, day-to-day
  spread, person-to-person spread, day-to-day persistence (`contract/signals.yaml`, plan 5.3);
- 7 scenarios (plan 6.2): normal, sleep debt, deconditioning, solar particle event, CO₂ creep, immune
  dysregulation, sensor loss;
- validation of the simulator against the real datasets (`data/validate.py`).

**Model inputs.** 10 daily signals: resting heart rate, HRV (RMSSD), systolic blood pressure, sleep duration,
sleep efficiency, reaction lapses, mood, cabin CO₂, exercise completion, daily radiation dose. Weekly lab
values (lymphocytes, IL-6, NK activity, viral shedding) are not model inputs; the rules and the immune-risk
score handle them.

**Scaling.** Each signal is expressed as "spreads away from this astronaut's own baseline": the mean and
standard deviation of their first 14 days (a z-score). The core service is meant to do the same and send
these z-scores to `/score`.

**Model.** Three dense autoencoders (flatten → 32 → 6 → 32), one per window length: 2, 7 and 14 days. Each
trained on normal days only; alarm line = 99th percentile of reconstruction error on validation astronauts.
The service returned the highest of the three.

**Reported performance (plan 6.3, before any change here):**

| Scenario | Flagged |
| --- | --- |
| Healthy | 19% of astronauts in 20 days; 1.1% of days |
| Sleep debt | 64% |
| Deconditioning | 64% |
| Solar event | 91%, same day |
| CO₂ creep | 24% |
| Immune | 16% (= normal) |
| Sensor loss | 14% (= normal) |

The plan itself noted the 7- and 14-day windows had lost sensitivity and named robust (median-based) scaling
as the first thing to try.

---

## 2. Is an autoencoder the right model?

**Critique.**

- **Training data.** The original plan trained on PhysioNet BIDSleep (Earth adults, Apple Watch). That data
  has 2–3 of the model's signals; the others would be masked, so the model would learn little about them.
  The repo had already moved to training on simulated astronauts calibrated to that data, which is better.
- **Data per astronaut.** A personal model from 14 baseline days is far too little for a neural network.
- **Attribution.** Per-signal reconstruction error is mixed through the bottleneck: a signal can show error
  because a correlated one changed. It looks precise but isn't, and explainability is a requirement (NFR-6).
- **The key mechanism.** The autoencoder squares errors day by day and then averages. A small steady drift
  (e.g. 0.7 spreads low for 14 days) and ordinary noise both add positive squared terms, so the drift barely
  stands out: about 1.3 spreads above normal, versus about 2.6 if you average first and square after
  (independent-noise arithmetic). This explains why the 7- and 14-day windows were weak at slow drift.

**Alternatives considered.**

| Approach | In plain terms | Verdict |
| --- | --- | --- |
| Residual ("anti-smoothing") detection | Subtract the smoothed trend, flag what's left | Removes exactly the slow drift we need to catch; good only for spikes |
| Gaussian mixture | Learn a few normal "states", flag days that fit none | Needs far more data for 10+ dimensions; scores single days, blind to drift |
| Isolation forest | Random splits; easily isolated days are odd | Robust and easy, but scores single days and can't say which signal |
| Denoising autoencoder | Corrupt input, learn to repair it | Learns signal relationships better, but the training data had almost none; doesn't fix attribution; needs a training pipeline |
| EWMA drift score | Running average of each signal's deviation, then combine | Built for small sustained shifts; exact per-signal attribution; nothing to train |

**Decision.** Keep a neural model for sudden changes, add an EWMA drift score for slow drift (section 5).

---

## 3. Can the datasets be combined into one training set?

**Question.** Merge the real datasets into one table, then split into train and test.

**Answer: no.** The sources share no person, no dates and no cadence:

| Source | Who or what | Shape |
| --- | --- | --- |
| BIDSleep | 47 healthy Earth adults | 253 nights: heart rate, sleep |
| NASA EDA | ISS cabin, 10 missions | 423 days of CO₂ |
| RadLab | 2 ISS detectors | 180 days of dose |
| Inspiration4 | 4 crew, 3-day flight | a few blood samples each |

Joining rows would invent astronauts (one person's sleep next to another mission's CO₂), so any
relationship between columns would come from how rows were paired. Stacking them leaves most columns empty.

**What the repo does instead (kept).** Each real source calibrates part of the simulator; the model trains
on simulated astronauts who have every signal on every day. Train/validation/test are split by astronaut
(different random seeds), never by row.

**Gap noted.** `data/validate.py` validates the simulator against the same BIDSleep people it was
calibrated on. A subject-held-out check would be more honest; not done.

---

## 4. Relations between signals

**Finding.** The simulator drew each signal's day-to-day noise independently, so on normal days signals
were unrelated. A model trained on that learns "no relationships" and can't flag a broken one.

**What real data could support.** Only BIDSleep measures several signals on the same person and night.
Within-person correlations (253 nights, 47 people):

| Pair | r | approx. 95% range |
| --- | --- | --- |
| Sleep duration vs sleep efficiency | +0.59 | +0.50 to +0.67 |
| Resting HR vs sleep duration | −0.09 | −0.22 to +0.05 |
| Resting HR vs sleep efficiency | −0.06 | −0.20 to +0.07 |

Other candidates: lymphocytes vs IL-6 in Inspiration4 gave +0.33 on one assay and −0.13 on the other with 27
points: unusable. CO₂ (2014–2021) and dose (2022) share no dates. HRV, BP, lapses, mood and exercise come
from papers with no person-level data.

**What the data owner added (commit 7605d13).**

- Sleep duration ↔ efficiency linked: set to 0.74 in the noise, which gives about 0.60–0.62 in the
  simulated values (the shape near 100% weakens it); test fails if simulated and real differ by > 0.08.
- Mood follows last night's sleep, using the Jones 2022 Table 1 bins (≤4 h −0.77 … 6–7 h −0.05 vs 7–8 h).
- Resting HR left unlinked (no reliable link in the data).
- Sleep debt's separate mood effect (−0.8) removed: it double-counted the new link.

**Consequence.** The model can detect several signals drifting together (their deviations add up), but
not a broken relationship between signals, except the two links above. The cross-system claim rests on the
cited pattern rules, not on the model.

---

## 5. Two timescales: which detector for which job

**Proposal considered.** EWMA for long-term change plus a denoising autoencoder for short-term change.

**Decision.** EWMA for slow drift, and the **existing 2-day autoencoder** for sudden change, not a new
denoising one: the 2-day model already caught 91% of solar events the same day, the denoising model's
advantage (learning relationships) had little to work with, and it would add a training pipeline.

**How the EWMA score works** (`model/ewma.py`):

1. For each signal, smooth its daily z-scores: `smoothed = λ × today + (1 − λ) × yesterday's smoothed`,
   with λ = 0.2 (memory ≈ 5 days), starting from 0 (baseline), over up to 14 days.
2. Keep the sign: the smoothed value says "running high" or "running low".
3. Divide by that signal's normal size of smoothed value (measured on healthy simulated astronauts).
4. Square and add across signals.
5. Divide by the alarm line, so > 1 means "outside the chosen share of healthy days".

Averaging before squaring is what lets a steady drift accumulate while noise cancels (section 2).

---

## 6. One-sided scoring: only harmful drift counts

**Question.** Squaring discards direction; does that hurt?

- Nothing is trained on the squared score, so no learning is lost.
- Direction is kept per signal (step 2 above) and returned to the caller.
- Squaring lets drifts in opposite directions add up (sleep down, heart rate up) instead of cancelling.

**Real cost.** A two-sided score treats improvement as an anomaly (sleeping more, HRV rising).

**Decision.** One-sided only: before squaring, a signal's smoothed value is set to 0 if it moved in its
harmless direction. Directions come from the research doc's amber/red rows:

| Harmful when high | Harmful when low | Both |
| --- | --- | --- |
| Resting HR, reaction lapses, cabin CO₂, dose | HRV, sleep duration, sleep efficiency, mood, exercise | Systolic BP |

BP is two-sided: severe hypertension, and low BP with dizziness on standing. Signals that are dangerous in
the "good" direction (very low heart rate, very long sleep) are left to the threshold rules.

---

## 7. First implementation and the 3-seed comparison

**Built.** `model/ewma.py`; EWMA calibrated alongside the autoencoders in `model/train.py`; an evaluation
over several training seeds (the autoencoders move 10–20 points between retrains); EWMA added to `/score`
next to the existing fields; `tests/test_ewma.py`.

**Environment issue.** For a while this machine could not reach PyPI or the PyTorch index (connection
resets), so code was written but not run; once the network came back, `uv sync` (~2 GB) ran in the
background.

**Result (3 training seeds, mean and range; 99% alarm lines from 60 validation astronauts):**

| Detector | Healthy flagged | Sleep debt | Deconditioning | Solar | CO₂ creep |
| --- | --- | --- | --- | --- | --- |
| 2-day AE | 14% | 71% | 81% | 97% | 22% |
| 7-day AE | 10% | 48% | 79% | 27% | 15% |
| 14-day AE | 6% | 26% | 62% | 8% | 8% |
| Highest of the three (old service) | 21% (14–29) | 74% (64–84) | 90% (84–95) | 97% | 31% |
| EWMA alone | 10% | 99% | 89% | 31% | 22% |
| **2-day AE + EWMA** | 19% (14–24) | **99%** (96–100) | **92%** (90–96) | **97%** | 34% |

False alarms per healthy day: old 0.8–1.6%, pair 0.8–1.4%.

**Reading.** EWMA carries slow drift (sleep debt 96–100% in every seed); the 2-day AE carries the one-day
solar event; the 7- and 14-day models added nothing the pair missed. Decision: switch to the pair.

**Two weaknesses found.** (1) The EWMA alarm line moved from 32 to 48 between seeds although EWMA learns
nothing: 60 validation astronauts are too few to place a 99th percentile. (2) Most remaining false alarms
came from the 2-day AE.

---

## 8. Why healthy astronauts were flagged, and the fix

**Cause.** Two detectors, each tuned so 1% of healthy days cross its line, checked every day for 19 days:
roughly 18% of healthy astronauts get at least one false flag by chance. Not noise in a seed; a property of
the alarm rule.

**Study** (3 seeds; 2-day AE + EWMA; healthy flagged / detection):

| Alarm line | AE needs 2 days in a row | Healthy flagged | Sleep debt | Deconditioning | Solar |
| --- | --- | --- | --- | --- | --- |
| 99% | no | 18% | 99% | 93% | 97% |
| 99% | yes | 10% | 99% | 89% | 96% |
| **99.5%** | **yes** | **5%** | 91% | 82% | 88% |
| 99.9% | yes | 2% | 56% | 60% | 57% |

300 instead of 60 validation astronauts narrowed the EWMA line (40.6–47.4 vs 31.6–47.9 at 99%).

**Decision.** 99.5% lines, autoencoder alarm confirmed on 2 days in a row, 300 validation astronauts. The
strictest line was rejected: it would miss about 40% of real cases.

**How "2 days in a row" works.** The autoencoder scores two overlapping pairs: (day before yesterday +
yesterday) and (yesterday + today), and alarms only if both are over the line. Yesterday is in both pairs,
so an extreme single day still alarms (that's how the solar event is still caught, a day late); what's
filtered out is borderline noise that pushes only one pair over. Implemented as `confirmed()` in
`model/dataset.py`, used by both training and the service.

**Result (3 seeds):** healthy flagged 7% (6–8), 0.2% of days; sleep debt 97% (EWMA 97%, AE 36%);
deconditioning 86% (EWMA 84%, AE 54%); solar 91% (AE 91%, EWMA 16%), now flagged on day 1 instead of day 0;
CO₂ creep 14%; immune 6%; sensor loss 6%. EWMA lines 49.0 / 52.1 / 49.3.

---

## 9. Removing the 7- and 14-day models; contract and service changes

- `WINDOWS = (2,)` in `model/dataset.py`; only `artifacts/model_2d.pt` and `artifacts/ewma.json` remain.
- Harmful directions moved from code into `contract/signals.yaml` (`harmful: high|low|both` on every
  model input); `model/ewma.py` reads them; a test fails if any model input lacks one.
- `/score` (team agreed):
  - needs 3 to 14 days (3 = one confirmed 2-day pair);
  - returns `score` (higher of the two detectors), `anomalous`, `detector` (`2d` or `ewma`, replacing
    `window_days`), `scores` (both), `contributions` (each signal's share of the top detector, sums to 1),
    `drift` (each signal's smoothed harmful deviation, signed), `label`;
  - EWMA is required, not optional.
- `tests/test_service.py`: the 2-day score equals the lower of the two pairs; harmless drift gives 0; bad
  input (too few days, unknown signal) is rejected.
- Live check on the trained models over HTTP: healthy 0.26 (not flagged); solar day after 1.28 (flagged,
  2-day AE, 91% from dose); sleep debt 8 days in 0.93 (just under; that astronaut is one of the later ones),
  with `drift` showing sleep, HRV and mood low and lapses high.

**Why the maximum of the two detectors.** Both are on the same scale (> 1 = past their 99.5% line), so the
maximum means "alarm if either alarms". An average would let a quiet detector hide a loud one: solar 1.28
and 0.14 average to 0.71, a miss. Cost: their false alarms add up (2% + 6% → 7% at that stage).

---

## 10. Clarifications that shaped later steps

- **Stricter line vs more data.** The first changes *which* percentile is the line; the second changes how
  accurately it's measured (60 astronauts ≈ 2,800 healthy days, so the top 0.5% is 14 days; 300 ≈ 70).
- **Shape of the output.** One request = one astronaut, one day. `score` is one number ≥ 0 (0 = baseline,
  1 = alarm line, no upper limit; not a probability).
- **Limits of `drift`.** No fixed limit: it's a weighted average of the daily z-scores (weights sum to
  0.96 over 14 days), so it can't exceed 0.96 × the most extreme day, but z-scores weren't capped. Signs are
  fixed by the harmful direction.
- **A CO₂ problem surfaced here.** The normal size of each signal's smoothed value on healthy days was about
  0.4–0.9 spreads for most signals, 1.45 for exercise, and **15.25 for cabin CO₂**. CO₂ drifts slowly (day-
  to-day persistence 0.87), so 14 baseline days see a narrow slice of its range; its baseline spread came
  out far too small and every later day looked enormous. Not a safety problem (absolute CO₂ rules still
  apply) but the model contributed almost nothing on CO₂ and `drift` showed meaningless numbers.
- **Spread** = how much a signal normally varies day to day around its average (standard deviation).
- **An extreme baseline day** inflates the spread (example: 13 nights ≈ 6.5 h with spread 1 h plus one 2 h
  night → spread ≈ 1.6 h), shrinking every later deviation by about 40% for the whole mission.
- **A narrow baseline** is the opposite: 14 unusually steady days give a too-small spread and repeated false
  alarms.

---

## 11. Untracked scenarios: the sweep and the research-doc patterns

**Problem.** Only 7 hand-written scenarios were measured; a change could get worse at anything else unseen.

**Added** (`model/eval_scenarios.py`, evaluation only, run by every `model.train`):

- **Single-signal sweep, 60 scenarios:** each of the 10 inputs drifting alone in its harmful direction (BP
  up), by 1, 2 or 3 times its population day-to-day spread (`sim_sd`), fast (3-day ramp) or slow (21-day
  ramp); 100 astronauts each.
- **Research-doc patterns, 6 scenarios** (doc section 7 and 4.4), model-visible parts only, sizes at the
  doc's amber thresholds (proposed, not published effect sizes), 7-day ramp:

| Pattern | Model-visible part |
| --- | --- |
| CO₂ performance impairment | CO₂ +0.8 mmHg, lapses +20% (headache not an input) |
| Stress-associated autonomic | sleep −1.5 h (to ~5 h), RMSSD −20% (cortisol, NK not inputs) |
| Autonomic stress / illness (4.4) | resting HR +10 bpm, RMSSD −20%, sleep efficiency −10 points |
| Vascular | systolic +15 mmHg, dose +50% (PWV not an input) |
| Radiation + immune | dose +50% (lymphocytes, NK are labs) |
| Bone resorption | exercise completion 80% (BMD, urinary calcium not inputs) |

Not representable at all (no model input): viral reactivation (labs; the `immune` scenario covers it),
oral mucosal defence, energy deficit.

---

## 12. Fixing the baseline scaling

### 12.1 Choosing the blending weight k on real data

**Blending.** spread² = ((n − 1) × own² + k × population²) / (n − 1 + k), with n = 14 baseline days and the
population spread = `sim_sd` from `contract/signals.yaml` (moved to the astronaut's level for multiplicative
signals: × own level / typical level for `log` signals, by the shortfall below the cap for `log_from`
signals). k = how many days' worth of trust the population value gets. Only the spread is blended; the
centre stays fully personal.

**Why not choose k in the simulator.** The simulator gives every astronaut the same day-to-day spread, so it
would always favour "use the population value" (k → ∞). Real data shows how much individuals actually differ.

**Method.** For each real person (BIDSleep: first half of their nights as baseline; ISS CO₂: first 14 days
of each mission), blend their baseline spread with the population spread for a range of k, and compare with
the spread they actually showed afterwards (measured from the baseline mean, as live scaling does). Error =
mean squared log ratio.

**Simulator check first (CO₂).** Baseline spread median 0.33 vs later typical deviation 0.63: later days
are 1.9× bigger than the baseline suggests (95th percentile 3.9×). That's the CO₂ problem in section 10.

**Results (error, lower is better):**

| k | 0 (own only) | 2 | 4 | 5 | 6 | 7 | 8 | 10 | 14 | 28 | 140 | population only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pooled (4 signals) | 1.614 | 0.424 | 0.395 | 0.392 | **0.391** | 0.392 | 0.393 | 0.396 | 0.403 | 0.420 | 0.446 | 0.456 |

Per signal, best k: resting HR 2–3, sleep duration 10, sleep efficiency 3–4, CO₂ 7. All four agree that
k = 0 is about 4× worse, and that population-only is also worse. **k = 6**; 5–8 are within 0.002.

### 12.2 Step-by-step comparison of the fixes

Each fix applied in turn, retrained over 3 seeds, scored on all 73 scenarios (7 original + 6 patterns + 60
sweep). Rule: keep a fix only if no scenario gets worse by more than run-to-run variation (about 4 points).

| Step | Healthy flagged | Sleep debt | Deconditioning | Solar | CO₂ creep | Sweep avg | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Before (mean/SD, no cap, λ 0.2) | 7% | 97% | 86% | 91% | 14% | 23% | — |
| Cap deviations at ±6 | 5% | 100% | 97% | **30%** | 25% | 35% | Cap kept, at a higher value |
| + blend, k = 6 | 4% | 100% | 97% | 86% | 28% | 37% | Kept |
| + median and MAD | 7% | 100% | 98%, 4–5 days later | 57% | 36% | 40% | Rejected |
| mean + blend, λ 0.1 | 3% | 100% | 98%, 1 day later | 86% | 27% | 37% | Rejected |
| median + blend, λ 0.1 | 5% | 100% | 99%, later | 56% | 34% | 39% | Rejected |

Patterns over the same steps: autonomic illness 79 → 93 → 96 → 97 → 98%; bone resorption 64 → 85 → 84 → 75
→ 86%; stress-autonomic 23 → 51 → 54 → 52 → 56%; vascular and radiation 100% throughout; CO₂ performance
8–12% throughout.

**Why the cap helped so much.** A few huge deviations on healthy days (heavy-tailed lapses and exercise,
CO₂'s narrow baselines) set the 99.5% alarm lines. Capping them lowers the lines, so real drift stands out.
**Why it hurt solar.** The one-day dose spike is about 9 spreads; ±6 flattened it below the 2-day model's
line.

**Why median scaling lost.** A median-based spread (MAD) from 14 days is a noisier estimate than the
standard deviation, so spreads came out less accurate, and blending had already handled most of the
extreme-day problem. Solar fell to 57% and deconditioning was flagged 4–5 days later.

**Why the slower EWMA lost.** Its gains were within run-to-run noise, and deconditioning was flagged a day
later on median: longer memory reacts more slowly.

### 12.3 Choosing the cap value

With blending, k = 6, λ 0.2:

| Cap | Healthy flagged | Deconditioning | Solar | CO₂ creep | Stress-autonomic | Sweep avg |
| --- | --- | --- | --- | --- | --- | --- |
| ±6 | 4% | 97% | 86% | 28% | 54% | 37% |
| **±8** | **4%** | **96%** | **100%** | **25%** | **48%** | **34%** |
| ±10 | 6% | 95% | 99% | 21% | 42% | 32% |
| none | 6% | 91% | 99% | 15% | 27% | 26% |

**±8 chosen:** the only setting where every tracked scenario is equal or better than before the fixes.
±6 loses 14 points on solar; ±8 gives up 6 points on one pattern and 3 on the sweep average against ±6.

**CO₂ fixed.** Normal size of CO₂'s smoothed value: 6.3 spreads before (15.25 in the earlier artifact with a
different validation set), 1.3 after blending, in line with the other signals.

---

## 13. Final state

**Design.** Baseline: mean of 14 days; spread blended with the population, k = 6; deviations capped ±8.
Detectors: 2-day autoencoder (alarm confirmed on 2 days in a row) and one-sided EWMA (λ 0.2). Alarm lines at
99.5% of 300 validation astronauts. `/score` reports the higher.

**Results (3 seeds):**

| Scenario | Flagged | Median days to flag |
| --- | --- | --- |
| Healthy | 4% (4–5); under 0.1% of days | — |
| Sleep debt | 100% | 5 |
| Deconditioning | 96% (96–97) | 4 |
| Solar event | 100% (99–100) | 1 |
| CO₂ creep | 25% (22–28) | 13 |
| Immune | 5% (= normal) | — |
| Sensor loss | 4% (= normal) | — |
| Pattern: radiation + immune | 100% | 4 |
| Pattern: vascular | 100% | 4 |
| Pattern: autonomic illness | 94% | 7 |
| Pattern: bone resorption | 82% | 4 |
| Pattern: stress-autonomic | 48% (42–52) | 12 |
| Pattern: CO₂ performance | 10% (= normal) | — |

Single-signal sweep (combined detector, % flagged):

| Signal | 1 fast | 1 slow | 2 fast | 2 slow | 3 fast | 3 slow |
| --- | --- | --- | --- | --- | --- | --- |
| Resting HR | 9 | 4 | 34 | 11 | 78 | 31 |
| HRV (RMSSD) | 9 | 4 | 34 | 11 | 67 | 29 |
| Systolic BP | 7 | 3 | 27 | 9 | 56 | 23 |
| Sleep duration | 19 | 7 | 78 | 30 | 100 | 75 |
| Sleep efficiency | 46 | 23 | 72 | 54 | 85 | 70 |
| Reaction lapses | 23 | 12 | 45 | 25 | 62 | 41 |
| Mood | 7 | 4 | 33 | 10 | 70 | 26 |
| Cabin CO₂ | 5 | 4 | 9 | 5 | 18 | 7 |
| Exercise | 35 | 24 | 54 | 42 | 66 | 54 |
| Dose | 12 | 6 | 63 | 16 | 98 | 55 |

Averages: 1 spread 13%, 2 spreads 33%, 3 spreads 56%; overall 34%.

Alarm lines across seeds: autoencoder 1.75–2.03; EWMA 32.0–40.0 (scaling changed, so not comparable with
earlier values; the EWMA line still varies about ±10% between seeds).

**Files.** `model/dataset.py` (scaling, windows, `confirmed()`), `model/ewma.py`, `model/autoencoder.py`,
`model/train.py` (training + full evaluation), `model/service.py`, `model/eval_scenarios.py`;
`contract/signals.yaml` (`harmful`, and `sim_sd` now also feeds live scaling). Tests: 34 passing, including
`tests/test_ewma.py`, `tests/test_service.py`, `tests/test_scaling.py`.

---

## 14. Is the single-signal result good enough?

**Short answer: for the model, yes; for the system, it depends on the threshold rules, and two of them have
no numbers.**

- **The model is built for combined drift.** Its alarm line covers the sum of 10 signals' normal noise, so
  one signal must move a lot on its own to cross it. A 1-spread shift is inside ordinary day-to-day
  variation; flagging it reliably would mean flagging healthy days too.
- **Making it more sensitive to single signals** would mean a per-signal alarm inside the model, each with
  its own false-alarm budget. That is what the threshold rules already are, but with cited thresholds
  (NFR-13). Duplicating them in the model would add false alarms without adding coverage.
- **The rules catch most single-signal drift earlier.** The research doc's amber thresholds, in population
  spreads from the typical level: reaction lapses +0.28, CO₂ +0.52, HRV 0.65, sleep efficiency 1.39,
  exercise 2.0, resting HR 2.6. Most sit at or below the sweep's smaller sizes.
- **Real gaps, where neither catches a single-signal drift:**
  - **Systolic BP:** the doc's amber is "persistent deviation" with no number, and the model catches a
    2-spread rise only 27% of the time.
  - **Mood:** "persistent deterioration", no number; model 33% at 2 spreads.
  - **Dose:** amber is "approaching mission budget"; the cumulative-dose rule covers long-term exposure.
  Recommendation: give BP and mood amber rules numeric, cited (or tagged proposed) thresholds.
- **One threshold is set too tight for astronauts.** Sleep duration amber is "under 7 h", but the typical
  in-flight level used by the simulator (Jones 2022) is 6.5 h: the rule would mark the average astronaut
  amber every night. The rule owner should make it relative to baseline or lower it.
- **Measurement caveat.** Slow sweep scenarios ramp over 21 days but are observed for 19, so they never
  reach full size; their low numbers partly reflect that. Running the sweep for longer would measure them
  fairly.
- **CO₂ alone** is nearly invisible to the model (18% at 3 spreads) because cabin CO₂ wanders a lot by
  nature; the absolute NASA limits in the rules are the right tool.

---

## 15. Open items and limits

**Open.**

- Core scaling: written on local branch `core-scaling` (section 16); waits for the backend owner's review.
- Missing signals are still filled as "at baseline"; waits for the core service's handling of stale data.
- "Score rises before any band changes" (plan 6.2) is untested; needs the rule engine.
- BP and mood amber rules need numbers; sleep amber needs revisiting (section 14).
- Subject-held-out validation of the simulator (section 3).

**Limits.**

- All detection numbers are on simulated astronauts with only two cross-signal links; expect lower
  performance on real crews.
- Pattern scenario sizes are the research doc's proposed amber thresholds, not measured effect sizes.
- k = 6 was fitted on 43 Earth adults (few nights each) and 10 ISS missions.
- Output is a research concept, not validated on crew data (NFR-10).

---

## 16. Hardening, measurement fixes and the core scaling change

Four improvements on the model side, then a full rerun (3 seeds, 1,000 validation astronauts, 74 scenarios).

**1. Bad input at `/score`.** Found by probing the running service:

- A `NaN` value returned `score: null, anomalous: false`: a sensor glitch read as a healthy astronaut.
- A value of 1,000,000 was not capped in the service (only the core's scaling capped).

Fix: values must be finite (pydantic `allow_inf_nan=False`) and are clipped at ±8, as in training. The
first test then exposed a second bug: FastAPI's default 422 reply echoes the rejected value, and `NaN` can't
be written as JSON, so the reply itself crashed with a 500 (which the core would read as "model down" and
stop calling for 10 s). A custom handler now returns a 422 without the raw value. Tests: NaN, +inf and
−inf give 422; 1,000,000 scores exactly like 8.

**2. Model version.** `/health` and every `/score` reply carry `model_version`, the first 12 hex characters
of a SHA-256 over the trained files, so any stored score can be traced to the model that produced it.

**3. Alarm-line stability: 1,000 validation astronauts (was 300).** Detection ranges across seeds
tightened (healthy flagged 4–4% instead of 4–5%; stress-autonomic pattern 46–50% instead of 42–52%;
deconditioning 95–96%). The EWMA line's *number* still differs by seed (32.7, 38.4, 37.6). That turned out
not to matter: the per-signal scale is fitted per seed too, so the line and the scores move together and
detection stays the same. My earlier reading ("too few validation astronauts") was only part of the story.

**4. Slow sweep under-measured: sweep runs now 60 days**, plus a 60-day healthy reference
(`sweep_normal`): over the same 39 days of watching, 10% of healthy astronauts get a false flag, so sweep
numbers near 10% mean "not detected".

| Size | Fast, 40-day runs | Fast, 60-day runs | Slow, 40-day runs | Slow, 60-day runs |
| --- | --- | --- | --- | --- |
| 1 spread | 17% | 25% | 9% | 22% |
| 2 spreads | 45% | 56% | 21% | 51% |
| 3 spreads | 70% | 80% | 41% | 77% |

Slow drifts now score close to fast ones (resting HR at 3 spreads: slow 91% vs fast 97%; it read 31% with
40-day runs). Part of every rise is the longer watch (healthy 4% → 10%). Per signal at 3 spreads, fast:
sleep duration 100%, dose 98%, resting HR 97%, sleep efficiency 95%, mood 84%, HRV 81%, exercise 78%,
systolic BP 75%, lapses 69%, CO₂ 27%. At 1 spread most signals sit at 11–15%, i.e. at the healthy level;
sleep efficiency (53%), exercise (49%), lapses (31%) and sleep duration (31%) stand out. Section 14's
conclusion holds: single-signal drift is the rules' job, BP and mood need numeric rules, CO₂ belongs to
the absolute limits. Details of the measurement: 16.4.

### 16.4 The longer sweep, in detail

**What the sweep is.** 60 evaluation-only scenarios (`model/eval_scenarios.py`, run by every
`model.train`): each of the 10 model inputs drifts alone in its harmful direction (BP: up) by 1, 2 or 3
times its population day-to-day spread (`sim_sd`), either fast (3-day linear ramp) or slow (21-day ramp),
plus `sweep_normal`, a healthy astronaut run for the same length. Onset is day 21, as for the demo
scenarios (14 baseline days + 7). 100 astronauts per scenario (half of the 200 used for the demo
scenarios and patterns). "Flagged" means the share whose combined score crossed 1 at least once after
onset, i.e. exactly what `/score` would have reported.

**Why the earlier 40-day runs under-measured slow drifts.** A 40-day run watches 19 days after onset
(days 21–39). A fast 3-day ramp is at full size from day 23 and holds it for 17 days: fair. A slow
21-day ramp only reaches full size on day 41, after the run has ended; on its last day it is at 19/21 ≈
90% of the intended size, and the EWMA (memory ≈ 5 days) plus the 2-day confirmation lag for the
autoencoder have not caught up with even that. The slow column was therefore measuring "a drift still
ramping up", not "a sustained drift of m spreads", so fast and slow were not comparable. The old resting
HR result (3 spreads, slow: 31%) looked like the model could not see slow drift; most of that gap was
the run length, not the detector.

**The fix.** `SWEEP_DAYS = 60`: a slow ramp reaches full size on day 41 and holds it for ~19 days; a fast
ramp holds it for ~37. `tests/test_slow_sweep_runs_long_enough_to_reach_full_size` requires every sweep
scenario to keep its largest ramp at full size for at least 14 days, so a later edit to a ramp length
cannot silently bring the problem back.

**The longer watch also collects more false alarms — hence the healthy reference.** Watching 39 days
instead of 19 gives both detectors more chances to cross their lines on ordinary noise. The healthy
share rose from 4% (19 days) to 10% (39 days). Every run therefore prints `sweep_normal` next to the
sweep, and sweep numbers are read against that 10%, not against the 4% of the demo scenarios: a sweep
number near 10% means "not detected", and a few points between seeds are noise at 100 astronauts.

**What changed (combined detector, % flagged; the table in point 4 has the numbers):**

- **Fast rows rise 8–11 points**, in line with the healthy rise (4% → 10%): the extra days add
  false-alarm chances, not detection.
- **Slow rows rise 13–36 points**, because the ramp now completes and is held; that is the real
  correction. Slow drifts now score close to fast ones: 77% vs 80% overall at 3 spreads, resting HR 91%
  vs 97%.
- **At 1 spread** slow 22% and fast 25% are barely above the 10% healthy level: a single small drift is
  still mostly invisible, which is by design (the model is built for several signals drifting together;
  the threshold rules own single signals, section 14).
- **At 2 spreads** slow 51% vs fast 56%, and at 3 spreads 77% vs 80%: onset speed matters little once the
  drift is large enough.

**Per signal at 3 spreads (fast, 60 days):** sleep duration 100%, dose 98%, resting HR 97%, sleep
efficiency 95%, mood 84%, HRV 81%, exercise 78%, systolic BP 75%, lapses 69%, CO₂ 27%. CO₂ remains the
exception (cabin CO₂ wanders naturally; the absolute NASA limits are the right tool). At 1 spread most
signals sit at 11–15%, i.e. at the healthy level; sleep efficiency (53%), exercise (49%), lapses (31%)
and sleep duration (31%) stand out because one population spread is already a large absolute change for
them (≈4.9 points off 92% efficiency, 4 points off 98% exercise, 5.4 points off 7.5% lapses, ≈1 h off
6.5 h sleep), and the baseline blend reacts to that size.

**Why not longer.** The sweep is the expensive part of a training run: 61 scenarios × 100 astronauts ×
60 days, for every seed. The EWMA's memory is about 5 days and an autoencoder alarm needs 2 days in a
row, so 39 days after onset already show a sustained drift many times over; more days would mostly add
healthy exposure and runtime. The sweep still reports only "ever flagged": `evaluate()` also computes
the median day of the first flag and the pre-onset false-alarm rate for each sweep scenario, but
`summarise()` does not print them, so latency by size is not reported. Printing those per sweep scenario
is a possible follow-up.

**Final results (3 seeds, mean and range):**

| Scenario | Flagged | Median days to flag |
| --- | --- | --- |
| Healthy | 4% (4–4); under 0.1% of days | — |
| Sleep debt | 100% | 5 |
| Deconditioning | 96% (95–96) | 4 |
| Solar event | 99% (99–100) | 1 |
| CO₂ creep | 23% (20–24) | 13 |
| Immune / sensor loss | 5% / 4% (= healthy) | — |
| Pattern: radiation + immune, vascular | 100% | 4 |
| Pattern: autonomic illness | 94% | 7 |
| Pattern: bone resorption | 81% | 4 |
| Pattern: stress-autonomic | 47% | 12 |
| Pattern: CO₂ performance | 9% (= healthy) | — |

All within run-to-run variation of section 13: the hardening changed no detection.

**Live check over HTTP** (trained model `a260b84413cd`): `/health` ok with version; a NaN window → 422; a
sleep-debt-like window (sleep 2.4 spreads low, lapses 3 high for a week) → 0.997 from EWMA, 78% from sleep.

**Core scaling integration.** The backend's health path still persists its original personal means and
sample SDs for charts and rules. The model path now reads raw values from the first 14 calendar days,
uses `model.dataset.baseline_stats` (shared blend `k = 6`, `typical_sd`, and cap ±8), and sends the
same capped z-scores used during training. Missing, constant, and partial signals remain baseline-safe;
old baseline rows need no migration. `tests/test_core.py` covers parity with `model.dataset.normalise`,
the `detector`/`model_version` response contract, cap behavior, and insufficient-day readiness.

The root Compose file stages the separate `aura-bio/model:local` image on port `8001`, with artifacts
baked into the image rather than mounted from the host. The core continues to treat a model 422 or
unreachable service as "model down" for 10 seconds while rule alerts continue.

**For the backend owner, not changed:** baselines use every reading of the first 14 days, which matches
training only while each signal has one reading per day (the generator); a sensor publishing more often
needs a daily value first. The model port is published (`8001:8001`); only the core needs it. A 422 from
the model is treated as "model down" for 10 s.
