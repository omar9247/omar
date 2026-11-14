"""Replay a scenario to MQTT: python -m generator.publish --scenario sleep_debt --crew cm1 --speed 10
--speed is seconds of wall-clock per simulated day (plan 6.2: ~10)."""
from __future__ import annotations

import argparse
import itertools
import json
import time

import numpy as np

from contract.schema import Reading
from generator.replay import CO2_SOURCES, apply_replay
from generator.sim import SCENARIOS, make_profile, simulate, to_readings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="normal", choices=SCENARIOS)
    ap.add_argument("--crew", default="cm1")
    ap.add_argument("--preset", default="station", help="station, moon, mars_transit, mars_surface")
    ap.add_argument("--days", type=int, default=None, help="default: the scenario's own length")
    ap.add_argument("--speed", type=float, default=10.0, help="seconds per simulated day")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--replay", action="store_true",
                    help="stream real ISS CO2 (and, for cm1/cm2 under station, real dose) as 'replayed'")
    ap.add_argument("--co2-source", default="RR-5", choices=CO2_SOURCES)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    a = ap.parse_args()

    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(a.host, a.port)
    client.loop_start()

    rng = np.random.default_rng(a.seed)
    days = a.days or SCENARIOS[a.scenario].days
    df = simulate(make_profile(rng, a.preset), days, rng, SCENARIOS[a.scenario])
    prov = "simulated"
    if a.replay:
        df, prov = apply_replay(df, a.crew, SCENARIOS[a.scenario], a.co2_source, a.preset)
    msgs = to_readings(a.crew, df, provenance=prov)
    for _, day_msgs in itertools.groupby(msgs, key=lambda m: m["ts"]):
        for m in day_msgs:
            r = Reading(**m)
            client.publish(r.topic(), json.dumps(m), qos=1)
        time.sleep(a.speed)
    client.loop_stop()


if __name__ == "__main__":
    main()
