from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str = "runtime.db"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    user_input TEXT NOT NULL,
                    state TEXT NOT NULL,
                    assistant_output TEXT,
                    provider_calls INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    terminal_at TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_run(self, run_id: str, user_input: str) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO runs(run_id,user_input,state,created_at) VALUES(?,?,?,?)",
                (run_id, user_input, "accepted", self._now()),
            )

    def update_state(self, run_id: str, state: str, output: str | None = None, provider_calls: int | None = None) -> None:
        with self._lock, self.conn:
            if state in {"completed", "rejected", "cancelled", "timed_out", "failed"}:
                stored_output = output if state == "completed" else None
                self.conn.execute(
                    "UPDATE runs SET state=?, assistant_output=?, provider_calls=COALESCE(?,provider_calls), terminal_at=? WHERE run_id=? AND state NOT IN ('completed','rejected','cancelled','timed_out','failed')",
                    (state, stored_output, provider_calls, self._now(), run_id),
                )
            else:
                self.conn.execute(
                    "UPDATE runs SET state=?, provider_calls=COALESCE(?,provider_calls) WHERE run_id=?",
                    (state, provider_calls, run_id),
                )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def append_event(self, run_id: str, seq: int, kind: str, payload: dict[str, Any]) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO events(run_id,seq,kind,payload_json,created_at) VALUES(?,?,?,?,?)",
                (run_id, seq, kind, json.dumps(payload, sort_keys=True), self._now()),
            )

    def get_events(self, run_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT run_id,seq,kind,payload_json,created_at FROM events WHERE run_id=? AND seq>? ORDER BY seq ASC",
            (run_id, after_seq),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "seq": row["seq"],
                "kind": row["kind"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def next_seq(self, run_id: str) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(seq),0)+1 AS next_seq FROM events WHERE run_id=?", (run_id,)).fetchone()
        return int(row["next_seq"])

    def all_runs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM runs ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
