"""Replay real ISS measurements in place of simulated values (plan FR-10: provenance "replayed").

Real daily series available (data/processed/):
- cabin_co2_mmhg: NASA EDA ISS CO2 — one mission (RR-5: 60 days, RR-3: 45 days) or all 10 usable
  missions joined in date order ("stitched": 423 days, with jumps where missions meet).
- dose_mgy: NASA RadLab ISS DosTel daily absorbed dose — 2 detectors, 90 days each. Crew member 1
  replays DosTel1, crew member 2 DosTel2; others keep simulated dose (only 2 real series exist).

Scenario effects are added on top of real values; from that day on the value is no longer a real
measurement, so it is labelled "simulated". Days beyond the end of a real series stay simulated.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from generator.sim import Scenario, apply_effect, effect_ramp

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
CO2_SOURCES = ("RR-5", "RR-3", "stitched")
DOSIMETERS = ("DosTel1", "DosTel2")


def co2_series(source: str) -> np.ndarray:
    d = pd.read_csv(PROCESSED / "eda_co2_daily.csv", parse_dates=["date"])
    if source == "stitched":
        start = d.groupby("mission")["date"].transform("min")
        return d.assign(start=start).sort_values(["start", "date"])["co2_mmhg_mean"].to_numpy()
    if source not in CO2_SOURCES:
        raise ValueError(f"unknown CO2 source {source!r}; choose from {CO2_SOURCES}")
    return d[d["mission"] == source].sort_values("date")["co2_mmhg_mean"].to_numpy()


def dose_series(crew_id: str) -> np.ndarray | None:
    """cm1 -> DosTel1, cm2 -> DosTel2, anyone else -> None (stays simulated)."""
    m = re.search(r"(\d+)$", crew_id)
    i = int(m.group(1)) - 1 if m else -1
    if not 0 <= i < len(DOSIMETERS):
        return None
    d = pd.read_csv(PROCESSED / "radlab_daily_dose.csv").sort_values("date")
    return d[d["instrument_id"] == DOSIMETERS[i]]["absorbed_ugy_per_day"].to_numpy() / 1000


def apply_replay(df: pd.DataFrame, crew_id: str, scenario: Scenario, co2_source: str = "RR-5",
                 preset: str = "station") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Swap real series into a simulated daily frame. Returns (values, provenance) with the same
    shape; provenance is "replayed" where a real, unmodified measurement is used, else "simulated".
    Real dose is ISS data, so it is replayed only under the station preset. Real CO2 is replayed
    under every preset (the ISS cabin stands in for any crew cabin)."""
    out = df.copy()
    prov = pd.DataFrame("simulated", index=df.index, columns=df.columns)
    dose = dose_series(crew_id) if preset == "station" else None
    for name, real in (("cabin_co2_mmhg", co2_series(co2_source)), ("dose_mgy", dose)):
        if real is None or name not in df:
            continue
        n = min(len(real), len(df))
        dropped = df[name].isna().to_numpy()[:n]               # sensor-loss scenario stays dropped
        values = apply_effect(real[:n], float(np.mean(real[:n])), scenario, name)
        pure = (effect_ramp(scenario, name, n) == 0) & ~dropped
        col = out[name].to_numpy().copy()
        col[:n] = np.where(dropped, np.nan, values)
        out[name] = col
        prov.iloc[:n, prov.columns.get_loc(name)] = np.where(pure, "replayed", "simulated")
    return out, prov
