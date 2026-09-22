from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.db import Database
from app.models import RunState
from app.policy import DeterministicPolicy
from app.provider import FakeProvider, FakeProviderConfig
from app.runtime import ConversationRuntime


async def show_case(runtime, label, text, provider):
    print(f"\n=== {label} ===")
    async for e in runtime.stream_turn(text, provider):
        if e.kind == "chunk":
            print(f"[{e.seq:02d}] chunk: {e.payload['text']!r}")
        elif e.kind == "terminal":
            print(f"[{e.seq:02d}] terminal: {e.payload['state']}")
        else:
            print(f"[{e.seq:02d}] {e.kind}")


async def main():
    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "demo.db")
        db = Database(db_path)
        runtime = ConversationRuntime(db, DeterministicPolicy())

        provider = FakeProvider(FakeProviderConfig(chunks=["Hello ", "from ", "Caygnus ", "runtime."]))
        await show_case(runtime, "Successful streamed turn", "hello", provider)

        provider = FakeProvider(FakeProviderConfig(chunks=["not called"]))
        await show_case(runtime, "Policy rejection", "BLOCK_ME", provider)

        provider = FakeProvider(FakeProviderConfig(chunks=["partial ", "output ", "here"], fail_after=2))
        await show_case(runtime, "Provider failure after partial output", "fail", provider)

        provider = FakeProvider(FakeProviderConfig(chunks=["one ", "two ", "three"], timeout_after=2))
        await show_case(runtime, "Deterministic timeout", "timeout", provider)

        print("\n=== Persisted restart view ===")
        db.close()
        restart_db = Database(db_path)
        new_runtime = ConversationRuntime(restart_db, DeterministicPolicy())
        for run in new_runtime.db.all_runs():
            print(run["run_id"], "->", run["state"])
        restart_db.close()


if __name__ == "__main__":
    asyncio.run(main())
