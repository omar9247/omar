"""Data layer: SQLite (plan 3.5 data decomposition). One connection shared by the MQTT thread and the API, behind a
lock. Threshold and Pattern live in contract/thresholds.yaml, not here. Invalid messages go to `reject` and are
dropped (plan 3.6 pipeline), so Reading holds only valid readings."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from contract.schema import Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS reading (
  crew_id TEXT NOT NULL, signal TEXT NOT NULL, ts TEXT NOT NULL,
  value REAL NOT NULL, source TEXT NOT NULL, provenance TEXT NOT NULL,
  PRIMARY KEY (crew_id, signal, ts));
CREATE TABLE IF NOT EXISTS reject (
  id INTEGER PRIMARY KEY, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  topic TEXT, payload TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS mission (
  id INTEGER PRIMARY KEY, preset TEXT NOT NULL, comms_delay_s REAL NOT NULL, dose_rate_mgy_day REAL NOT NULL);
CREATE TABLE IF NOT EXISTS crew_member (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, mission_id INTEGER NOT NULL REFERENCES mission(id));
CREATE TABLE IF NOT EXISTS baseline (
  crew_id TEXT NOT NULL, signal TEXT NOT NULL, mean REAL NOT NULL, sd REAL NOT NULL,
  window_days INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (crew_id, signal));
CREATE TABLE IF NOT EXISTS alert (
  id INTEGER PRIMARY KEY, crew_id TEXT NOT NULL, pattern_id TEXT, signal TEXT, level TEXT NOT NULL,
  signals_fired TEXT NOT NULL, ts TEXT NOT NULL, last_ts TEXT NOT NULL,
  active INTEGER NOT NULL, acknowledged_at TEXT);
CREATE TABLE IF NOT EXISTS report (
  id INTEGER PRIMARY KEY, crew_id TEXT NOT NULL, alert_id INTEGER, body TEXT NOT NULL,
  created_at REAL NOT NULL, release_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS showcase_crew (crew_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS game_session (
  session_id TEXT PRIMARY KEY, crew_id TEXT NOT NULL, game_id TEXT NOT NULL, ts TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.executescript(SCHEMA)

    def q(self, sql: str, *args) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def add(self, r: Reading) -> None:
        # first reading of a new crew member registers them on the current mission
        self.q("INSERT OR IGNORE INTO crew_member VALUES (?, ?, 1)", r.crew_id, r.crew_id)
        # ts stored as UTC ISO text so it sorts as text. REPLACE: QoS 1 may deliver a message twice.
        self.q("INSERT OR REPLACE INTO reading VALUES (?,?,?,?,?,?)", r.crew_id, r.signal,
               r.ts.astimezone(timezone.utc).isoformat(), r.value, r.source, r.provenance)

    def reject(self, topic: str | None, payload: str, error: str) -> None:
        self.q("INSERT INTO reject (topic, payload, error) VALUES (?,?,?)", topic, payload, error)

    def count(self, table: str = "reading") -> int:
        return self.q(f"SELECT COUNT(*) FROM {table}")[0][0]

    def crews(self) -> list[str]:
        return [r[0] for r in self.q("SELECT id FROM crew_member ORDER BY 1")]

    def clear(self, crew_id: str, include_games: bool = True) -> None:
        for table in ("reading", "alert", "report", "baseline"):
            self.q(f"DELETE FROM {table} WHERE crew_id = ?", crew_id)
        if include_games:
            self.q("DELETE FROM game_session WHERE crew_id = ?", crew_id)
        self.q("DELETE FROM crew_member WHERE id = ?", crew_id)

    def reset_showcase(self, crew_id: str, include_games: bool = False) -> None:
        """Claim a new demo ID, or reset only a persistently owned demo; never adopt existing data."""
        if include_games:
            raise ValueError("showcase resets must preserve games")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                owned = self.db.execute("SELECT 1 FROM showcase_crew WHERE crew_id = ?", (crew_id,)).fetchone()
                if not owned:
                    existing = self.db.execute("SELECT 1 FROM crew_member WHERE id = ?", (crew_id,)).fetchone()
                    for table in ("reading", "alert", "report", "baseline", "game_session"):
                        existing = existing or self.db.execute(f"SELECT 1 FROM {table} WHERE crew_id = ? LIMIT 1", (crew_id,)).fetchone()
                    if existing:
                        raise ValueError(f"{crew_id} already has non-showcase data; nothing was reset")
                    self.db.execute("INSERT INTO showcase_crew VALUES (?)", (crew_id,))
                for table in ("reading", "alert", "report", "baseline"):
                    self.db.execute(f"DELETE FROM {table} WHERE crew_id = ?", (crew_id,))
                self.db.execute("DELETE FROM crew_member WHERE id = ?", (crew_id,))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def add_game_session(self, body: dict, ts: str) -> bool:
        """A UUID is immutable: retry identical data, but never overwrite another session/crew."""
        text = json.dumps(body, sort_keys=True, allow_nan=False)
        with self.lock:
            old = self.db.execute("SELECT body FROM game_session WHERE session_id = ?", (body["session_id"],)).fetchone()
            if old:
                if old[0] != text:
                    raise ValueError("session_id already belongs to different game data")
                return False
            self.db.execute("INSERT INTO game_session (session_id, crew_id, game_id, ts, body) VALUES (?,?,?,?,?)",
                            (body["session_id"], body["crew_id"], body["game_id"], ts, text))
        return True

    def game_sessions(self, crew_id: str, limit: int = 20) -> list[dict]:
        return [json.loads(r["body"]) | {"ts": r["ts"], "received_at": r["received_at"], "provenance": "simulated"}
                for r in self.q("SELECT * FROM game_session WHERE crew_id = ? ORDER BY rowid DESC LIMIT ?", crew_id, limit)]

    def mission(self) -> sqlite3.Row | None:
        rows = self.q("SELECT * FROM mission WHERE id = 1")
        return rows[0] if rows else None

    def set_mission(self, preset: str, comms_delay_s: float, dose_rate_mgy_day: float) -> None:
        self.q("INSERT OR REPLACE INTO mission VALUES (1, ?, ?, ?)", preset, comms_delay_s, dose_rate_mgy_day)

    def sync_alerts(self, crew_id: str, live: list[dict], ts: str) -> list[tuple[int, dict]]:
        """One stored alert per episode of a pattern (pattern_id) or a red signal (signal): opened when it starts,
        kept up to date while it lasts, set inactive when it stops. Returns (id, live alert) for each new one."""
        new = []
        with self.lock:
            open_ = {(r[1], r[2]): r[0] for r in self.db.execute(
                "SELECT id, pattern_id, signal FROM alert WHERE crew_id = ? AND active = 1", (crew_id,))}
            for a in live:
                key, fired = (a["id"], a.get("signal")), json.dumps(a["fired"])
                if key in open_:
                    self.db.execute("UPDATE alert SET level = ?, signals_fired = ?, last_ts = ? WHERE id = ?",
                                    (a["level"], fired, ts, open_.pop(key)))
                else:
                    new.append((self.db.execute(
                        "INSERT INTO alert (crew_id, pattern_id, signal, level, signals_fired, ts, last_ts, active)"
                        " VALUES (?,?,?,?,?,?,?,1)", (crew_id, *key, a["level"], fired, ts, ts)).lastrowid, a))
            for alert_id in open_.values():
                self.db.execute("UPDATE alert SET active = 0 WHERE id = ?", (alert_id,))
        return new

    def all_alerts(self, crew_id: str) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM alert WHERE crew_id = ? ORDER BY id", crew_id)]

    def open_alerts(self, crew_id: str) -> list[dict]:
        """Alerts still matching, or no longer matching but not yet acknowledged."""
        return [dict(r) for r in self.q("SELECT * FROM alert WHERE crew_id = ? AND (active = 1 OR acknowledged_at"
                                         " IS NULL) ORDER BY id", crew_id)]

    def ack(self, alert_id: int) -> str | None:
        """Returns the alert's crew_id, or None if there is no such alert."""
        rows = self.q("SELECT crew_id FROM alert WHERE id = ?", alert_id)
        self.q("UPDATE alert SET acknowledged_at = COALESCE(acknowledged_at, ?) WHERE id = ?",
               datetime.now(timezone.utc).isoformat(), alert_id)
        return rows[0][0] if rows else None

    def queue_report(self, crew_id: str, alert_id: int, body: dict, created: float, delay_s: float) -> None:
        self.q("INSERT INTO report (crew_id, alert_id, body, created_at, release_at) VALUES (?,?,?,?,?)",
               crew_id, alert_id, json.dumps(body), created, created + delay_s)

    def reports(self, now: float) -> tuple[list[dict], list[dict]]:
        """(released, pending) ground reports at wall-clock time `now`."""
        rows = self.q("SELECT * FROM report ORDER BY id")
        released = [json.loads(r["body"]) | {"report_id": r["id"]} for r in rows if r["release_at"] <= now]
        pending = [{"report_id": r["id"], "crew_id": r["crew_id"], "release_in_s": round(r["release_at"] - now, 1)}
                   for r in rows if r["release_at"] > now]
        return released, pending

    def latest(self, crew_id: str, until: str = "9999") -> dict[str, dict]:
        """Newest reading per signal at or before `until` (UTC ISO text)."""
        # SQLite returns the other columns from the row that holds MAX(ts)
        rows = self.q("SELECT signal, value, provenance, MAX(ts) AS ts FROM reading"
                      " WHERE crew_id = ? AND ts <= ? GROUP BY signal", crew_id, until)
        return {r["signal"]: dict(r) for r in rows}

    def series(self, crew_id: str, signal: str, since: str) -> list[dict]:
        return [dict(r) for r in self.q("SELECT ts, value, provenance FROM reading WHERE crew_id = ? AND signal = ?"
                                         " AND ts >= ? ORDER BY ts", crew_id, signal, since)]

    def total(self, crew_id: str, signal: str) -> float:
        return self.q("SELECT COALESCE(SUM(value), 0) FROM reading WHERE crew_id = ? AND signal = ?",
                      crew_id, signal)[0][0]

    def span(self, crew_id: str) -> tuple[str | None, str | None]:
        return tuple(self.q("SELECT MIN(ts), MAX(ts) FROM reading WHERE crew_id = ?", crew_id)[0])

    def baseline_window(self, crew_id: str, days: int) -> dict[str, list[float]]:
        """Readings per signal in the crew member's first `days` days; {} until those days have passed."""
        first, last = self.span(crew_id)
        if first is None:
            return {}
        cutoff = (datetime.fromisoformat(first) + timedelta(days=days)).isoformat()
        if last < cutoff:
            return {}
        values: dict[str, list[float]] = {}
        for r in self.q("SELECT signal, value FROM reading WHERE crew_id = ? AND ts < ?", crew_id, cutoff):
            values.setdefault(r["signal"], []).append(r["value"])
        return values

    def baselines(self, crew_id: str) -> dict[str, tuple[float, float]]:
        return {r["signal"]: (r["mean"], r["sd"]) for r in self.q(
            "SELECT signal, mean, sd FROM baseline WHERE crew_id = ?", crew_id)}

    def save_baselines(self, crew_id: str, stats: dict[str, tuple[float, float]], window_days: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for signal, (m, sd) in stats.items():
            self.q("INSERT OR REPLACE INTO baseline VALUES (?,?,?,?,?,?)", crew_id, signal, m, sd, window_days, now)
