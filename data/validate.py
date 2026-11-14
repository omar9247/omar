"""Validate the simulator against the real datasets it was calibrated from.

    uv run python data/validate.py      -> prints the table, writes data/processed/validation.csv

For each signal with real data: level, within-unit spread, between-unit spread and coverage
(share of real values inside the simulated 2.5-97.5% range), real vs simulated. A "unit" is what has
its own normal level: a person (BIDSleep, Inspiration4), a mission/cabin (EDA) or a detector (RadLab).
Inspiration4 also checks the flight change (day after landing vs pre-flight) against the immune scenario.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generator.sim import SCENARIOS, make_profile, simulate  # noqa: E402

PROCESSED = Path(__file__).parent / "processed"
N_SIM, DAYS = 2000, 63  # 63 days -> 10 weekly lab samples per simulated astronaut


def real_data() -> dict[str, pd.DataFrame]:
    """Long tables (unit, value) per signal, from data/processed/."""
    b = pd.read_csv(PROCESSED / "bidsleep_nights.csv")
    e = pd.read_csv(PROCESSED / "eda_co2_daily.csv")
    r = pd.read_csv(PROCESSED / "radlab_daily_dose.csv")
    lab = pd.read_csv(PROCESSED / "inspiration4_labs.csv")
    pre = lab[lab["day"] < 0]
    pick = lambda analyte, panel: pre[(pre.analyte == analyte) & pre.panel.str.contains(panel)]
    out = {n: b.rename(columns={"subject": "unit", n: "value"})[["unit", "value"]]
           for n in ["resting_hr_bpm", "sleep_duration_h", "sleep_efficiency_pct"]}
    out["cabin_co2_mmhg"] = e.rename(columns={"mission": "unit", "co2_mmhg_mean": "value"})[["unit", "value"]]
    out["dose_mgy"] = r.assign(value=r.absorbed_ugy_per_day / 1000).rename(columns={"instrument_id": "unit"})[["unit", "value"]]
    # (the lab table's own "unit" column is the measurement unit, so select before renaming)
    out["lymphocytes_per_ul"] = pick("absolute_lymphocytes", "CBC")[["crew", "value"]].rename(columns={"crew": "unit"})
    out["il6_pg_ml"] = pick("il_6", "immune_Eve")[["crew", "value"]].rename(columns={"crew": "unit"})
    return out


def stats(df: pd.DataFrame) -> dict:
    g = df.groupby("unit")["value"]
    return {"level": g.mean().mean(), "within_sd": np.sqrt(g.var().mean()), "between_sd": g.mean().std(),
            "n_units": g.ngroups, "n_values": len(df)}


def simulated(rng: np.random.Generator, n_sim: int = N_SIM) -> pd.DataFrame:
    frames = []
    for i in range(n_sim):
        d = simulate(make_profile(rng), DAYS, rng)
        frames.append(d.assign(unit=i))
    return pd.concat(frames)


def validate(seed: int = 0, n_sim: int = N_SIM) -> pd.DataFrame:
    sim = simulated(np.random.default_rng(seed), n_sim)
    rows = []
    for name, real in real_data().items():
        # compare like with like: give each simulated unit as many values as a typical real unit has
        # (spreads of slowly drifting signals such as CO2 depend on how long the run is)
        per_unit = int(real.groupby("unit").size().median())
        s = (sim[["unit", name]].dropna().groupby("unit").head(per_unit)
             .rename(columns={name: "value"}))
        lo, hi = np.percentile(s["value"], [2.5, 97.5])
        rs, ss = stats(real), stats(s)
        rows.append({"signal": name, "real_level": rs["level"], "sim_level": ss["level"],
                     "real_within_sd": rs["within_sd"], "sim_within_sd": ss["within_sd"],
                     "real_between_sd": rs["between_sd"], "sim_between_sd": ss["between_sd"],
                     "coverage_95": real["value"].between(lo, hi).mean(),
                     "real_units": rs["n_units"], "real_values": rs["n_values"]})
    return pd.DataFrame(rows)


def links(seed: int = 0, n_sim: int = N_SIM) -> pd.DataFrame:
    """Same-day links set with `corr` in signals.yaml: within-unit correlation, real vs simulated
    (deviations from each unit's own mean, simulated units cut to the real number of values)."""
    from contract.schema import load_signals
    b = pd.read_csv(PROCESSED / "bidsleep_nights.csv")
    sim = simulated(np.random.default_rng(seed), n_sim)
    per_unit = int(b.groupby("subject").size().median())
    within = lambda df, unit, a, c: (lambda d: d[a].corr(d[c]))(
        df[[a, c]] - df.groupby(unit)[[a, c]].transform("mean"))
    rows = []
    for s in load_signals():
        for other, r in s.get("corr", {}).items():
            real = b.dropna(subset=[s["name"], other])
            sm = sim.groupby("unit").head(per_unit)
            rows.append({"signal": s["name"], "linked_to": other, "set_r": r,
                         "real_r": within(real, "subject", s["name"], other),
                         "sim_r": within(sm, "unit", s["name"], other), "real_values": len(real)})
    return pd.DataFrame(rows)


def flight_change(seed: int = 0) -> pd.DataFrame:
    """Inspiration4 day-after-landing change per crew member vs the immune scenario at full effect."""
    lab = pd.read_csv(PROCESSED / "inspiration4_labs.csv")
    sc = SCENARIOS["immune"]
    rng = np.random.default_rng(seed)
    sims = [simulate(make_profile(rng), sc.days, rng, sc) for _ in range(500)]
    rows = []
    for name, analyte, panel in [("lymphocytes_per_ul", "absolute_lymphocytes", "CBC"), ("il6_pg_ml", "il_6", "immune_Eve")]:
        a = lab[(lab.analyte == analyte) & lab.panel.str.contains(panel)]
        pre = a[a.day < 0].groupby("crew").value.mean()
        post = a[a.timepoint == "R+1"].groupby("crew").value.mean()
        real = ((post / pre - 1) * 100).dropna()
        sim = np.array([(d[name][d.index >= sc.onset_day + 60].dropna().iloc[0]
                         / d[name][d.index < sc.onset_day].dropna().mean() - 1) * 100 for d in sims])
        lo, hi = np.percentile(sim, [2.5, 97.5])
        rows.append({"signal": name, "real_mean_pct": real.mean(), "sim_mean_pct": sim.mean(),
                     "real_min_pct": real.min(), "real_max_pct": real.max(), "sim_95_lo": lo, "sim_95_hi": hi,
                     "coverage_95": ((real >= lo) & (real <= hi)).mean(), "real_crew": len(real)})
    return pd.DataFrame(rows)


# Spreads calibrated from data (not from papers): (signal, field) pairs tuned by simulation so that
# short simulated runs reproduce the real within-unit and between-unit spreads.
MATCHED = {"resting_hr_bpm": ("sim_sd", "person_sd"), "sleep_duration_h": ("sim_sd", "person_sd"),
           "sleep_efficiency_pct": ("sim_sd", "person_sd"), "cabin_co2_mmhg": ("sim_sd", "person_sd"),
           "il6_pg_ml": ("person_sd",)}


def match_spreads(iterations: int = 5, n_sim: int = 800) -> dict:
    """Scale each matched field by real/simulated spread until they agree. Returns the new values.
    Changes the in-process signal settings: restart Python before trusting any other result."""
    from contract.schema import load_signals
    sig = {s["name"]: s for s in load_signals()}  # cached dicts: editing them changes the simulator
    for _ in range(iterations):
        v = validate(seed=1, n_sim=n_sim).set_index("signal")
        for name, fields in MATCHED.items():
            if "sim_sd" in fields:
                sig[name]["sim_sd"] *= v.at[name, "real_within_sd"] / v.at[name, "sim_within_sd"]
            if "person_sd" in fields:
                sig[name]["person_sd"] *= v.at[name, "real_between_sd"] / v.at[name, "sim_between_sd"]
    return {n: {f: round(sig[n][f], 4) for f in fields} for n, fields in MATCHED.items()}


def main() -> None:
    pd.set_option("display.width", 200)
    v, f, l = validate(), flight_change(), links()
    PROCESSED.mkdir(exist_ok=True)
    v.to_csv(PROCESSED / "validation.csv", index=False, float_format="%.4g")
    f.to_csv(PROCESSED / "validation_flight_change.csv", index=False, float_format="%.4g")
    print(v.round(3).to_string(index=False))
    print()
    print(f.round(1).to_string(index=False))
    print()
    print(l.round(3).to_string(index=False))
    l.to_csv(PROCESSED / "validation_links.csv", index=False, float_format="%.4g")


if __name__ == "__main__":
    main()
