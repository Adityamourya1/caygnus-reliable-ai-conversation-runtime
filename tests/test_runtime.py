import asyncio

from app.db import Database
from app.models import RunState
from app.policy import DeterministicPolicy
from app.provider import FakeProvider, FakeProviderConfig
from app.runtime import ConversationRuntime


async def collect(runtime, text, provider, run_id=None):
    events = []
    async for event in runtime.stream_turn(text, provider, run_id=run_id):
        events.append(event)
    return events


def make_runtime(tmp_path, timeout_seconds=30.0):
    return ConversationRuntime(Database(str(tmp_path / "test.db")), DeterministicPolicy(), timeout_seconds=timeout_seconds)


def test_successful_stream_order_and_persistence(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["A", "B", "C"]))
    events = asyncio.run(collect(runtime, "hello", provider))
    chunks = [e.payload["text"] for e in events if e.kind == "chunk"]
    assert chunks == ["A", "B", "C"]
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    run = runtime.db.get_run(events[0].run_id)
    assert run["state"] == RunState.COMPLETED.value
    assert run["assistant_output"] == "ABC"


def test_policy_rejection_never_calls_provider(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["should-not-run"]))
    events = asyncio.run(collect(runtime, "BLOCK_ME please", provider))
    assert provider.calls == 0
    run = runtime.db.get_run(events[0].run_id)
    assert run["state"] == RunState.REJECTED.value
    assert run["assistant_output"] is None


def test_cancellation_during_streaming(tmp_path):
    runtime = make_runtime(tmp_path)

    class StepProvider(FakeProvider):
        async def stream(self, user_input, cancel_event):
            self.calls += 1
            yield "one"
            await asyncio.sleep(0)
            cancel_event.set()
            yield "two"

    provider = StepProvider(FakeProviderConfig(chunks=[]))
    events = asyncio.run(collect(runtime, "cancel me", provider))
    chunks = [e.payload["text"] for e in events if e.kind == "chunk"]
    run = runtime.db.get_run(events[0].run_id)
    assert chunks == ["one"]
    assert run["state"] == RunState.CANCELLED.value


def test_provider_failure_after_partial_output(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["A", "B", "C"], fail_after=2))
    events = asyncio.run(collect(runtime, "fail", provider))
    chunks = [e.payload["text"] for e in events if e.kind == "chunk"]
    run = runtime.db.get_run(events[0].run_id)
    assert chunks == ["A", "B"]
    assert run["state"] == RunState.FAILED.value
    assert run["assistant_output"] is None
    assert any(e.kind == "provider_error" for e in events)


def test_deterministic_provider_timeout_after_partial_output(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["A", "B", "C"], timeout_after=2))
    events = asyncio.run(collect(runtime, "timeout", provider))
    run = runtime.db.get_run(events[0].run_id)
    assert run["state"] == RunState.TIMED_OUT.value
    assert run["assistant_output"] is None
    assert [e.payload["text"] for e in events if e.kind == "chunk"] == ["A", "B"]


def test_runtime_timeout_cancels_stalled_provider(tmp_path):
    runtime = make_runtime(tmp_path, timeout_seconds=0.02)
    provider = FakeProvider(FakeProviderConfig(chunks=["A", "B"], stall_after=1))
    events = asyncio.run(collect(runtime, "stall", provider))
    run = runtime.db.get_run(events[0].run_id)
    assert run["state"] == RunState.TIMED_OUT.value
    assert [e.payload["text"] for e in events if e.kind == "chunk"] == ["A"]


def test_terminal_state_is_idempotent(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["done"]))
    events = asyncio.run(collect(runtime, "hello", provider))
    run_id = events[0].run_id
    first = asyncio.run(runtime._terminal(run_id, RunState.FAILED))
    assert first is None
    run = runtime.db.get_run(run_id)
    assert run["state"] == RunState.COMPLETED.value


def test_trace_excludes_secrets_and_reasoning(tmp_path):
    runtime = make_runtime(tmp_path)
    provider = FakeProvider(FakeProviderConfig(chunks=["safe"]))
    events = asyncio.run(collect(runtime, "hello", provider))
    run_id = events[0].run_id
    safe = asyncio.run(runtime._append(run_id, "provider_error", {
        "code": "bad_provider",
        "api_key": "SECRET-123",
        "reasoning": "private chain",
    }))
    assert "api_key" not in safe.payload
    assert "reasoning" not in safe.payload
    persisted = runtime.db.get_events(run_id)
    assert all("SECRET-123" not in str(e) for e in persisted)
    assert all("private chain" not in str(e) for e in persisted)
