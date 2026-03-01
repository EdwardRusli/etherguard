"""
Event Logger — SQLite-based logging for fall detection events.

Usage (as module):
    from event_logger import EventLogger

    logger = EventLogger("../data/events.db")
    logger.log_event("fall_detected", confidence=0.92, details="2 consecutive windows")
    events = logger.get_recent_events(limit=10)
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional


class EventLogger:
    """Logs detection events to a local SQLite database."""

    def __init__(self, db_path: str = "../data/events.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_table()
        print(f"[event_logger] Database: {self.db_path}")

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                confidence REAL,
                details TEXT
            )
        """)
        self._conn.commit()

    def log_event(self, event_type: str, confidence: float = 0.0,
                  details: str = "", silent: bool = False):
        """Log a detection event."""
        ts = time.time()
        self._conn.execute(
            "INSERT INTO events (timestamp, event_type, confidence, details) "
            "VALUES (?, ?, ?, ?)",
            (ts, event_type, confidence, details),
        )
        self._conn.commit()
        if not silent:
            human_time = time.strftime("%H:%M:%S", time.localtime(ts))
            print(f"[event] {human_time} | {event_type} "
                  f"(conf={confidence:.1%}) {details}")

    def get_recent_events(self, limit: int = 20):
        """Return the most recent events."""
        rows = self._conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_events_since(self, since_timestamp: float):
        """Return events since a given Unix timestamp."""
        rows = self._conn.execute(
            "SELECT * FROM events WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since_timestamp,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
