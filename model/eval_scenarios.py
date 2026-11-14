"""Evaluation-only scenarios (not demo scenarios), so a model change can't quietly get worse at something untracked.

SWEEP: every model input drifting alone in its harmful direction (BP: up), by 1, 2 or 3 times its population
day-to-day spread (signals.yaml sim_sd), fast (3-day ramp) or slow (21-day ramp). Covers "any one signal goes bad".
Sweep runs last SWEEP_DAYS: onset is day 21, so a slow 21-day ramp reaches full size on day 41 and holds it for
~19 days (a fast ramp holds it for ~37). The earlier 40-day runs ended at day 39, before a slow ramp completed:
they measured a drift still in progress (90% of size on the last day), which is why slow numbers read low.
`sweep_normal` is the healthy reference over the same length: a longer watch also gives more chances for a false
flag (4% over 19 days, 10% over 39), so sweep numbers are read against it, not against the demo-scenario healthy
figure. Details and the 40-vs-60-day table: docs/model-decisions.md 16.4.

PATTERNS: the research doc's cross-system patterns (Nasa pre hackathon section 7 and 4.4), using only the parts the
model sees. Sizes are the research doc's AMBER thresholds (proposed, not published effect sizes); 7-day ramp.
Not representable (no model input): viral reactivation (labs; see the `immune` scenario), oral mucosal defence
(sIgA, oral exam, microbiome), energy deficit (calories, body mass, strength).
"""
from __future__ import annotations

from contract.schema import load_signals
from generator.sim import Effect, Scenario

_UP = {"high": 1, "both": 1, "low": -1}
SWEEP_DAYS = 60

SWEEP: dict[str, Scenario] = {
    f"sweep_{s['name']}_{m}sd_{speed}": Scenario(
        f"sweep_{s['name']}_{m}sd_{speed}",
        days=SWEEP_DAYS, effects={s["name"]: Effect("add", _UP[s["harmful"]] * m * s["sim_sd"], ramp)})
    for s in load_signals() if s.get("model")
    for m in (1, 2, 3)
    for speed, ramp in (("fast", 3), ("slow", 21))
} | {"sweep_normal": Scenario("sweep_normal", days=SWEEP_DAYS)}

PATTERNS: dict[str, Scenario] = {
    # CO2 + headache + slower reactions (7): CO2 into amber/red (+0.8 mmHg from ~2.2), lapses +20% (amber)
    "pattern_co2_performance": Scenario("pattern_co2_performance", effects={
        "cabin_co2_mmhg": Effect("add", 0.8, 7), "reaction_lapses_pct": Effect("mul", 0.2, 7)}),
    # sleep deficiency + reduced HRV (+ cortisol, NK: not inputs) (7): sleep 6.5 -> 5 h (amber), RMSSD -20% (amber)
    "pattern_stress_autonomic": Scenario("pattern_stress_autonomic", effects={
        "sleep_duration_h": Effect("add", -1.5, 7), "rmssd_ms": Effect("mul", -0.2, 7)}),
    # raised resting HR + reduced HRV + poor sleep (4.4): HR +10 bpm, RMSSD -20%, efficiency -10 points (all amber)
    "pattern_autonomic_illness": Scenario("pattern_autonomic_illness", effects={
        "resting_hr_bpm": Effect("add", 10, 7), "rmssd_ms": Effect("mul", -0.2, 7),
        "sleep_efficiency_pct": Effect("add", -10, 7)}),
    # abnormal BP + raised radiation (+ PWV: not an input) (7): systolic +15 mmHg (persistent deviation), dose +50%
    "pattern_vascular": Scenario("pattern_vascular", effects={
        "bp_systolic_mmhg": Effect("add", 15, 7), "dose_mgy": Effect("mul", 0.5, 7)}),
    # raised dose (+ lymphocytes, NK: labs, not inputs) (7): dose +50%, sustained
    "pattern_radiation_immune": Scenario("pattern_radiation_immune", effects={"dose_mgy": Effect("mul", 0.5, 7)}),
    # reduced exercise (+ BMD, urinary calcium: not inputs) (7): exercise completion 80% (amber 75-89%)
    "pattern_bone_resorption": Scenario("pattern_bone_resorption", effects={
        "exercise_completion_pct": Effect("set", 80, 7)}),
}
