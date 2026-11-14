"""SQLite persistence: players, sessions, baselines, physiology and alerts.

The Pygbag web build keeps SQLite in memory and mirrors a snapshot to browser
``localStorage`` after every commit, so progress survives page reloads.
"""

import base64
import datetime as _dt
import json
import os
import re
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

from config import DB_PATH

IS_WEB = sys.platform == "emscripten"
WEB_DB_KEY = "lunar_arcade_hub_db_v1"
WEB_SQL_KEY = "lunar_arcade_hub_sql_v1"
_CREW_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _crew_namespace(search):
    """Return a safe crew namespace; no query means standalone storage."""
    query = parse_qs(urlsplit(search or "").query, keep_blank_values=True)
    if "crew" not in query:
        return None
    crew = query["crew"][0]
    return crew if _CREW_RE.fullmatch(crew) else "!invalid"


def _key_for_query(base, search):
    namespace = _crew_namespace(search)
    return base if namespace is None else f"{base}:crew:{namespace}"


def _browser_search():
    try:
        from platform import window
        return str(window.location.search or "")
    except Exception:
        return ""


def _web_key(base):
    return _key_for_query(base, _browser_search())


def _browser_storage():
    if not IS_WEB:
        return None
    try:
        from platform import window
        return window.localStorage
    except Exception:
        return None

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    game_id TEXT NOT NULL,
    game_title TEXT NOT NULL,
    played_at TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    accuracy REAL NOT NULL DEFAULT 0,
    mistakes INTEGER NOT NULL DEFAULT 0,
    hits INTEGER NOT NULL DEFAULT 0,
    avg_reaction_ms REAL,
    duration REAL NOT NULL DEFAULT 0,
    extra TEXT,
    FOREIGN KEY (player_id) REFERENCES players(id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_player_game
    ON sessions(player_id, game_id, played_at);

CREATE TABLE IF NOT EXISTS baselines (
    game_id TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'normal',
    metric TEXT,
    direction TEXT,
    original_value REAL,
    baseline_value REAL,
    rolling_avg REAL,
    samples INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'none',
    updated_at TEXT,
    PRIMARY KEY (game_id, difficulty)
);
CREATE TABLE IF NOT EXISTS baseline_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    old_value REAL,
    new_value REAL,
    reason TEXT
);
CREATE TABLE IF NOT EXISTS physiology (
    date TEXT PRIMARY KEY,
    sleep_hours REAL,
    co2_mmhg REAL,
    hrv_ms REAL,
    sleep_efficiency REAL,
    mood INTEGER,
    hydration REAL,
    stress INTEGER,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    game_id TEXT NOT NULL,
    level TEXT NOT NULL,
    deterioration REAL,
    multisystem INTEGER NOT NULL DEFAULT 0,
    physiology TEXT,
    message TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wellbeing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    answers TEXT,
    scores TEXT,
    feedback TEXT,
    FOREIGN KEY (player_id) REFERENCES players(id)
);
CREATE INDEX IF NOT EXISTS idx_wellbeing_player
    ON wellbeing(player_id, status, created_at);
"""

SESSION_MIGRATIONS = {
    "difficulty": "TEXT",
    "valid": "INTEGER DEFAULT 1",
    "metric_value": "REAL",
    "baseline_value": "REAL",
    "deterioration": "REAL",
    "alert_level": "TEXT",
    "status": "TEXT",
    "feedback": "TEXT",
}


class Database:
    def __init__(self, path=DB_PATH, username="Cadet"):
        self.path = path
        self._storage = _browser_storage()
        self._web = self._storage is not None
        if self._web:
            self.conn = sqlite3.connect(":memory:")
            self._restore_web()
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self._commit()
        self.player_id = self._ensure_player(username)

    def _restore_web(self):
        """Restore the last browser snapshot, falling back to a SQL dump."""
        try:
            raw = self._storage.getItem(_web_key(WEB_DB_KEY))
        except Exception:
            raw = None
        if raw:
            try:
                self.conn.deserialize(base64.b64decode(raw))
                return
            except Exception:
                self.conn = sqlite3.connect(":memory:")
        try:
            dump = self._storage.getItem(_web_key(WEB_SQL_KEY))
            if dump:
                self.conn.executescript(dump)
        except Exception:
            pass

    def _commit(self):
        """Commit and mirror browser state to durable localStorage."""
        self.conn.commit()
        if not self._web:
            return
        try:
            snapshot = self.conn.serialize()
            self._storage.setItem(
                _web_key(WEB_DB_KEY), base64.b64encode(snapshot).decode("ascii"))
        except Exception:
            # Older SQLite/Pyodide builds may not expose serialize().
            try:
                dump = "\n".join(self.conn.iterdump())
                self._storage.setItem(_web_key(WEB_SQL_KEY), dump)
            except Exception:
                pass

    def _migrate(self):
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(sessions)")}
        for name, sql_type in SESSION_MIGRATIONS.items():
            if name not in cols:
                self.conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}")

    # ------------------------------------------------------------ players
    def _ensure_player(self, username):
        row = self.conn.execute(
            "SELECT id FROM players ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            return row["id"]
        now = _dt.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "INSERT INTO players (username, created_at) VALUES (?, ?)",
            (username, now),
        )
        self._commit()
        return cur.lastrowid

    def get_username(self):
        row = self.conn.execute(
            "SELECT username FROM players WHERE id = ?", (self.player_id,)
        ).fetchone()
        return row["username"] if row else "Cadet"

    def profile_info(self):
        row = self.conn.execute(
            "SELECT username, created_at FROM players WHERE id = ?",
            (self.player_id,),
        ).fetchone()
        return dict(row) if row else {"username": "Cadet", "created_at": ""}

    def set_username(self, username):
        username = (username or "").strip()[:24] or "Cadet"
        self.conn.execute(
            "UPDATE players SET username = ? WHERE id = ?",
            (username, self.player_id),
        )
        self._commit()
        return username

    # ----------------------------------------------------------- sessions
    def record(self, game_id, game_title, result, evaluation=None,
               feedback=None):
        """Persist one completed game session with its assessment metadata."""
        extra = result.get("extra") or {}
        ev = evaluation or {}
        difficulty = (ev.get("difficulty")
                      or str(extra.get("difficulty", "normal")).lower())
        self.conn.execute(
            """INSERT INTO sessions
               (player_id, game_id, game_title, played_at, score, accuracy,
                mistakes, hits, avg_reaction_ms, duration, extra, difficulty,
                valid, metric_value, baseline_value, deterioration,
                alert_level, status, feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.player_id,
                game_id,
                game_title,
                _dt.datetime.now().isoformat(timespec="seconds"),
                int(result.get("score", 0)),
                float(result.get("accuracy", 0.0)),
                int(result.get("mistakes", 0)),
                int(result.get("hits", 0)),
                (float(result["avg_reaction_ms"])
                 if result.get("avg_reaction_ms") is not None else None),
                float(result.get("duration", 0.0)),
                json.dumps(extra),
                difficulty,
                1 if ev.get("valid", True) else 0,
                ev.get("value"),
                ev.get("baseline_value"),
                ev.get("deterioration"),
                ev.get("level"),
                ev.get("status"),
                json.dumps(feedback) if feedback else None,
            ),
        )
        self._commit()
        return self.conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    def _rows(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def recent(self, limit=6):
        return self._rows(
            "SELECT * FROM sessions WHERE player_id = ? "
            "ORDER BY id DESC LIMIT ?", (self.player_id, limit)
        )

    def latest_session(self, game_id):
        rows = self._rows(
            "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
            "ORDER BY id DESC LIMIT 1", (self.player_id, game_id)
        )
        return rows[0] if rows else None

    def last_valid_session(self, game_id, difficulty=None):
        if difficulty:
            rows = self._rows(
                "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
                "AND difficulty = ? AND valid = 1 ORDER BY id DESC LIMIT 1",
                (self.player_id, game_id, difficulty),
            )
        else:
            rows = self._rows(
                "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
                "AND valid = 1 ORDER BY id DESC LIMIT 1",
                (self.player_id, game_id),
            )
        return rows[0] if rows else None

    def history(self, game_id=None, limit=40):
        if game_id:
            rows = self._rows(
                "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
                "ORDER BY id DESC LIMIT ?", (self.player_id, game_id, limit)
            )
        else:
            rows = self._rows(
                "SELECT * FROM sessions WHERE player_id = ? "
                "ORDER BY id DESC LIMIT ?", (self.player_id, limit)
            )
        return list(reversed(rows))

    def recent_valid_values(self, game_id, difficulty=None, limit=5):
        if difficulty:
            rows = self._rows(
                "SELECT metric_value FROM sessions WHERE player_id = ? "
                "AND game_id = ? AND difficulty = ? AND valid = 1 "
                "AND metric_value IS NOT NULL ORDER BY id DESC LIMIT ?",
                (self.player_id, game_id, difficulty, limit),
            )
        else:
            rows = self._rows(
                "SELECT metric_value FROM sessions WHERE player_id = ? "
                "AND game_id = ? AND valid = 1 AND metric_value IS NOT NULL "
                "ORDER BY id DESC LIMIT ?", (self.player_id, game_id, limit)
            )
        return [r["metric_value"] for r in reversed(rows)]

    def metric_history(self, game_id, difficulty=None, limit=14):
        if difficulty:
            rows = self._rows(
                "SELECT metric_value, alert_level FROM sessions "
                "WHERE player_id = ? AND game_id = ? AND difficulty = ? "
                "AND valid = 1 AND metric_value IS NOT NULL "
                "ORDER BY id DESC LIMIT ?",
                (self.player_id, game_id, difficulty, limit),
            )
        else:
            rows = self._rows(
                "SELECT metric_value, alert_level FROM sessions "
                "WHERE player_id = ? AND game_id = ? AND valid = 1 "
                "AND metric_value IS NOT NULL ORDER BY id DESC LIMIT ?",
                (self.player_id, game_id, limit),
            )
        return list(reversed(rows))

    def best_score(self, game_id=None):
        if game_id:
            row = self.conn.execute(
                "SELECT MAX(score) AS m FROM sessions "
                "WHERE player_id = ? AND game_id = ?",
                (self.player_id, game_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT MAX(score) AS m FROM sessions WHERE player_id = ?",
                (self.player_id,),
            ).fetchone()
        return int(row["m"] or 0)

    def totals(self):
        row = self.conn.execute(
            """SELECT COUNT(*) AS games, COALESCE(SUM(duration), 0) AS seconds,
                      COALESCE(AVG(accuracy), 0) AS accuracy,
                      COALESCE(SUM(hits), 0) AS hits,
                      COALESCE(SUM(mistakes), 0) AS mistakes
               FROM sessions WHERE player_id = ?""",
            (self.player_id,),
        ).fetchone()
        return {
            "games": row["games"],
            "seconds": row["seconds"],
            "accuracy": row["accuracy"],
            "hits": row["hits"],
            "mistakes": row["mistakes"],
            "best": self.best_score(),
        }

    def per_game(self):
        rows = self._rows(
            """SELECT game_id, COUNT(*) AS plays, MAX(score) AS best,
                      AVG(score) AS avg_score, AVG(accuracy) AS avg_accuracy,
                      MAX(played_at) AS last_played
               FROM sessions WHERE player_id = ? GROUP BY game_id""",
            (self.player_id,),
        )
        return {r["game_id"]: r for r in rows}

    def game_history(self, game_id, limit=30):
        return self.history(game_id, limit)

    def comparison(self, game_id):
        """Latest session vs. the one before it, for the same game."""
        rows = self._rows(
            "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
            "ORDER BY id DESC LIMIT 2", (self.player_id, game_id)
        )
        latest = rows[0] if rows else None
        previous = None
        if latest is not None:
            # Never compare scores across difficulties (Speed Click).
            same = self._rows(
                "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
                "AND COALESCE(difficulty, 'normal') = ? AND id < ? "
                "ORDER BY id DESC LIMIT 1",
                (self.player_id, game_id, latest.get("difficulty") or "normal",
                 latest["id"]),
            )
            previous = same[0] if same else None
        best = None
        if rows:
            best = self.conn.execute(
                "SELECT * FROM sessions WHERE player_id = ? AND game_id = ? "
                "ORDER BY score DESC, accuracy DESC LIMIT 1",
                (self.player_id, game_id),
            ).fetchone()
            best = dict(best) if best else None
        return latest, previous, best

    def daily_activity(self, days=14):
        today = _dt.date.today()
        start = (today - _dt.timedelta(days=days - 1)).isoformat()
        rows = self._rows(
            "SELECT substr(played_at, 1, 10) AS day, COUNT(*) AS n "
            "FROM sessions WHERE player_id = ? AND substr(played_at, 1, 10) >= ? "
            "GROUP BY day", (self.player_id, start)
        )
        counts = {r["day"]: r["n"] for r in rows}
        return [
            ((today - _dt.timedelta(days=days - 1 - i)).isoformat(),
             counts.get((today - _dt.timedelta(days=days - 1 - i)).isoformat(), 0))
            for i in range(days)
        ]

    # ---------------------------------------------------------- baselines
    def get_baseline(self, game_id, difficulty=None):
        if difficulty:
            row = self.conn.execute(
                "SELECT * FROM baselines WHERE game_id = ? AND difficulty = ?",
                (game_id, difficulty),
            ).fetchone()
            if row:
                return dict(row)
        row = self.conn.execute(
            "SELECT * FROM baselines WHERE game_id = ? "
            "ORDER BY samples DESC LIMIT 1", (game_id,)
        ).fetchone()
        return dict(row) if row else None

    def all_baselines(self):
        rows = self._rows("SELECT * FROM baselines ORDER BY game_id, difficulty")
        return {(r["game_id"], r["difficulty"]): r for r in rows}

    def upsert_baseline(self, game_id, difficulty, metric, direction,
                        original_value, baseline_value, rolling_avg, samples,
                        status):
        now = _dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO baselines
               (game_id, difficulty, metric, direction, original_value,
                baseline_value, rolling_avg, samples, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(game_id, difficulty) DO UPDATE SET
                 metric=excluded.metric, direction=excluded.direction,
                 original_value=excluded.original_value,
                 baseline_value=excluded.baseline_value,
                 rolling_avg=excluded.rolling_avg, samples=excluded.samples,
                 status=excluded.status, updated_at=excluded.updated_at""",
            (game_id, difficulty, metric, direction, original_value,
             baseline_value, rolling_avg, samples, status, now),
        )
        self._commit()

    def add_baseline_history(self, game_id, difficulty, old_value, new_value,
                             reason):
        self.conn.execute(
            """INSERT INTO baseline_history
               (game_id, difficulty, changed_at, old_value, new_value, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, difficulty,
             _dt.datetime.now().isoformat(timespec="seconds"),
             old_value, new_value, reason),
        )
        self._commit()

    def baseline_history(self, game_id=None, limit=20):
        if game_id:
            return self._rows(
                "SELECT * FROM baseline_history WHERE game_id = ? "
                "ORDER BY id DESC LIMIT ?", (game_id, limit))
        return self._rows(
            "SELECT * FROM baseline_history ORDER BY id DESC LIMIT ?", (limit,))

    def has_baselines(self):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM baselines").fetchone()
        return row["n"] > 0

    def all_sessions_asc(self):
        return self._rows(
            "SELECT * FROM sessions WHERE player_id = ? ORDER BY id ASC",
            (self.player_id,),
        )

    def update_session_metrics(self, session_id, valid, metric_value,
                               baseline_value=None, deterioration=None,
                               alert_level=None, status=None, difficulty=None):
        self.conn.execute(
            """UPDATE sessions SET valid = ?, metric_value = ?,
               baseline_value = ?, deterioration = ?, alert_level = ?,
               status = ?, difficulty = COALESCE(?, difficulty)
               WHERE id = ?""",
            (1 if valid else 0, metric_value, baseline_value, deterioration,
             alert_level, status, difficulty, session_id),
        )
        self._commit()

    # -------------------------------------------------------- physiology
    def get_physiology(self, date=None):
        if date:
            row = self.conn.execute(
                "SELECT * FROM physiology WHERE date = ?", (date,)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM physiology WHERE date <= ? "
                "ORDER BY date DESC LIMIT 1",
                (_dt.date.today().isoformat(),),
            ).fetchone()
        return dict(row) if row else None

    def save_physiology(self, data, date=None):
        date = date or _dt.date.today().isoformat()
        now = _dt.datetime.now().isoformat(timespec="seconds")
        keys = ["sleep_hours", "co2_mmhg", "hrv_ms", "sleep_efficiency",
                "mood", "hydration", "stress"]
        values = [data.get(k) for k in keys]
        self.conn.execute(
            """INSERT INTO physiology
               (date, sleep_hours, co2_mmhg, hrv_ms, sleep_efficiency, mood,
                hydration, stress, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                 sleep_hours=excluded.sleep_hours, co2_mmhg=excluded.co2_mmhg,
                 hrv_ms=excluded.hrv_ms,
                 sleep_efficiency=excluded.sleep_efficiency,
                 mood=excluded.mood, hydration=excluded.hydration,
                 stress=excluded.stress, updated_at=excluded.updated_at""",
            (date, *values, now),
        )
        self._commit()
        return date

    def hrv_history(self, limit=14):
        rows = self._rows(
            "SELECT hrv_ms FROM physiology WHERE hrv_ms IS NOT NULL "
            "ORDER BY date DESC LIMIT ?", (limit,))
        return [r["hrv_ms"] for r in rows]

    # --------------------------------------------------------- wellbeing
    @staticmethod
    def _decode_wellbeing(row):
        row = dict(row)
        for field in ("answers", "scores", "feedback"):
            raw = row.get(field)
            try:
                row[field + "_data"] = json.loads(raw) if raw else None
            except (TypeError, ValueError):
                row[field + "_data"] = None
        return row

    def save_wellbeing_draft(self, answers):
        """Store one editable draft per player; submitted rows are untouched."""
        now = _dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "DELETE FROM wellbeing WHERE player_id = ? AND status = 'draft'",
            (self.player_id,),
        )
        self.conn.execute(
            """INSERT INTO wellbeing
               (player_id, created_at, status, answers, scores, feedback)
               VALUES (?, ?, 'draft', ?, NULL, NULL)""",
            (self.player_id, now, json.dumps(answers)),
        )
        self._commit()
        return now

    def wellbeing_draft(self):
        rows = self._rows(
            "SELECT * FROM wellbeing WHERE player_id = ? AND status = 'draft' "
            "ORDER BY id DESC LIMIT 1", (self.player_id,))
        return self._decode_wellbeing(rows[0]) if rows else None

    def delete_wellbeing_draft(self):
        self.conn.execute(
            "DELETE FROM wellbeing WHERE player_id = ? AND status = 'draft'",
            (self.player_id,))
        self._commit()

    def submit_wellbeing(self, answers, scores, feedback):
        """Insert a completed, timestamped check-in; never overwrite history."""
        now = _dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO wellbeing
               (player_id, created_at, status, answers, scores, feedback)
               VALUES (?, ?, 'submitted', ?, ?, ?)""",
            (self.player_id, now, json.dumps(answers),
             json.dumps(scores), json.dumps(feedback)),
        )
        self.conn.execute(
            "DELETE FROM wellbeing WHERE player_id = ? AND status = 'draft'",
            (self.player_id,),
        )
        self._commit()
        return now

    def wellbeing_submissions(self, limit=30):
        rows = self._rows(
            "SELECT * FROM wellbeing WHERE player_id = ? "
            "AND status = 'submitted' ORDER BY id DESC LIMIT ?",
            (self.player_id, limit))
        return [self._decode_wellbeing(r) for r in rows]

    def wellbeing_count(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM wellbeing WHERE player_id = ? "
            "AND status = 'submitted'", (self.player_id,)).fetchone()
        return row["n"]

    # ------------------------------------------------------------ alerts
    def add_alert(self, session_id, game_id, level, deterioration,
                  multisystem, physiology, message):
        self.conn.execute(
            """INSERT INTO alerts
               (session_id, game_id, level, deterioration, multisystem,
                physiology, message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, game_id, level, deterioration,
             1 if multisystem else 0, json.dumps(physiology or {}),
             message, _dt.datetime.now().isoformat(timespec="seconds")),
        )
        self._commit()

    def recent_alerts(self, limit=5):
        return self._rows(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))

    def alert_count(self):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM alerts").fetchone()
        return row["n"]

    def reset_progress(self):
        for table in ("sessions", "baselines", "baseline_history", "alerts",
                      "wellbeing"):
            self.conn.execute(f"DELETE FROM {table}")
        self._commit()

    def close(self):
        self._commit()
        self.conn.close()
