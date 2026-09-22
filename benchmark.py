from __future__ import annotations

import asyncio
import json
from collections import Counter

from app.db import Database
from app.models import RunState
from app.policy import DeterministicPolicy
from app.provider import FakeProvider, FakeProviderConfig
from app.runtime import ConversationRuntime


async def run_case(runtime, mode: str, iteration: int):
    chunks = [f"chunk-{iteration}-{i} " for i in range(8)]
    if mode == "success":
        provider = FakeProvider(FakeProviderConfig(chunks=chunks))
        text = "normal"
    elif mode == "rejection":
        provider = FakeProvider(FakeProviderConfig(chunks=chunks))
        text = "BLOCK_ME"
    elif mode == "failure":
        provider = FakeProvider(FakeProviderConfig(chunks=chunks, fail_after=4))
        text = "failure"
    elif mode == "timeout":
        provider = FakeProvider(FakeProviderConfig(chunks=chunks, timeout_after=4))
        text = "timeout"
    elif mode == "cancel":
        provider = FakeProvider(FakeProviderConfig(chunks=chunks))
        text = "cancel"
    else:
        raise ValueError(mode)

    events = []
    if mode == "cancel":
        async for event in runtime.stream_turn(text, provider):
            events.append(event)
            if event.kind == "chunk":
                await runtime.cancel(events[0].run_id)
    else:
        async for event in runtime.stream_turn(text, provider):
            events.append(event)
    run = runtime.db.get_run(events[0].run_id)
    terminal_events = [e for e in events if e.kind == "terminal"]
    return run, events, provider, terminal_events


async def main() -> None:
    # The benchmark validates runtime correctness, not filesystem cleanup.
    # An in-memory SQLite database keeps the command deterministic on Windows
    # and avoids file-lock cleanup noise after the benchmark completes.
    db = Database(":memory:")
    runtime = ConversationRuntime(db, DeterministicPolicy())
    counter = Counter()
    checks = []

    for mode in ["success", "rejection", "cancel", "timeout", "failure"]:
        for i in range(10):
            run, events, provider, terminal_events = await run_case(runtime, mode, i)
            counter[run["state"]] += 1
            checks.append(len(terminal_events) == 1)
            checks.append(run["state"] in {s.value for s in RunState})
            if mode == "rejection":
                checks.append(provider.calls == 0)
            if mode in {"cancel", "timeout", "failure", "rejection"}:
                checks.append(run["assistant_output"] is None)
            if mode == "cancel":
                checks.append(any(e.kind == "chunk" for e in events))
            seqs = [e.seq for e in events]
            checks.append(seqs == sorted(seqs) and len(seqs) == len(set(seqs)))
            terminal_seen = False
            for e in events:
                if terminal_seen:
                    checks.append(False)
                if e.kind == "terminal":
                    terminal_seen = True

    print(json.dumps({
        "scenario_counts": counter,
        "checks_passed": sum(checks),
        "checks_total": len(checks),
        "all_checks_passed": all(checks),
    }, indent=2))
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
