"""Personal baselines, deterioration alerts and astronaut feedback.

This module deliberately contains no game mechanics: games report raw metrics,
the database stores them, and this engine turns them into longitudinal
neurobehavioral indicators. Game scores are never treated as a diagnosis.
"""

import datetime as _dt
import json


def median(values):
    """Small local median helper (avoids Pygbag's PyPI import scan)."""
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return None
    middle = n // 2
    return (ordered[middle] if n % 2
            else (ordered[middle - 1] + ordered[middle]) / 2)

# Classification tolerance for a single reaction relative to the baseline.
CLASSIFY_TOLERANCE = 0.10

# Percentage thresholds (configurable per assessment below).
AMBER_PCT = 20.0
RED_PCT = 40.0

FLAG_ACTIONS = {
    "sleep": "Prioritise sleep extension toward an 8-hour sleep opportunity and keep "
             "a consistent light-dark schedule.",
    "co2": "Check cabin CO2 sensors and ventilation; the operational target is at or "
           "below 2.5 mmHg.",
    "hrv": "Compare with resting heart rate and HRV trends; review recovery, workload "
           "and sleep conditions.",
    "efficiency": "Review sleep efficiency and the sleep environment (light, noise, "
                  "temperature).",
    "mood": "Initiate a behavioural-health check-in and review light exposure and "
            "workload.",
    "hydration": "Increase fluid intake toward the 90% hydration target.",
    "stress": "Review workload, recovery time and available physiological stress "
              "indicators.",
}

ASSESSMENTS = {
    "reaction_test": {
        "title": "Reaction Test",
        "metric": "avg_reaction_ms",
        "label": "median reaction time",
        "unit": "ms",
        "direction": "lower",
        "min_trials": 6,
        "min_sessions": 3,
        "biomarker": "Reaction-time lapses (90-second PVT-B style vigilance)",
        "interpretation": "Reduced vigilance and neurobehavioral impairment can be "
                          "associated with sleep deficiency, severe sleep restriction "
                          "or elevated cabin CO2. This is a potential association, "
                          "not a diagnosis.",
        "normal_advice": "Continue routine monitoring and maintain your current sleep "
                         "schedule.",
        "actions": [
            "Protect an 8-hour sleep opportunity.",
            "Maintain consistent light-dark schedules.",
            "Check cabin CO2 sensors and ventilation if you also notice headache or "
            "congestion.",
            "If a Red alert is confirmed, reassess fitness for safety-critical tasks "
            "and consult the flight surgeon.",
        ],
    },
    "lunar_alien_reaction": {
        "title": "Lunar Alien Reaction",
        "metric": "avg_reaction_ms",
        "label": "median target-recognition time",
        "unit": "ms",
        "direction": "lower",
        "min_trials": 8,
        "min_sessions": 3,
        "biomarker": "Reaction-time lapses and selective attention",
        "interpretation": "Attentional slowing and impaired decision-making can be "
                          "associated with isolation, circadian misalignment or "
                          "somatic stress. This is a potential association, not a "
                          "diagnosis.",
        "normal_advice": "Continue routine monitoring; keep assessments under "
                         "comparable conditions.",
        "actions": [
            "Complete initial baseline assessments while rested.",
            "Establish a reliable personal preflight/in-flight reference.",
            "Review light-dark schedule timing if repeated circadian disruption "
            "occurs.",
        ],
    },
    "speed_click": {
        "title": "Speed Click",
        "metric": "avg_hit_ms",
        "label": "median time-to-hit",
        "unit": "ms",
        "direction": "lower",
        "min_trials": 8,
        "min_sessions": 3,
        "biomarker": "Fine-motor jitter and psychomotor speed",
        "interpretation": "Changes in psychomotor speed and motor variability can be "
                          "associated with microgravity sensorimotor adaptation, acute "
                          "sleep debt or physiological stress. This is a potential "
                          "association, not a diagnosis.",
        "normal_advice": "Continue routine monitoring and keep recording persistent "
                         "task errors.",
        "actions": [
            "Complete baseline calibration sessions.",
            "Record persistent task errors.",
            "Report persistent sleep difficulties.",
            "Review sleep conditions and prescribed exercise when appropriate.",
        ],
    },
    "coloring_shapes": {
        "title": "Coloring Shapes",
        "metric": "error_rate",
        "label": "selection error rate",
        "unit": "%",
        "direction": "lower",
        "absolute": True,
        "amber_abs": 5.0,
        "red_abs": 15.0,
        "min_trials": 10,
        "min_sessions": 3,
        "biomarker": "Fine-motor jitter and motor stability",
        "interpretation": "Reduced precision and increased fine-motor errors can be "
                          "associated with acute fatigue, circadian desynchronization "
                          "or physiological stress. This is a potential association, "
                          "not a diagnosis.",
        "normal_advice": "Continue routine monitoring; this result alone does not "
                         "require deferring manual tasks.",
        "actions": [
            "Defer delicate manual hardware or EVA tasks only if a Red alert is "
            "confirmed.",
            "Compare performance with resting HR and HRV.",
            "Review sleep efficiency (Amber below 85%, Red below 75%).",
        ],
    },
    "number_hunt": {
        "title": "Number Hunt",
        "metric": "completion_time",
        "label": "completion time",
        "unit": "s",
        "direction": "lower",
        "min_trials": 1,
        "min_sessions": 3,
        "biomarker": "Attention and executive visual search",
        "interpretation": "Executive visual-search slowing can be associated with "
                          "circadian desynchronization or CO2-associated cognitive "
                          "effects. This is a potential association, not a diagnosis.",
        "normal_advice": "Continue routine monitoring and maintain hydration.",
        "actions": [
            "Check cabin air quality (CO2 target at or below 2.5 mmHg).",
            "Verify hydration against the 90% target.",
            "If deteriorating daily mood scores accompany the decline, initiate "
            "behavioural-health check-ins.",
            "Review light exposure and reduce light intensity when appropriate.",
        ],
    },
    "memory_test": {
        "title": "Memory Test",
        "metric": "longest_sequence",
        "label": "longest recalled sequence",
        "unit": " steps",
        "direction": "higher",
        "min_trials": 1,
        "min_sessions": 3,
        "biomarker": "Working memory and fine-motor jitter",
        "interpretation": "Working-memory changes can accompany chronic sleep "
                          "deficiency, circadian disruption or multisystem "
                          "physiological stress. This is a potential association, "
                          "not a diagnosis.",
        "normal_advice": "Continue routine monitoring and maintain your sleep "
                         "schedule.",
        "actions": [
            "Use the sequence-recall check to screen recall and input precision.",
            "If deterioration coincides with reduced HRV and short sleep duration, "
            "initiate a multisystem review covering sleep, workload and available "
            "immune/cortisol indicators.",
        ],
    },
}

STATUS_LABELS = {
    "none": "BASELINE REQUIRED",
    "baseline": "BASELINE REQUIRED",
    "provisional": "CALIBRATING",
    "invalid": "INSUFFICIENT DATA",
    "normal": "NORMAL",
    "amber": "AMBER ALERT",
    "red": "RED ALERT",
}

LEVEL_COLORS = {
    "normal": (75, 245, 170),
    "amber": (255, 205, 75),
    "red": (255, 95, 120),
    "baseline": (55, 225, 255),
    "invalid": (142, 154, 192),
}


def _load_extra(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}
    return {}


def format_value(value, cfg):
    if value is None:
        return "—"
    unit = cfg.get("unit", "")
    if unit == "ms":
        return f"{value:.0f} ms"
    if unit == "s":
        return f"{value:.1f} s"
    if unit == "%":
        return f"{value:.1f}%"
    if unit == " steps":
        return f"{value:.0f} steps"
    return f"{value:.0f}"


def deterioration(current, baseline, cfg):
    """Positive values mean worse performance. Direction-aware."""
    if baseline is None or current is None:
        return None
    if cfg.get("absolute"):
        return current - baseline
    if not baseline:
        return None
    if cfg["direction"] == "lower":
        return (current - baseline) / baseline * 100.0
    return (baseline - current) / baseline * 100.0


class NeuroEngine:
    def __init__(self, db):
        self.db = db
        self._rebuilt = False

    # ---------------------------------------------------------- metrics
    def config(self, game_id):
        return ASSESSMENTS.get(game_id)

    def extract(self, game_id, source):
        """Return {value, valid, reason, metrics} for a result or DB row."""
        cfg = self.config(game_id)
        ex = _load_extra(source.get("extra"))
        hits = int(source.get("hits") or 0)
        mistakes = int(source.get("mistakes") or 0)
        premature = int(ex.get("premature") or 0)
        metrics = dict(ex)
        reason = ""
        valid = True
        value = None

        if game_id == "reaction_test":
            trials = ex.get("trials") or []
            value = median(trials) if trials else source.get("avg_reaction_ms")
            if len(trials) < cfg["min_trials"]:
                valid = False
                reason = f"only {len(trials)} valid trials (minimum {cfg['min_trials']})"
            elif premature > 5:
                valid = False
                reason = f"{premature} premature clicks"
        elif game_id == "lunar_alien_reaction":
            trials = ex.get("reaction_times") or []
            value = median(trials) if trials else source.get("avg_reaction_ms")
            if len(trials) < cfg["min_trials"]:
                valid = False
                reason = (f"only {len(trials)} valid target responses "
                          f"(minimum {cfg['min_trials']})")
            elif int(ex.get("incorrect_friendly") or 0) > 8:
                valid = False
                reason = "too many friendly-alien errors"
        elif game_id == "speed_click":
            value = ex.get("median_hit_ms")
            if value is None:
                value = ex.get("avg_hit_ms")
            if hits < cfg["min_trials"]:
                valid = False
                reason = f"only {hits} targets hit (minimum {cfg['min_trials']})"
        elif game_id == "coloring_shapes":
            value = ex.get("error_rate")
            if int(ex.get("targets_total") or 0) < cfg["min_trials"]:
                valid = False
                reason = "not enough targets shown"
            elif value is None:
                valid = False
                reason = "precision metric unavailable"
        elif game_id == "number_hunt":
            if not ex.get("completed"):
                valid = False
                reason = "assessment not completed within the time limit"
            value = ex.get("completion_time")
        elif game_id == "memory_test":
            value = ex.get("longest_sequence")
            if int(ex.get("rounds_cleared") or 0) < 1:
                valid = False
                reason = "no sequence cleared"
        else:
            valid = False
            reason = "unknown assessment"

        if valid and value is None:
            valid = False
            reason = "primary metric missing"

        return {"value": value, "valid": valid, "reason": reason,
                "metrics": metrics, "hits": hits, "mistakes": mistakes}

    # --------------------------------------------------------- baseline
    def get_baseline(self, game_id, difficulty=None):
        row = self.db.get_baseline(game_id, difficulty)
        if row and difficulty and row.get("difficulty") != difficulty:
            return None
        return row

    def reaction_baseline(self, game_id):
        """Provisional or established baseline value for instant classification."""
        row = self.db.get_baseline(game_id)
        if row and row.get("baseline_value"):
            return row
        return None

    def classify_reaction(self, rt_ms, baseline_value):
        if not baseline_value or baseline_value <= 0:
            return "baseline"
        if rt_ms < baseline_value * (1 - CLASSIFY_TOLERANCE):
            return "fast"
        if rt_ms > baseline_value * (1 + CLASSIFY_TOLERANCE):
            return "slow"
        return "normal"

    def status_for(self, game_id, difficulty=None):
        row = self.get_baseline(game_id, difficulty)
        if not row:
            latest = self.db.latest_session(game_id)
            if latest and latest.get("alert_level") == "invalid":
                return "INSUFFICIENT DATA", "invalid"
            return "BASELINE REQUIRED", "none"
        cfg = self.config(game_id) or {}
        if row.get("samples", 0) < cfg.get("min_sessions", 3):
            return "CALIBRATING", "provisional"
        latest = self.db.latest_session(game_id)
        level = (latest or {}).get("alert_level")
        if level in ("amber", "red"):
            return STATUS_LABELS[level], level
        if level == "invalid":
            return "INSUFFICIENT DATA", "invalid"
        if level == "baseline" or level is None:
            return "CALIBRATING", "baseline"
        return "NORMAL", "normal"

    def evaluate(self, game_id, difficulty, result):
        cfg = self.config(game_id)
        if cfg is None:
            return {"valid": False, "level": "invalid", "status": "INSUFFICIENT DATA",
                    "value": None, "deterioration": None, "baseline_value": None,
                    "difficulty": difficulty, "game_id": game_id,
                    "multisystem": False, "reason": "unknown assessment",
                    "metric": None, "samples": 0}
        ex = self.extract(game_id, result)
        base = self.get_baseline(game_id, difficulty)
        ev = {
            "game_id": game_id,
            "difficulty": difficulty,
            "metric": cfg["metric"],
            "metric_label": cfg["label"],
            "unit": cfg["unit"],
            "value": ex["value"],
            "valid": ex["valid"],
            "reason": ex["reason"],
            "baseline_value": None,
            "original_baseline": None,
            "samples": 0,
            "deterioration": None,
            "level": "invalid",
            "status": "INSUFFICIENT DATA",
            "multisystem": False,
            "metrics": ex["metrics"],
        }
        if not ex["valid"]:
            return ev
        if base is None:
            ev["level"] = "baseline"
            ev["status"] = "BASELINE REQUIRED"
            return ev

        ev["baseline_value"] = base["baseline_value"]
        ev["original_baseline"] = base["original_value"]
        ev["samples"] = base["samples"]
        ev["deterioration"] = deterioration(ex["value"], base["baseline_value"], cfg)
        established = base["samples"] >= cfg["min_sessions"]
        if not established:
            ev["level"] = "baseline"
            ev["status"] = "CALIBRATING"
            return ev

        d = ev["deterioration"]
        if d is None:
            ev["level"] = "normal"
            ev["status"] = "NORMAL"
            return ev
        prev = self.db.last_valid_session(game_id, difficulty)
        prev_d = prev.get("deterioration") if prev else None
        if prev is not None and prev.get("alert_level") in (None, "baseline", "invalid"):
            prev_d = None

        level = "normal"
        if cfg.get("absolute"):
            amber, red = cfg.get("amber_abs", 5.0), cfg.get("red_abs", 15.0)
            if d > red and (prev_d is None or prev_d > amber / 2):
                level = "red"
            elif d > amber and prev_d is not None and prev_d > amber / 2:
                level = "amber"
        else:
            if d > RED_PCT:
                level = "red" if (prev_d is None or prev_d > AMBER_PCT / 2) else "amber"
            elif d > AMBER_PCT and prev_d is not None and prev_d > 10:
                level = "amber"
        ev["level"] = level
        ev["status"] = STATUS_LABELS[level]

        flags = self.physiology_flags()
        ev["flags"] = flags
        if level in ("amber", "red") and any(f["level"] in ("amber", "red")
                                             for f in flags):
            ev["multisystem"] = True
        return ev

    def update_baseline(self, game_id, difficulty, value):
        cfg = self.config(game_id)
        row = self.get_baseline(game_id, difficulty)
        if row is None:
            self.db.upsert_baseline(
                game_id, difficulty, cfg["metric"], cfg["direction"],
                value, value, value, 1, "provisional")
            self.db.add_baseline_history(game_id, difficulty, None, value,
                                         "Initial baseline established")
            return
        vals = self.db.recent_valid_values(game_id, difficulty, 5)
        if not vals:
            return
        samples = row["samples"] + 1
        rolling = median(vals[-3:])
        min_sessions = cfg["min_sessions"]
        base = row["baseline_value"]
        original = row["original_value"]
        new_base = base
        reason = "Within expected range — baseline unchanged"
        status = row["status"]
        if samples < min_sessions:
            status = "provisional"
            reason = "Calibration in progress"
        elif row["samples"] < min_sessions:
            new_base = median(vals[-3:])
            status = "established"
            reason = "Baseline established from calibration sessions"
        else:
            if not base:
                new_base = rolling
                reason = "Baseline refreshed (invalid prior value)"
            else:
                drift = abs(rolling - base) / abs(base)
                same_side_worse = all(
                    (v - base) / base > 0.15 if cfg["direction"] == "lower"
                    else (base - v) / base > 0.15 for v in vals)
                same_side_better = all(
                    (base - v) / base > 0.15 if cfg["direction"] == "lower"
                    else (v - base) / base > 0.15 for v in vals)
                if len(vals) >= 5 and (same_side_worse or same_side_better):
                    new_base = rolling
                    reason = "Persistent shift across five sessions"
                elif drift <= 0.10:
                    new_base = base * 0.7 + rolling * 0.3
                    reason = "Gradual drift within tolerance"
        self.db.upsert_baseline(
            game_id, difficulty, cfg["metric"], cfg["direction"],
            original, new_base, rolling, samples, status)
        if base is None or abs((new_base or 0) - (base or 0)) > max(0.5, abs(base or 1) * 0.005):
            self.db.add_baseline_history(game_id, difficulty, base, new_base, reason)

    # ------------------------------------------------------ physiology
    def physiology_flags(self, record=None):
        rec = record if record is not None else self.db.get_physiology()
        if not rec:
            return []
        flags = []

        def add(key, label, value_text, level, detail):
            flags.append({"key": key, "label": label, "value": value_text,
                          "level": level, "detail": detail})

        sleep = rec.get("sleep_hours")
        if sleep is not None:
            if sleep < 5:
                add("sleep", "Sleep duration", f"{sleep:.1f} h", "red",
                    "Severe sleep restriction (below 5 h)")
            elif sleep < 7:
                add("sleep", "Sleep duration", f"{sleep:.1f} h", "amber",
                    "Short sleep (below 7 h)")
        co2 = rec.get("co2_mmhg")
        if co2 is not None:
            if co2 > 3.0:
                add("co2", "Cabin CO2", f"{co2:.1f} mmHg", "red",
                    "Above 3.0 mmHg")
            elif co2 > 2.5:
                add("co2", "Cabin CO2", f"{co2:.1f} mmHg", "amber",
                    "Above the 2.5 mmHg target")
        hrv = rec.get("hrv_ms")
        history = self.db.hrv_history(14)
        if hrv is not None and len(history) >= 4:
            prior = [h for h in history[1:] if h]
            if prior:
                base = median(prior)
                if base > 0:
                    drop = (base - hrv) / base
                    if drop > 0.4:
                        add("hrv", "HRV", f"{hrv:.0f} ms ({drop * 100:.0f}% below)",
                            "red", "Marked reduction versus personal baseline")
                    elif drop > 0.2:
                        add("hrv", "HRV", f"{hrv:.0f} ms ({drop * 100:.0f}% below)",
                            "amber", "Reduced versus personal baseline")
        eff = rec.get("sleep_efficiency")
        if eff is not None:
            if eff < 75:
                add("efficiency", "Sleep efficiency", f"{eff:.0f}%", "red",
                    "Below 75%")
            elif eff < 85:
                add("efficiency", "Sleep efficiency", f"{eff:.0f}%", "amber",
                    "Below 85%")
        mood = rec.get("mood")
        if mood is not None:
            if mood <= 3:
                add("mood", "Daily mood", f"{mood}/10", "red", "Very low mood score")
            elif mood <= 5:
                add("mood", "Daily mood", f"{mood}/10", "amber", "Reduced mood score")
        hydration = rec.get("hydration")
        if hydration is not None:
            if hydration < 80:
                add("hydration", "Hydration", f"{hydration:.0f}%", "red",
                    "Well below the 90% target")
            elif hydration < 90:
                add("hydration", "Hydration", f"{hydration:.0f}%", "amber",
                    "Below the 90% target")
        stress = rec.get("stress")
        if stress is not None:
            if stress >= 8:
                add("stress", "Stress index", f"{stress}/10", "red",
                    "High physiological stress indicator")
            elif stress >= 6:
                add("stress", "Stress index", f"{stress}/10", "amber",
                    "Elevated stress indicator")
        return flags

    # -------------------------------------------------------- feedback
    def build_feedback(self, game_id, ev, flags):
        cfg = self.config(game_id)
        level = ev.get("level", "invalid")
        value_text = format_value(ev.get("value"), cfg)
        base_text = format_value(ev.get("baseline_value"), cfg)
        d = ev.get("deterioration")
        ms = ev.get("multisystem")
        actions = []
        parts = []

        if level == "invalid":
            headline = "ASSESSMENT EXCLUDED"
            message = ("This run did not produce enough valid observations "
                       f"({ev.get('reason') or 'incomplete assessment'}). It was not "
                       "used to update your baseline and cannot generate an alert. "
                       "Repeat the assessment under comparable, rested conditions.")
            actions = ["Repeat the assessment when you are rested and distraction-free."]
        elif level == "baseline":
            if ev.get("baseline_value") is None:
                headline = "BASELINE REQUIRED"
                message = ("No personal baseline existed for this assessment. This "
                           f"valid run ({value_text}) is your initial reference point; "
                           "no alert is generated from a first measurement. Complete "
                           "three valid calibration sessions so future changes can be "
                           "compared against your own performance.")
            else:
                samples = ev.get("samples", 0)
                need = max(0, cfg["min_sessions"] - samples)
                headline = "CALIBRATING"
                more = (f"{need} more valid session is required" if need == 1
                        else f"{need} more valid sessions are required")
                message = (f"Calibration session recorded ({value_text}; provisional "
                           f"baseline {base_text}). {more} before alerts are "
                           "enabled. No alert is generated while calibrating.")
            actions = ["Complete calibration sessions while rested and under similar "
                       "conditions (time of day, device, posture)."]
        elif level == "normal":
            headline = "WITHIN BASELINE"
            if d is None:
                message = (f"Your {cfg['label']} ({value_text}) remains within your "
                           "expected personal range. " + cfg["normal_advice"])
            else:
                direction_word = "better than" if d < 0 else "worse than"
                message = (f"Your {cfg['label']} of {value_text} is "
                           f"{abs(d):.0f}% {direction_word} your personal baseline of "
                           f"{base_text}. ")
                if d > 10:
                    message += ("A change of this size was detected but is not yet "
                                "confirmed as persistent, so no alert was raised. "
                                "Repeat the assessment under comparable conditions to "
                                "verify whether it reflects a real trend.")
                else:
                    message += ("This is within the expected fluctuation range. "
                                + cfg["normal_advice"])
            actions = [cfg["normal_advice"]]
        else:
            headline = "MULTISYSTEM ALERT" if ms else STATUS_LABELS[level]
            if cfg.get("absolute"):
                change = f"increased by {d:.1f} points"
            else:
                change = f"deteriorated by {abs(d):.0f}%"
            message = (f"Your {cfg['label']} has {change} compared with your personal "
                       f"baseline ({base_text} → {value_text}). " +
                       cfg["interpretation"])
            if level == "red":
                message += (" This represents a significant change in your "
                            "neurobehavioral performance. Reassess fitness for "
                            "safety-critical activities and consult the flight surgeon.")
            else:
                message += (" Repeat the assessment under comparable conditions before "
                            "drawing operational conclusions.")
            actions = list(cfg["actions"])
            if ms:
                affected = ", ".join(f"{f['label']} {f['value']}" for f in flags
                                     if f["level"] in ("amber", "red"))
                message = (f"Your cognitive performance ({cfg['label']} {value_text}, "
                           f"{change} versus baseline {base_text}) declined alongside "
                           f"reduced physiological indicators: {affected}. This "
                           "combination may indicate broader physiological stress "
                           "rather than an isolated cognitive fluctuation. " +
                           cfg["interpretation"])
                for f in flags:
                    if f["level"] in ("amber", "red") and f["key"] in FLAG_ACTIONS:
                        actions.append(FLAG_ACTIONS[f["key"]])
                actions.insert(0, "Prioritise a broader review of sleep, workload, "
                                  "environmental conditions and physiological "
                                  "indicators.")

        actions = list(dict.fromkeys(a for a in actions if a))
        return {
            "headline": headline,
            "level": level,
            "status": ev.get("status", ""),
            "multisystem": bool(ms),
            "message": message,
            "actions": actions,
            "deterioration": d,
            "baseline_value": ev.get("baseline_value"),
            "value": ev.get("value"),
            "flags": flags,
        }

    # ---------------------------------------------------------- commit
    def commit(self, game_id, difficulty, result):
        ev = self.evaluate(game_id, difficulty, result)
        flags = self.physiology_flags()
        ev["flags"] = flags
        feedback = self.build_feedback(game_id, ev, flags)
        session_id = self.db.record(game_id, ASSESSMENTS[game_id]["title"],
                                    result, ev, feedback)
        if ev.get("valid") and ev.get("value") is not None:
            self.update_baseline(game_id, difficulty, ev["value"])
        if ev.get("level") in ("amber", "red"):
            self.db.add_alert(
                session_id, game_id, ev["level"], ev.get("deterioration"),
                ev.get("multisystem"),
                self.db.get_physiology() or {},
                feedback["message"])
        return ev, feedback, session_id

    # ------------------------------------------------------ legacy data
    def rebuild_from_history(self):
        """Populate baselines/metrics for sessions created before v2."""
        if self._rebuilt or self.db.has_baselines():
            self._rebuilt = True
            return 0
        rows = self.db.all_sessions_asc()
        if not rows:
            self._rebuilt = True
            return 0
        rebuilt = 0
        for row in rows:
            game_id = row["game_id"]
            if game_id not in ASSESSMENTS:
                continue
            cfg = ASSESSMENTS[game_id]
            difficulty = row.get("difficulty") or "normal"
            ex = self.extract(game_id, row)
            if not ex["valid"]:
                self.db.update_session_metrics(row["id"], False, None,
                                               difficulty=difficulty)
                continue
            base = self.get_baseline(game_id, difficulty)
            det = None
            level = "baseline"
            status = "BASELINE REQUIRED"
            bval = None
            if base and base["samples"] >= cfg["min_sessions"]:
                bval = base["baseline_value"]
                det = deterioration(ex["value"], bval, cfg)
                level = "normal"
                status = "NORMAL"
                if det is not None and det > RED_PCT:
                    level, status = "red", "RED ALERT"
                elif det is not None and det > AMBER_PCT:
                    level, status = "amber", "AMBER ALERT"
            elif base:
                bval = base["baseline_value"]
                status = "CALIBRATING"
            self.db.update_session_metrics(
                row["id"], True, ex["value"], bval, det, level, status, difficulty)
            self.update_baseline(game_id, difficulty, ex["value"])
            rebuilt += 1
        self._rebuilt = True
        return rebuilt
