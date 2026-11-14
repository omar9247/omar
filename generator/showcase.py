"""Safe, reserved-crew scenario showcases for the console demo.

This module deliberately uses the same generator messages and core ingest path as
``/scenario``.  It owns only showcase lifecycle state; it does not change mission
presets or game sessions.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Awaitable, Callable

import numpy as np

from generator.sim import SCENARIOS, make_profile, simulate, to_readings

SEED = 12
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.1
MAX_SPEED = 60.0
LABEL = "simulated"

SHOWCASE_NAMES = ("normal", "co2_creep", "sleep_debt", "sensor_loss")
RESERVED_CREWS = {name: f"demo_{name}" for name in SHOWCASE_NAMES}

# Timing is intentionally descriptive: rule alerts depend on the generated values,
# current thresholds, and baseline readiness, so the cards never promise an alarm.
_STORIES = {
    "normal": {
        "title": "Nominal flight day",
        "story": "A seed-12 simulated crew member follows ordinary day-to-day variation with no injected scenario effect.",
        "expected_events": [
            "Mission days 1–14: daily-signal baselines are established; weekly lab baselines need 28 days.",
            "Mission day 22 onward: normal variation continues; no exact alert is guaranteed.",
        ],
        "watch_signals": ["cabin_co2_mmhg", "sleep_duration_h", "resting_hr_bpm"],
    },
    "co2_creep": {
        "title": "Cabin CO₂ creep",
        "story": "Cabin CO₂ and related performance signals gradually move from this simulated crew member’s own baseline.",
        "expected_events": [
            "Mission day 22: the approved co2_creep effects begin at the existing scenario onset.",
            "Mission days 22–29: CO₂ and linked performance effects ramp over eight days; a rule alert is possible, not guaranteed.",
        ],
        "watch_signals": ["cabin_co2_mmhg", "reaction_lapses_pct", "mood_score"],
    },
    "sleep_debt": {
        "title": "Accumulating sleep debt",
        "story": "Sleep duration, efficiency, reaction lapses, and mood follow the existing simulated sleep-debt effects.",
        "expected_events": [
            "Mission day 22: the approved sleep_debt effects begin at the existing scenario onset.",
            "Mission days 22–26: sleep effects ramp over five days; downstream impairment alerts are possible, not guaranteed.",
        ],
        "watch_signals": ["sleep_duration_h", "sleep_efficiency_pct", "reaction_lapses_pct", "mood_score"],
    },
    "sensor_loss": {
        "title": "Sensor dropout",
        "story": "Two simulated sensors stop publishing at the existing sensor-loss onset so the core’s stale-data handling is visible.",
        "expected_events": [
            "Mission day 22: resting_hr_bpm and rmssd_ms readings stop in the generated stream.",
            "After the configured stale interval: the core may mark those signals stale; exact status timing is governed by contract thresholds.",
        ],
        "watch_signals": ["resting_hr_bpm", "rmssd_ms"],
    },
}


def _card(name: str) -> dict:
    scenario = SCENARIOS[name]
    # Scenario onset is zero-indexed in generator.sim; cards speak in mission days.
    return {
        "name": name,
        **_STORIES[name],
        "scenario": name,
        "source": f"generator.sim.SCENARIOS[{name!r}] (seed {SEED})",
        "crew_id": RESERVED_CREWS[name],
        "days": scenario.days,
        "onset_day": scenario.onset_day + 1,
        "onset_index": scenario.onset_day,
        "provenance": LABEL,
        "simulated": True,
        "label": LABEL,
    }


CATALOG = {name: _card(name) for name in SHOWCASE_NAMES}


class ShowcaseUnknown(ValueError):
    pass


class ShowcaseCollision(RuntimeError):
    pass


class ShowcaseRunning(RuntimeError):
    pass


@dataclass
class _Run:
    state: str = "ready"
    day: int = 0
    speed: float = DEFAULT_SPEED
    error: str | None = None
    task: asyncio.Task | None = None


class ShowcaseRunner:
    """Manage independent, repeatable replays on reserved demo crew IDs."""

    def __init__(self) -> None:
        self.runs = {name: _Run() for name in SHOWCASE_NAMES}

    def _check(self, name: str, speed: float) -> None:
        if name not in CATALOG:
            raise ShowcaseUnknown(f"unknown showcase {name}; choose from {list(CATALOG)}")
        if not np.isfinite(speed) or not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(f"speed must be between {MIN_SPEED} and {MAX_SPEED} seconds per simulated day")

    def cards(self) -> list[dict]:
        out = []
        for name in SHOWCASE_NAMES:
            run = self.runs[name]
            card = deepcopy(CATALOG[name])
            card.update({
                "state": run.state,
                "status": run.state,
                "completed_days": run.day,
                "speed": run.speed,
                "progress": {"day": run.day, "days": card["days"],
                              "fraction": round(run.day / card["days"], 3)},
                "error": run.error,
            })
            out.append(card)
        return out

    async def start(
        self,
        name: str,
        speed: float,
        *,
        clear: Callable[[str, bool], None],
        ingest: Callable[[bytes | str, str | None], object],
        broadcast: Callable[[str], Awaitable[None]],
        mission_name: Callable[[], str],
    ) -> dict:
        self._check(name, speed)
        run = self.runs[name]
        if run.state == "running":
            raise ShowcaseRunning(f"showcase {name} is already running")

        crew_id = RESERVED_CREWS[name]
        # Only this fixed ID is cleared, and games are explicitly retained.
        try:
            clear(crew_id, include_games=False)
        except ValueError as exc:
            raise ShowcaseCollision(str(exc)) from None
        scenario = SCENARIOS[name]
        rng = np.random.default_rng(SEED)
        messages = to_readings(
            crew_id,
            simulate(make_profile(rng, mission_name()), scenario.days, rng, scenario),
        )
        run.state, run.day, run.speed, run.error = "running", 0, speed, None

        async def replay() -> None:
            try:
                for day, (_, day_messages) in enumerate(itertools.groupby(messages, key=lambda m: m["ts"]), 1):
                    for message in day_messages:
                        ingest(json.dumps(message), "showcase")
                    run.day = day
                    await broadcast(crew_id)
                    if day < scenario.days:
                        await asyncio.sleep(speed)
                run.state = "completed"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # surfaced through GET /showcases, not lost in a task
                run.state, run.error = "error", str(exc)

        run.task = asyncio.create_task(replay())
        return self.response(name)

    def response(self, name: str) -> dict:
        if name not in CATALOG:
            raise ShowcaseUnknown(name)
        card = deepcopy(CATALOG[name])
        run = self.runs[name]
        card.update({
            "state": run.state,
            "status": run.state,
            "completed_days": run.day,
            "speed": run.speed,
            "progress": {"day": run.day, "days": card["days"],
                          "fraction": round(run.day / card["days"], 3)},
            "error": run.error,
        })
        return card

    async def shutdown(self) -> None:
        """Stop active replays before the app closes its SQLite store."""
        tasks = [run.task for run in self.runs.values() if run.task and not run.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for run in self.runs.values():
            if run.state == "running":
                run.state, run.day, run.error = "ready", 0, None


runner = ShowcaseRunner()
