"""
Event Logger — CSV-based logging for fall detection events.

Logs events to a human-readable CSV file for easy inspection.
SQLite version is commented out below for future backend porting.

Usage (as module):
    from event_logger import EventLogger

    logger = EventLogger("events.csv")
    logger.log_event("fall_detected", confidence=0.92, details="2 consecutive windows")
    events = logger.get_recent_events(limit=10)
"""

import csv
import time
from pathlib import Path
from typing import List, Dict, Optional


class EventLogger:
    """Logs detection events to a local CSV file."""

    CSV_HEADERS = ['id', 'timestamp', 'datetime', 'event_type', 'confidence', 'details']

    def __init__(self, csv_path: str = "events.csv"):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._event_id = 0

        # If file exists, count existing rows to continue ID sequence
        if self.csv_path.exists():
            with open(self.csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._event_id = max(self._event_id, int(row.get('id', 0)))

        # Write header if file is new
        if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

        print(f"[event_logger] CSV log: {self.csv_path}")

    def log_event(self, event_type: str, confidence: float = 0.0,
                  details: str = "", silent: bool = False):
        """Log a detection event to CSV."""
        ts = time.time()
        human_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        self._event_id += 1

        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                self._event_id,
                f"{ts:.3f}",
                human_time,
                event_type,
                f"{confidence:.4f}",
                details,
            ])

        if not silent:
            print(f"[event] {human_time} | {event_type} "
                  f"(conf={confidence:.1%}) {details}")

    def get_recent_events(self, limit: int = 20) -> List[Dict]:
        """Return the most recent events from the CSV."""
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Return last `limit` rows in reverse order (newest first)
        return rows[-limit:][::-1]

    def get_events_since(self, since_timestamp: float) -> List[Dict]:
        """Return events since a given Unix timestamp."""
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            return [row for row in reader
                    if float(row.get('timestamp', 0)) >= since_timestamp]

    def close(self):
        """No-op for CSV (file handles are opened/closed per write)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# =============================================================================
# SQLITE VERSION (commented out for future backend porting)
# =============================================================================
#
# import sqlite3
#
# class EventLoggerSQLite:
#     """Logs detection events to a local SQLite database."""
#
#     def __init__(self, db_path: str = "events.db"):
#         self.db_path = Path(db_path)
#         self.db_path.parent.mkdir(parents=True, exist_ok=True)
#         self._conn = sqlite3.connect(str(self.db_path))
#         self._conn.row_factory = sqlite3.Row
#         self._create_table()
#         print(f"[event_logger] Database: {self.db_path}")
#
#     def _create_table(self):
#         self._conn.execute("""
#             CREATE TABLE IF NOT EXISTS events (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 timestamp REAL NOT NULL,
#                 event_type TEXT NOT NULL,
#                 confidence REAL,
#                 details TEXT
#             )
#         """)
#         self._conn.commit()
#
#     def log_event(self, event_type: str, confidence: float = 0.0,
#                   details: str = "", silent: bool = False):
#         """Log a detection event."""
#         ts = time.time()
#         self._conn.execute(
#             "INSERT INTO events (timestamp, event_type, confidence, details) "
#             "VALUES (?, ?, ?, ?)",
#             (ts, event_type, confidence, details),
#         )
#         self._conn.commit()
#         if not silent:
#             human_time = time.strftime("%H:%M:%S", time.localtime(ts))
#             print(f"[event] {human_time} | {event_type} "
#                   f"(conf={confidence:.1%}) {details}")
#
#     def get_recent_events(self, limit: int = 20):
#         """Return the most recent events."""
#         rows = self._conn.execute(
#             "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
#         ).fetchall()
#         return [dict(r) for r in rows]
#
#     def get_events_since(self, since_timestamp: float):
#         """Return events since a given Unix timestamp."""
#         rows = self._conn.execute(
#             "SELECT * FROM events WHERE timestamp >= ? ORDER BY timestamp ASC",
#             (since_timestamp,),
#         ).fetchall()
#         return [dict(r) for r in rows]
#
#     def close(self):
#         self._conn.close()
#
#     def __enter__(self):
#         return self
#
#     def __exit__(self, *args):
#         self.close()
