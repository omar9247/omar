"""Simulated crew data: per-astronaut baselines + AR(1) day-to-day noise + scenario effects.

Everything here is SIMULATED (provenance="simulated"); it is anchored to the research-doc findings,
not to real crew vitals (none are open). See data/SOURCES.md for the real datasets to anchor on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from contract.schema import load_presets, load_signals

BASELINE_DAYS = 14


@dataclass
class Effect:
    """Ramp a signal from onset over ramp_days. mode 'add': +value at full effect; 'mul': *(1+value);
    'set': move toward the absolute value. Default ramp is linear, then flat after ramp_days.
    With power set, the ramp is (days since onset / ramp_days) ** power and keeps growing past
    ramp_days (Van Dongen et al. 2003 fit y = beta * t^theta)."""
    mode: str
    value: float
    ramp_days: int = 5
    power: float | None = None
    duration_days: int | None = None  # effect stops after this many days (e.g. a one-day event)


@dataclass
class Scenario:
    name: str
    onset_day: int = BASELINE_DAYS + 7
    days: int = 40  # default run length for this scenario
    response_sd: float = 0.0  # spread of each astronaut's response size (1 = average); 0 = identical
    effects: dict[str, Effect] = field(default_factory=dict)
    drop_signals: list[str] = field(default_factory=list)  # stop publishing (sensor loss)


SCENARIOS: dict[str, Scenario] = {
    "normal": Scenario("normal"),
    "co2_creep": Scenario("co2_creep", effects={
        "cabin_co2_mmhg": Effect("add", 1.2, 8),  # plan 6.2 size (2.0->3.2), from the cabin's own level
        "reaction_lapses_pct": Effect("mul", 0.25, 8),
        "mood_score": Effect("add", -0.8, 8),
    }),
    "sleep_debt": Scenario("sleep_debt", effects={
        "sleep_duration_h": Effect("add", -2.4, 5),  # same drop as plan 6.2 (7.2->4.8 h), from own baseline
        "sleep_efficiency_pct": Effect("add", -8, 5),
        "rmssd_ms": Effect("mul", -0.25, 5),
        # Van Dongen et al. 2003 (SLEEP 26:117), 4 h time-in-bed group (~3.8 h sleep; our scenario
        # sleeps ~4.1 h = 6.5 - 2.4): PVT lapses +~14 per 10-min test at day 14 (Fig 1A) ~ +14
        # percentage points of trials, curve t^0.78, extrapolated past day 14. The 3-min PVT-B at a
        # 355 ms threshold tracks the 10-min PVT (Basner et al. 2011), so the size carries over.
        # Mood has no effect of its own here: it follows last night's sleep (signals.yaml `follows`, Jones
        # et al. 2022 Table 1), which gives about -0.4 at ~4.1 h vs the astronaut's usual ~6.5 h.
        "reaction_lapses_pct": Effect("add", 14, 14, power=0.78),
    }),
    # Exercise lapses -> bed-rest-like deconditioning. Sizes are the plan's PROPOSAL (not published):
    # on the ISS, resting HR stays unchanged when crew exercise (Hughson et al.); bed rest without
    # exercise raises it, but no rate was found. HR rise spread over 21 days (builds over weeks).
    "deconditioning": Scenario("deconditioning", effects={
        "resting_hr_bpm": Effect("add", 12, 21),
        "exercise_completion_pct": Effect("set", 70, 7),
        "rmssd_ms": Effect("mul", -0.1, 7),
    }),
    "sensor_loss": Scenario("sensor_loss", drop_signals=["resting_hr_bpm", "rmssd_ms"]),
    # Solar particle event, one day: the 10 Sep 2017 event added 0.146 mGy (Si) on the ISS (Berger et
    # al. 2018, DOSIS 3D), i.e. +51% of a normal 0.285 mGy ISS day. Applied as a percentage so it scales
    # to each astronaut and preset (for non-station presets that scaling is derived, not measured).
    "solar_event": Scenario("solar_event", effects={
        "dose_mgy": Effect("mul", 0.146 / 0.285, 1, duration_days=1),
    }),
    # Long-duration immune dysregulation, ramping in over 60 days (NK drop measured at flight day 90,
    # Bigley et al. 2019). Sizes: lymphocytes -27%, IL-6 +90% (Inspiration4 average, day after
    # landing); NK activity -50% (Bigley 2019). Shedding chance per weekly sample 3% -> 23%: healthy
    # controls 3% (Mehta et al. 2017); 23% of astronaut saliva samples EBV-positive (NASA, shuttle era).
    # Crew respond very differently: Inspiration4 per-crew changes spread ~78% of the average change
    # (lymphocytes -48/-34/-27/+2%, IL-6 +31/+59/+81/+190%), so each astronaut gets their own response size.
    "immune": Scenario("immune", days=90, response_sd=0.78, effects={
        "lymphocytes_per_ul": Effect("mul", -0.27, 60),
        "il6_pg_ml": Effect("mul", 0.90, 60),
        "nk_activity_pct": Effect("mul", -0.50, 60),
        "viral_pcr_positive": Effect("set", 0.23, 60),
    }),
}


def log_sigma(spread: float, level: float) -> float:
    """Log-scale sigma that gives a lognormal with this mean (level) and standard deviation (spread)."""
    return float(np.sqrt(np.log1p((spread / level) ** 2)))


def to_logit(x, s: dict):
    lo, hi = s["logit"]
    return np.log((x - lo) / (hi - x))


def from_logit(u, s: dict):
    lo, hi = s["logit"]
    return lo + (hi - lo) / (1 + np.exp(-u))


def logit_center(s: dict) -> float:
    """Logit-scale centre whose average, after person and day-to-day variation, equals sim_mean
    (squeezing toward the ends shifts the average, so the plain logit of sim_mean is slightly off)."""
    k = logit_slope(s)
    sig = k * np.hypot(s["person_sd"], s["sim_sd"])
    z, w = np.polynomial.hermite_e.hermegauss(40)
    w = w / w.sum()
    u = to_logit(s["sim_mean"], s)
    for _ in range(30):  # Newton steps on mean(u) = sim_mean
        x = from_logit(u + sig * z, s)
        lo, hi = s["logit"]
        f, df = (w * x).sum() - s["sim_mean"], (w * (x - lo) * (hi - x) / (hi - lo)).sum()
        u -= f / df
    return float(u)


def logit_slope(s: dict) -> float:
    """d logit / dx at the typical level: converts spreads in signal units to the logit scale."""
    lo, hi = s["logit"]
    m = s["sim_mean"]
    return (hi - lo) / ((m - lo) * (hi - m))


def make_profile(rng: np.random.Generator, preset: str = "station") -> dict[str, float]:
    """One astronaut's personal baseline means. Dose is scaled to the mission preset's level, keeping
    each astronaut's own offset (personal dosimeter), so crew differ independently of each other."""
    p = load_presets()[preset]
    prof = {}
    for s in load_signals():
        mean, spread = s["sim_mean"], s["person_sd"]
        if s["name"] == "dose_mgy":
            scale = p["dose_mgy_day"] / mean
            mean, spread = mean * scale, spread * scale
        if s.get("log"):  # multiplicative offset: never <= 0, keeps the stated average and spread
            sig = log_sigma(spread, s["sim_mean"])
            prof[s["name"]] = mean * np.exp(rng.normal(0, sig) - sig**2 / 2)
        elif "log_from" in s:  # multiplicative SHORTFALL below a cap: approaches it, never sits on it
            top, gap = s["log_from"], s["log_from"] - s["sim_mean"]
            sig = log_sigma(spread, gap)
            prof[s["name"]] = top - gap * np.exp(rng.normal(0, sig) - sig**2 / 2)
        elif "logit" in s:  # bounded both ends: varies on the logit scale, never sits on either end
            prof[s["name"]] = from_logit(logit_center(s) + rng.normal(0, spread * logit_slope(s)), s)
        else:
            prof[s["name"]] = mean + rng.normal(0, spread)
    return prof


def effect_ramp(scenario: Scenario, name: str, n_days: int) -> np.ndarray:
    """0 before onset, then the effect's ramp (0..1 linear, or a power curve). Zeros if no effect."""
    eff = scenario.effects.get(name)
    if not eff:
        return np.zeros(n_days)
    since = np.arange(n_days) - scenario.onset_day + 1        # 1 on the onset day
    t = np.clip(since, 0, None) / eff.ramp_days
    ramp = t ** eff.power if eff.power else np.clip(t, 0, 1)
    if eff.duration_days:
        ramp = np.where(since > eff.duration_days, 0.0, ramp)
    return ramp


def mul_base(value: float, response_sd: float) -> float:
    """Base b so that b ** response averages 1 + value over response ~ N(1, response_sd):
    E[b**R] = b * exp(response_sd**2 * ln(b)**2 / 2). Keeps the stated average change."""
    b = 1 + value
    for _ in range(50):
        b = (1 + value) / np.exp(response_sd**2 * np.log(b) ** 2 / 2)
    return b


def apply_effect(x: np.ndarray, mean: float, scenario: Scenario, name: str,
                 scale: float = 1.0) -> np.ndarray:
    """Add the scenario's effect for this signal to a daily series (simulated or replayed).
    scale = this astronaut's response size (1 = the average effect)."""
    eff = scenario.effects.get(name)
    if not eff:
        return x
    ramp = effect_ramp(scenario, name, len(x)) * scale
    if eff.mode == "add":
        return x + ramp * eff.value
    if eff.mode == "mul":
        if scenario.response_sd:  # response size varies: log scale, so a large response never crosses 0
            return x * mul_base(eff.value, scenario.response_sd) ** ramp
        return x * (1 + ramp * eff.value)
    return x + ramp * (eff.value - mean)  # "set"


def follow_change(f: dict, v):
    """`follows` change for value(s) v: the published bin values, as steps (bins split at f["edges"])."""
    return np.asarray(f["change"])[np.searchsorted(f["edges"], v)]


def usual_change(f: dict, usual: float, sd: float) -> float:
    """Average change over this astronaut's normal day-to-day range, so the link moves values around
    the astronaut's own level without shifting it (short nights hurt more than long nights help)."""
    z, w = np.polynomial.hermite_e.hermegauss(40)
    return float((w / w.sum() * follow_change(f, usual + sd * z)).sum())


def simulate(profile: dict[str, float], n_days: int, rng: np.random.Generator,
             scenario: Scenario | None = None) -> pd.DataFrame:
    """Daily values, one row per day, one column per signal (NaN where a sensor dropped out)."""
    scenario = scenario or SCENARIOS["normal"]
    # this astronaut's response size, shared by all signals in the scenario
    scale = 1 + rng.normal(0, scenario.response_sd) if scenario.response_sd else 1.0
    cols, shocks = {}, {}
    by_name = {s["name"]: s for s in load_signals()}
    for s in load_signals():
        name, mean, sd, ar = s["name"], profile[s["name"]], s["sim_sd"], s.get("ar", 0.4)
        z = rng.standard_normal(n_days + 1)  # this signal's daily shocks (last one starts the series)
        for other, r in s.get("corr", {}).items():  # same-day link to an earlier signal
            z = r * shocks[other] + np.sqrt(1 - r**2) * z
        shocks[name] = z
        eps = sd * np.sqrt(1 - ar**2) * z[:n_days]  # stationary AR(1) with std sd
        noise = np.zeros(n_days)
        noise[0] = sd * z[n_days]
        for t in range(1, n_days):
            noise[t] = ar * noise[t - 1] + eps[t]
        if "p" in s:  # binary yes/no signal (e.g. viral shedding): effects change the chance, not the 0/1
            p = np.clip(apply_effect(np.full(n_days, s["p"]), s["p"], scenario, name, scale), 0, 1)
            x = (rng.random(n_days) < p).astype(float)
        else:
            # log: true -> variation is multiplicative with a fixed relative size (sim_sd / sim_mean),
            # so it scales with each astronaut's or preset's level and never goes negative
            if s.get("log"):  # -sig^2/2 keeps the average at `mean` (exp of a normal is biased up)
                sig = log_sigma(sd, s["sim_mean"])
                x = mean * np.exp(sig * noise / sd - sig**2 / 2)
            elif "log_from" in s:  # shortfall below the cap varies multiplicatively
                top = s["log_from"]
                sig = log_sigma(sd, top - s["sim_mean"])
                x = top - (top - mean) * np.exp(-sig * noise / sd - sig**2 / 2)  # minus: positive noise = higher value
            elif "logit" in s:
                x = from_logit(to_logit(mean, s) + noise * logit_slope(s), s)
            else:
                x = mean + noise
            for other, f in s.get("follows", {}).items():  # day-to-day dependence on an earlier signal
                x = x + follow_change(f, cols[other]) - usual_change(f, profile[other], by_name[other]["sim_sd"])
            x = apply_effect(x, mean, scenario, name, scale)
        if "min" in s or "max" in s:  # hard limits of the scale (e.g. efficiency <= 100%)
            x = np.clip(x, s.get("min", -np.inf), s.get("max", np.inf))
        if "interval_days" in s:  # measured only on sample days (e.g. weekly blood test)
            x = np.where(np.arange(n_days) % s["interval_days"] == 0, x, np.nan)
        if name in scenario.drop_signals:
            x[scenario.onset_day:] = np.nan
        cols[name] = x
    return pd.DataFrame(cols)


def to_readings(crew_id: str, df: pd.DataFrame, start: str = "2026-11-14T10:00:00+00:00",
                provenance: str | pd.DataFrame = "simulated") -> list[dict]:
    """Daily frame -> contract messages (JSON-ready), skipping NaN (dropped sensors).
    provenance: one label for everything, or a frame shaped like df with a label per day and signal."""
    by_name = {s["name"]: s for s in load_signals()}
    ts0 = pd.Timestamp(start)
    out = []
    for day, row in df.iterrows():
        ts = (ts0 + pd.Timedelta(days=int(day))).isoformat().replace("+00:00", "Z")
        for name, v in row.items():
            if pd.notna(v):
                out.append({"crew_id": crew_id, "ts": ts, "signal": name, "value": round(float(v), 3),
                            "source": by_name[name]["source"],
                            "provenance": provenance if isinstance(provenance, str) else provenance.at[day, name]})
    return out
