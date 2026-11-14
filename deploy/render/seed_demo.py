"""Seed an empty public-demo database; never replace existing readings or games."""
import itertools
import json
import os

import numpy as np

from core import app as core
from core.store import Store
from generator.showcase import RESERVED_CREWS, SEED, SHOWCASE_NAMES
from generator.sim import SCENARIOS, make_profile, simulate, to_readings


def seed() -> None:
    if os.environ.get("AURA_PUBLIC_DEMO") != "1":
        return
    core.store = Store(os.environ.get("AURA_DB", "/data/core.db"))
    try:
        if core.store.count() or core.store.crews():
            print("Existing demo database retained", flush=True)
            return
        for crew_id in RESERVED_CREWS.values():
            core.store.reset_showcase(crew_id, include_games=False)
        core.store.db.execute("BEGIN IMMEDIATE")
        for name in SHOWCASE_NAMES:
            crew_id, scenario = RESERVED_CREWS[name], SCENARIOS[name]
            rng = np.random.default_rng(SEED)
            messages = to_readings(crew_id, simulate(make_profile(rng, core.mission()["name"]),
                                                    scenario.days, rng, scenario))
            for _, day in itertools.groupby(messages, key=lambda m: m["ts"]):
                for reading in day:
                    core.ingest(json.dumps(reading), "showcase")
                core.crew_status(crew_id)
            print(f"Seeded simulated showcase {name}", flush=True)
        core.store.db.commit()
    finally:
        core.store.db.close()


if __name__ == "__main__":
    seed()
