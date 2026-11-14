"""Domain layer (plan 3.5): all health logic. No network or database code, so it tests alone."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from statistics import mean, stdev
import pandas as pd
from contract.schema import model_signals
from model.dataset import Z_CAP, baseline_stats

ORDER = ("unknown", "green", "stale", "amber", "red")  # a system shows the worst of its signals
log = logging.getLogger("aura.core")
DISCLAIMER = "Not a medical device. Research concept; all crew data is simulated."


def baseline(values: list[float]) -> tuple[float, float] | None:
    return (mean(values), stdev(values)) if len(values) >= 2 else None


def band(rule: dict | list[dict], value: float, base_mean: float | None = None) -> str | None:
    """green/amber/red for one reading; None while a baseline-relative rule has no baseline.
    A list of rules gives the worst band of those that can be evaluated."""
    if isinstance(rule, list):
        bands = [b for r in rule if (b := band(r, value, base_mean))]
        return max(bands, key=ORDER.index) if bands else None
    sign = 1 if rule["direction"] == "above" else -1
    relative = rule["kind"] != "abs"
    x = value
    if relative:
        if not base_mean:
            return None
        x = value - base_mean
        if rule["kind"] == "pct":
            x = x / base_mean * 100

    def crossed(t):
        return t is not None and sign * x > (t if relative else sign * t)

    return "red" if crossed(rule.get("red")) else "amber" if crossed(rule.get("amber")) else "green"


def pattern_hit(p: dict, signals: dict[str, dict]) -> bool:
    """Every signal amber or red, and at least its min_band where the pattern sets one."""
    need = p.get("min_band", {})
    return all(ORDER.index(signals[s]["band"]) >= ORDER.index(need.get(s, "amber")) for s in p["signals"])


def fired(signals: dict[str, dict], names: list[str]) -> dict[str, dict]:
    return {s: {k: signals[s].get(k) for k in ("band", "value", "ts", "provenance")} for s in names}


def published_red(name: str, e: dict, cfg: dict) -> bool:
    """Red by a threshold the research doc tags published (cumulative dose: NASA-STD-3001 career limit)."""
    if e["band"] != "red" or name == "cumulative_dose_msv":
        return e["band"] == "red"
    rule = cfg["thresholds"].get(name) or []
    return any(r["basis"] == "published" and band(r, e["value"], e.get("baseline_mean")) == "red"
               for r in (rule if isinstance(rule, list) else [rule]))


def signal_alerts(signals: dict[str, dict], cfg: dict) -> list[dict]:
    """One alert per signal red by a published threshold. Team choice 2026-11-13: all reds gave a median 11.5
    stored alerts per normal simulated astronaut in 40 days, published reds 1; other reds stay on the signal."""
    return [{"id": None, "signal": n, "name": f"{n} red", "level": "red", "fired": fired(signals, [n]),
             "rule": cfg["thresholds"].get(n), "response": e.get("response")}
            for n, e in signals.items() if published_red(n, e, cfg)]


def match_patterns(signals: dict[str, dict], patterns: list[dict], history: list[dict] = ()) -> list[dict]:
    """One alert per pattern that matches now and on each of its previous `days` - 1 days (history[0] = yesterday);
    red if any signal is red now (FR-5, FR-6)."""
    alerts = []
    for p in patterns:
        try:  # NFR-2: a broken pattern must not stop the others
            days = p.get("days", 1)
            if pattern_hit(p, signals) and len(history) >= days - 1 and all(
                    pattern_hit(p, h) for h in history[:days - 1]):
                bands = [signals[s]["band"] for s in p["signals"]]
                alerts.append(p | {"level": "red" if "red" in bands else "amber",
                                   "fired": fired(signals, p["signals"])})
        except Exception:  # noqa: BLE001
            log.exception("pattern %s failed", p.get("id"))
    return alerts


def signal_bands(latest: dict[str, dict], baselines: dict[str, tuple[float, float]], cfg: dict,
                 signals: list[dict], now: datetime) -> dict[str, dict]:
    out = {}
    for s in signals:
        name, r = s["name"], latest.get(s["name"])
        entry = {"system": s["system"], "band": "unknown"}
        if r:
            rule, base = cfg["thresholds"].get(name), baselines.get(name)
            limit = timedelta(days=s.get("interval_days", 1) * cfg["stale_after_intervals"])
            if now - datetime.fromisoformat(r["ts"]) > limit:
                entry["band"] = "stale"  # FR-8: never green when the data is late
            elif rule:
                entry["band"] = band(rule, r["value"], base and base[0]) or "unknown"
            entry |= {"value": r["value"], "ts": r["ts"], "provenance": r["provenance"], "rule": rule,
                      "baseline_mean": base and base[0], "baseline_sd": base and base[1],
                      "z": (r["value"] - base[0]) / base[1] if base and base[1] else None}
        out[name] = with_response(entry, name, cfg)
    return out


def with_response(entry: dict, name: str, cfg: dict) -> dict:
    """FR-6: what the medical system and the astronaut should do when a signal is amber or red."""
    r = cfg.get("responses", {}).get(name)
    if r and entry["band"] in ("amber", "red"):
        entry["response"] = {"system": r[entry["band"]], "crew": r["crew"]}
    return entry


def cumulative_dose(total_mgy: float, preset: dict, limits: dict, cfg: dict) -> dict:
    """Derived signal: career effective dose so far vs the career limit (research doc 5)."""
    c = cfg["cumulative_dose"]
    # shortcut: the whole history uses the current preset's quality factor; per-reading presets if presets switch mid-run
    msv = c["prior_career_msv"] + total_mgy * preset["quality_factor"]
    limit = limits["career_effective_dose_msv"]
    pct = 100 * msv / limit
    b = "red" if pct > c["red_pct_of_limit"] else "amber" if pct >= c["amber_pct_of_limit"] else "green"
    return with_response({"system": "radiation", "band": b, "value": round(msv, 2), "pct_of_limit": round(pct, 2),
                          "limit_msv": limit, "provenance": "derived"}, "cumulative_dose_msv", cfg)


def immune_risk(signals: dict[str, dict], cfg: dict) -> dict:
    """FR-15 research concept: weighted mean of bad-direction z-scores, 0-100."""
    ir = cfg["immune_risk"]
    inputs, num, den = {}, 0.0, 0.0
    for name, spec in ir["inputs"].items():
        z = signals.get(name, {}).get("z")
        if z is None:
            inputs[name] = None
            continue
        bad = max(0.0, z if spec["direction"] == "above" else -z)
        inputs[name] = round(bad, 2)
        num, den = num + spec["weight"] * bad, den + spec["weight"]
    score = None if den == 0 else round(min(100.0, 100 * num / den / ir["full_scale_z"]), 1)
    return {"score": score, "inputs": inputs, "not_measured": ir["not_measured"],
            "label": "research concept, not validated on crew data; placeholder weights"}


def model_baselines(raw: dict[str, list[float]]) -> dict[str, tuple[float, float]]:
    """Model-only baselines from raw first-14-day values; health baselines stay persisted separately."""
    names = model_signals()
    frame = pd.DataFrame({n: pd.Series(raw.get(n, []), dtype=float) for n in names})
    centre, spread = baseline_stats(frame)
    return {n: (float(centre[n]), float(spread[n])) for n in names
            if pd.notna(centre[n]) and pd.notna(spread[n])}


def model_window(snapshots: list[dict[str, dict]], baselines: dict[str, tuple[float, float]],
                 names: list[str]) -> dict[str, list[float]]:
    """Daily z-scores for the model service, oldest first (snapshots[0] = today). Missing = baseline (0)."""
    def z(snap, n):
        r, b = snap.get(n), baselines.get(n)
        if not r or not b:
            return 0.0
        return max(-Z_CAP, min(Z_CAP, (r["value"] - b[0]) / max(b[1], 1e-3)))
    return {n: [round(z(snap, n), 4) for snap in reversed(snapshots)] for n in names}


def score_checkin(reaction_times_ms: list[float] | None, mood_answers: list[float] | None, cfg: dict) -> dict:
    """FR-12: raw check-in -> signals. Lapse = reaction time at or above the PVT-B threshold (Basner 2011)."""
    c, out = cfg["checkin"], {}
    if reaction_times_ms:
        out["reaction_lapses_pct"] = 100 * sum(t >= c["lapse_ms"] for t in reaction_times_ms) / len(reaction_times_ms)
    if mood_answers:
        lo, hi = c["mood_scale"]
        if not all(lo <= a <= hi for a in mood_answers):
            raise ValueError(f"mood answers must be within {lo}-{hi}")
        out["mood_score"] = mean(mood_answers)
    return out


def system_bands(signals: dict[str, dict]) -> dict[str, str]:
    """Each body system shows the worst band of its signals."""
    systems: dict[str, str] = {}
    for e in signals.values():
        systems[e["system"]] = max(systems.get(e["system"], "unknown"), e["band"], key=ORDER.index)
    return systems


def history_days(cfg: dict) -> int:
    """How many earlier daily snapshots the patterns need."""
    return max((p.get("days", 1) for p in cfg.get("patterns", [])), default=1) - 1


def status(crew_id: str, latest: dict[str, dict], baselines: dict[str, tuple[float, float]],
           cfg: dict, signals: list[dict], history: list[dict[str, dict]] = (), mission: dict | None = None,
           dose_total_mgy: float | None = None, anomaly: dict | None = None) -> dict:
    """latest: newest stored reading per signal. history[k]: the same as of k + 1 days before now.
    'Now' is the newest reading of this crew member, so staleness also works when a scenario is
    replayed faster than real time."""
    now = max(datetime.fromisoformat(r["ts"]) for r in latest.values())
    out = signal_bands(latest, baselines, cfg, signals, now)
    if mission and dose_total_mgy is not None:
        out["cumulative_dose_msv"] = cumulative_dose(dose_total_mgy, mission["preset"], mission["limits"], cfg)
    past = [signal_bands(h, baselines, cfg, signals, now - timedelta(days=k + 1)) for k, h in enumerate(history)]
    systems = system_bands(out)
    alerts = match_patterns(out, cfg.get("patterns", []), past) + signal_alerts(out, cfg)
    return {"crew_id": crew_id, "ts": now.isoformat(), "baseline_ready": bool(baselines),
            "mission": mission and {"name": mission["name"], **mission["preset"]},
            "systems": systems, "signals": out, "alerts": alerts,
            "immune_risk": immune_risk(out, cfg), "anomaly": anomaly, "disclaimer": DISCLAIMER}
