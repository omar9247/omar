"""Core service: MQTT ingest, REST and WebSocket (plan 3.5 API layer).
uvicorn core.app:app --port 8000
Env: AURA_DB (default core.db), AURA_MQTT_HOST (default localhost), AURA_MQTT_PORT (default 1883),
AURA_MODEL_URL (default http://localhost:8001).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AwareDatetime, BaseModel, Field

from contract.schema import Reading, load_limits, load_presets, load_signals, load_thresholds, model_signals
from core import domain, model_client
from core.game_sessions import GAME_LABEL, GameSession
from core import public_demo
from core.store import Store
from generator import showcase
from generator.sim import SCENARIOS, make_profile, simulate, to_readings
from model.dataset import BASELINE_DAYS

WEB = Path(__file__).resolve().parent.parent / "web" / "static"

log = logging.getLogger("aura.core")
store: Store
mqtt_client: mqtt.Client
sockets: set[WebSocket] = set()
_status_lock = threading.Lock()  # one status at a time: a stale overlapping one could reopen a closed alert


def ingest(payload: bytes | str, topic: str | None = None) -> Reading | None:
    """Validate and store one message. A bad message is logged to `reject` and dropped (FR-2, NFR-2)."""
    try:
        r = Reading.model_validate_json(payload)
        if r.signal not in {s["name"] for s in load_signals()}:
            raise ValueError(f"unknown signal {r.signal!r}")
        if not math.isfinite(r.value):
            raise ValueError("value is not finite")
    except Exception as e:  # noqa: BLE001
        text = payload.decode(errors="replace") if isinstance(payload, bytes) else payload
        log.warning("rejected message on %s: %s", topic, e)
        store.reject(topic, text, str(e))
        return None
    store.add(r)
    return r


def mission() -> dict:
    if (row := store.mission()) is None:
        set_preset("station")
        row = store.mission()
    return {"name": row["preset"], "preset": load_presets()[row["preset"]], "limits": load_limits()}


def set_preset(name: str) -> None:
    p = load_presets()[name]
    store.set_mission(name, p["one_way_delay_s"], p["dose_mgy_day"])


def anomaly(crew_id: str, base: dict, now: datetime) -> dict:
    """FR-14: model score over up to 14 days of z-scores; optional, never blocks the rule alerts."""
    raw = store.baseline_window(crew_id, BASELINE_DAYS)
    if not raw:
        return {"available": False, "reason": "baseline not ready"}
    first = datetime.fromisoformat(store.span(crew_id)[0])
    n = min(14, (now - first).days + 1)
    snaps = [day_readings(crew_id, now - timedelta(days=k)) for k in range(n)]
    window = domain.model_window(snaps, domain.model_baselines(raw), model_signals())
    return model_client.score(crew_id, window)


def day_readings(crew_id: str, until: datetime) -> dict:
    """Readings from the day ending at `until` only. A signal with none that day (dropped sensor) is left out, so
    the model sees baseline (0) for it, as in training (model.dataset.normalise), not its last value repeated."""
    after = (until - timedelta(days=1)).isoformat()
    return {n: r for n, r in store.latest(crew_id, until.isoformat()).items() if r["ts"] > after}


def latest_ts(latest: dict) -> str:
    return max(r["ts"] for r in latest.values())


def baselines(crew_id: str, cfg: dict) -> dict[str, tuple[float, float]]:
    """Stored baselines; a signal's baseline is computed and saved once its window has passed (plan 3.6:
    "baseline ready?"). Daily signals use baseline_days, weekly labs lab_baseline_days so they get enough samples."""
    stored = store.baselines(crew_id)
    labs = {s["name"] for s in load_signals() if s.get("interval_days", 1) > 1}
    for days, wanted in ((cfg["baseline_days"], lambda n: n not in labs), (cfg["lab_baseline_days"], labs.__contains__)):
        window = store.baseline_window(crew_id, days)
        new = {n: b for n, v in window.items() if wanted(n) and n not in stored and (b := domain.baseline(v))}
        if new:
            store.save_baselines(crew_id, new, days)
            stored |= new
    return stored


def crew_status(crew_id: str) -> dict | None:
    with _status_lock:
        return _crew_status(crew_id)


def _crew_status(crew_id: str) -> dict | None:
    latest = store.latest(crew_id)
    if not latest:
        return None
    cfg = load_thresholds()
    now = datetime.fromisoformat(latest_ts(latest))
    history = [store.latest(crew_id, (now - timedelta(days=k)).isoformat())
               for k in range(1, domain.history_days(cfg) + 1)]
    base, m = baselines(crew_id, cfg), mission()
    s = domain.status(crew_id, latest, base, cfg, load_signals(), history, m,
                      store.total(crew_id, "dose_mgy"), anomaly(crew_id, base, now))
    for alert_id, a in store.sync_alerts(crew_id, s["alerts"], s["ts"]):  # FR-16: each new alert goes to the ground
        store.queue_report(crew_id, alert_id, {
            "crew_id": crew_id, "ts": s["ts"], "alert": a["name"], "level": a["level"], "signals_fired": a["fired"],
            "systems": s["systems"], "mission": m["name"], "disclaimer": domain.DISCLAIMER},
            time.time(), m["preset"]["one_way_delay_s"])
    patterns = {p["id"]: p for p in cfg["patterns"]}
    signal_alert = {a["signal"]: a for a in s["alerts"] if a["id"] is None}
    s["alerts"] = [(patterns.get(r["pattern_id"]) or signal_alert.get(r["signal"]) or {
        "id": None, "signal": r["signal"], "name": f"{r['signal']} red", "rule": cfg["thresholds"].get(r["signal"]),
        "response": domain.with_response({"band": "red"}, r["signal"], cfg).get("response")}) | {
        "alert_id": r["id"], "level": r["level"], "fired": json.loads(r["signals_fired"]), "started_ts": r["ts"],
        "last_ts": r["last_ts"], "active": bool(r["active"]), "acknowledged_at": r["acknowledged_at"],
        "action": m["preset"]["alert_wording"]}  # FR-13: the same alert reads differently far from Earth
        for r in store.open_alerts(crew_id) if r["pattern_id"] is None or r["pattern_id"] in patterns]
    return s


async def broadcast(crew_id: str) -> None:
    msg = crew_status(crew_id)
    for ws in list(sockets):
        try:
            await ws.send_json(msg)
        except Exception:  # noqa: BLE001  a dead socket must not stop the others
            sockets.discard(ws)


def start_mqtt(loop: asyncio.AbstractEventLoop) -> mqtt.Client:
    # fixed id + clean_session=False: the broker keeps QoS 1 messages while the service restarts (NFR-3)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="aura-core", clean_session=False)
    c.on_connect = lambda client, *_: client.subscribe("aura/+/+", qos=1)

    def on_message(_c, _u, m):
        try:
            if r := ingest(m.payload, m.topic):
                asyncio.run_coroutine_threadsafe(broadcast(r.crew_id), loop)
        except Exception:  # noqa: BLE001
            log.exception("ingest failed")

    c.on_message = on_message
    c.connect_async(os.environ.get("AURA_MQTT_HOST", "localhost"), int(os.environ.get("AURA_MQTT_PORT", 1883)))
    c.loop_start()  # reconnects by itself; the API starts even with no broker
    return c


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global store, mqtt_client, replay
    store = Store(os.environ.get("AURA_DB", "core.db"))
    mqtt_client = start_mqtt(asyncio.get_running_loop())
    yield
    await showcase.runner.shutdown()
    if replay and not replay.done():
        replay.cancel()
        await asyncio.gather(replay, return_exceptions=True)
    mqtt_client.loop_stop()


app = FastAPI(title="AURA-Bio core service", lifespan=lifespan)
# a web app served from another port may call the API; any origin is fine for a local demo with simulated data
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(public_demo.PublicDemoMiddleware)
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.mount("/lunar-arcade-hub", StaticFiles(directory=WEB / "lunar-arcade-hub", html=True), name="games")
replay: asyncio.Task | None = None


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.post("/scenario/{name}")
async def run_scenario(name: str, crew_id: str = "cm1", seed: int = 12, speed: float = 10.0):
    """FR-9, demo only: wipe the crew member and replay a simulated scenario straight into the core, one day per
    `speed` seconds (same messages as generator.publish, so no broker is needed). A new call stops the last one."""
    global replay
    if name not in SCENARIOS:
        raise HTTPException(422, f"unknown scenario {name}; choose from {list(SCENARIOS)}")
    if replay:
        replay.cancel()
    store.clear(crew_id, include_games=False)  # scenario replay must not erase recorded game sessions
    rng, sc = np.random.default_rng(seed), SCENARIOS[name]
    msgs = to_readings(crew_id, simulate(make_profile(rng, mission()["name"]), sc.days, rng, sc))

    async def run():
        for _, day in itertools.groupby(msgs, key=lambda m: m["ts"]):
            for m in day:
                ingest(json.dumps(m), "scenario")
            await broadcast(crew_id)
            await asyncio.sleep(speed)

    replay = asyncio.create_task(run())
    return {"scenario": name, "crew_id": crew_id, "days": sc.days, "seed": seed, "seconds_per_day": speed}


@app.get("/showcases")
def get_showcases():
    """The four safe, simulated story cards and their current replay progress."""
    return showcase.runner.cards()


@app.post("/showcase/{name}")
async def run_showcase(name: str, speed: float = Query(showcase.DEFAULT_SPEED,
                                                         ge=showcase.MIN_SPEED,
                                                         le=showcase.MAX_SPEED)):
    """Replay one catalog scenario on its fixed reserved demo crew only."""
    claim = None
    if public_demo.enabled() and name in showcase.CATALOG:
        claim, retry_after = public_demo.reserve_showcase(name)
        if claim is None:
            raise HTTPException(429, f"showcase {name} is cooling down; retry in {retry_after} seconds",
                                headers={"Retry-After": str(retry_after)})
    try:
        return await showcase.runner.start(name, speed, clear=store.reset_showcase, ingest=ingest,
                                            broadcast=broadcast, mission_name=lambda: mission()["name"])
    except showcase.ShowcaseUnknown as e:
        public_demo.release_showcase(name, claim)
        raise HTTPException(422, str(e)) from None
    except (showcase.ShowcaseRunning, showcase.ShowcaseCollision) as e:
        public_demo.release_showcase(name, claim)
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        public_demo.release_showcase(name, claim)
        raise HTTPException(422, str(e)) from None


class CheckIn(BaseModel):
    crew_id: str
    # None = the crew member's current simulated day (their newest reading): the app does not know how far a
    # replayed scenario has run, and a wall-clock ts would land weeks in the past or jump everyone to stale
    ts: AwareDatetime | None = None
    values: dict[str, float] = {}  # signal name -> value, e.g. {"exercise_completion_pct": 95}
    reaction_times_ms: list[float] | None = Field(None, min_length=1)  # raw reaction test, one per trial
    mood_answers: list[float] | None = Field(None, min_length=1)  # one per mood question, on the checkin mood_scale


class MissionChange(BaseModel):
    preset: str


@app.get("/health")
def health():
    return {"status": "ok", "mqtt_connected": mqtt_client.is_connected(),
            "readings": store.count(), "rejects": store.count("reject")}


@app.get("/crew")
def crew():
    return store.crews()


@app.get("/crew/overview")
def overview():
    """FR-17: one card per astronaut for the crew medical officer."""
    cards = []
    for crew_id in store.crews():
        s = crew_status(crew_id)
        cards.append({"crew_id": crew_id, "ts": s["ts"], "systems": s["systems"],
                      "worst": max(s["systems"].values(), key=domain.ORDER.index),
                      "alerts": [{"alert_id": a["alert_id"], "name": a["name"], "level": a["level"],
                                  "active": a["active"]} for a in s["alerts"]],
                      "anomaly_score": s["anomaly"].get("score"), "immune_risk": s["immune_risk"]["score"]})
    return cards


@app.post("/alerts/{alert_id}/ack")
async def ack(alert_id: int):
    if (crew_id := store.ack(alert_id)) is None:
        raise HTTPException(404, f"no alert {alert_id}")
    await broadcast(crew_id)
    return {"acknowledged": alert_id}


@app.get("/ground/reports")
def ground_reports():
    """FR-16: reports reach the ground only after the mission's one-way delay (wall-clock seconds)."""
    released, pending = store.reports(time.time())
    return {"released": released, "pending": pending}


@app.get("/crew/{crew_id}/status")
def get_status(crew_id: str):
    if (s := crew_status(crew_id)) is None:
        raise HTTPException(404, f"no readings for {crew_id}")
    return s


@app.delete("/crew/{crew_id}")
def reset_crew(crew_id: str):
    """Demo only: wipe a crew member's readings before replaying another scenario."""
    store.clear(crew_id)
    return {"cleared": crew_id}


@app.get("/crew/{crew_id}/timeline")
def timeline(crew_id: str):
    """Per mission day, each body system's worst band (computed here, like every band), and every alert episode
    with its first and last day: what the console's timeline lanes draw. Day 1 is the crew member's first reading."""
    first, last = store.span(crew_id)
    if first is None:
        raise HTTPException(404, f"no readings for {crew_id}")
    cfg, signals = load_thresholds(), load_signals()
    labs = {s["name"] for s in signals if s.get("interval_days", 1) > 1}
    base = baselines(crew_id, cfg)
    t0 = datetime.fromisoformat(first)
    day_of = lambda ts: (datetime.fromisoformat(ts) - t0).days + 1  # noqa: E731
    days = []
    for d in range(day_of(last)):
        snap = store.latest(crew_id, (t0 + timedelta(days=d + 1, seconds=-1)).isoformat())
        if not snap:
            continue
        # only the baselines that existed on that day: relative rules stay unknown during the baseline period
        known = {k: v for k, v in base.items() if d >= cfg["lab_baseline_days" if k in labs else "baseline_days"]}
        now = max(datetime.fromisoformat(r["ts"]) for r in snap.values())
        days.append({"day": d + 1, "systems": domain.system_bands(domain.signal_bands(snap, known, cfg, signals, now))})
    system_of = {s["name"]: s["system"] for s in signals} | {"cumulative_dose_msv": "radiation"}
    names = {p["id"]: p["name"] for p in cfg["patterns"]}
    episodes = [{"alert_id": r["id"], "pattern_id": r["pattern_id"], "signal": r["signal"], "level": r["level"],
                 "name": names.get(r["pattern_id"], r["signal"]), "start_day": day_of(r["ts"]),
                 "end_day": day_of(r["last_ts"]), "active": bool(r["active"]),
                 "acknowledged": r["acknowledged_at"] is not None,
                 "systems": sorted({system_of.get(k, "") for k in json.loads(r["signals_fired"])} - {""})}
                for r in store.all_alerts(crew_id)]
    return {"crew_id": crew_id, "first_ts": first, "baseline_days": cfg["baseline_days"],
            "lab_baseline_days": cfg["lab_baseline_days"], "days": days, "episodes": episodes}


@app.get("/crew/{crew_id}/signal/{signal}")
def trend(crew_id: str, signal: str, days: int = 30):
    """FR-11: readings of one signal over the last `days` days, with the baseline band and thresholds."""
    if signal not in {s["name"] for s in load_signals()}:
        raise HTTPException(404, f"unknown signal {signal}")
    cfg = load_thresholds()
    _, last = store.span(crew_id)
    if last is None:
        raise HTTPException(404, f"no readings for {crew_id}")
    since = (datetime.fromisoformat(last) - timedelta(days=days)).isoformat()
    base = baselines(crew_id, cfg).get(signal)
    return {"crew_id": crew_id, "signal": signal, "points": store.series(crew_id, signal, since),
            "baseline_mean": base and base[0], "baseline_sd": base and base[1],
            "rule": cfg["thresholds"].get(signal)}


@app.get("/mission")
def get_mission():
    m = mission()
    return {"name": m["name"], **m["preset"], "presets": load_presets()}


@app.put("/mission")
async def set_mission(m: MissionChange):
    """FR-13: switch preset (demo mission panel); every crew member's status is pushed again."""
    if m.preset not in load_presets():
        raise HTTPException(422, f"unknown preset {m.preset}; choose from {list(load_presets())}")
    set_preset(m.preset)
    for crew_id in store.crews():
        await broadcast(crew_id)
    return get_mission()


@app.post("/checkin")
async def checkin(c: CheckIn):
    try:
        scored = domain.score_checkin(c.reaction_times_ms, c.mood_answers, load_thresholds())
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    last = store.span(c.crew_id)[1]
    ts = c.ts or (datetime.fromisoformat(last) if last else datetime.now(timezone.utc))
    ok = {}
    for signal, value in (c.values | scored).items():
        r = Reading.model_construct(crew_id=c.crew_id, ts=ts, signal=signal, value=value,
                                    source="app", provenance="simulated")
        ok[signal] = ingest(r.model_dump_json(), "checkin") is not None
    await broadcast(c.crew_id)
    return {"accepted": [s for s, v in ok.items() if v], "rejected": [s for s, v in ok.items() if not v]}


@app.post("/game-sessions")
async def save_game_session(request: Request):
    try:
        # Manual validation keeps NaN/inf error replies JSON-safe (no invalid input echoed into a response).
        c = GameSession.model_validate(await request.json())
    except ValueError:
        raise HTTPException(422, "Invalid game session: check game ID, crew, finite results and aware timestamp") from None
    last = store.span(c.crew_id)[1]
    ts = c.ts or (datetime.fromisoformat(last) if last else datetime.now(timezone.utc))
    if c.ts:
        c.ts = c.ts.astimezone(timezone.utc)
    body = c.model_dump(mode="json")
    try:
        created = store.add_game_session(body, ts.astimezone(timezone.utc).isoformat())
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return {"saved": str(c.session_id), "created": created, "label": GAME_LABEL}


@app.get("/crew/{crew_id}/game-sessions")
def game_history(crew_id: str, limit: int = Query(20, ge=1, le=100)):
    return {"crew_id": crew_id, "sessions": store.game_sessions(crew_id, limit), "label": GAME_LABEL}


@app.websocket("/ws")
async def ws_status(ws: WebSocket):
    """Pushes a crew member's full status after every reading stored for them."""
    await ws.accept()
    sockets.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        sockets.discard(ws)
