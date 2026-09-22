from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

from .db import Database
from .models import RunResult, RunState, RuntimeEvent, TERMINAL_STATES
from .policy import DeterministicPolicy
from .provider import Provider, ProviderError, ProviderTimeout


class ConversationRuntime:
    """Orchestrates one streamed turn and owns terminal-state semantics."""

    def __init__(self, db: Database, policy: DeterministicPolicy, timeout_seconds: float = 30.0):
        self.db = db
        self.policy = policy
        self.timeout_seconds = timeout_seconds
        self._active: dict[str, asyncio.Event] = {}
        self._state_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, run_id: str) -> asyncio.Lock:
        return self._state_locks.setdefault(run_id, asyncio.Lock())

    async def _append(self, run_id: str, kind: str, payload: dict) -> RuntimeEvent:
        seq = self.db.next_seq(run_id)
        safe_payload = self._safe_payload(kind, payload)
        self.db.append_event(run_id, seq, kind, safe_payload)
        return RuntimeEvent(run_id, seq, kind, safe_payload)

    @staticmethod
    def _safe_payload(kind: str, payload: dict) -> dict:
        """Keep operational traces free of secrets/hidden reasoning."""
        if kind == "chunk":
            return {"text": payload.get("text", "")}
        if kind == "policy":
            return {"allowed": bool(payload.get("allowed")), "reason": payload.get("reason", "unknown")}
        if kind == "terminal":
            return {"state": payload.get("state")}
        if kind == "provider_error":
            return {"code": payload.get("code", "provider_error")}
        return {k: v for k, v in payload.items() if k not in {"api_key", "authorization", "token", "secret", "prompt", "reasoning"}}

    async def _terminal(self, run_id: str, state: RunState, output: str = "") -> RuntimeEvent | None:
        if state not in TERMINAL_STATES:
            raise ValueError("terminal state required")
        async with self._lock_for(run_id):
            current = self.db.get_run(run_id)
            if not current or current["state"] in {s.value for s in TERMINAL_STATES}:
                return None
            self.db.update_state(run_id, state.value, output=output)
            return await self._append(run_id, "terminal", {"state": state.value})

    async def cancel(self, run_id: str) -> bool:
        event = self._active.get(run_id)
        if event is None:
            current = self.db.get_run(run_id)
            return bool(current and current["state"] not in {s.value for s in TERMINAL_STATES})
        event.set()
        return True

    async def stream_turn(self, user_input: str, provider: Provider, run_id: str | None = None) -> AsyncIterator[RuntimeEvent]:
        """Execute one turn while preserving provider yield order and terminal-state rules.

        The provider iterator is advanced one chunk at a time instead of using a
        producer queue. This prevents the provider from racing ahead of the
        runtime and makes cancellation semantics deterministic: a chunk that has
        already been yielded is committed exactly once; a later chunk is not.
        """
        run_id = run_id or str(uuid.uuid4())
        cancel_event = asyncio.Event()
        self._active[run_id] = cancel_event
        self.db.create_run(run_id, user_input)

        yield await self._append(run_id, "accepted", {})

        decision = self.policy.check(user_input)
        yield await self._append(run_id, "policy", {"allowed": decision.allowed, "reason": decision.reason})
        if not decision.allowed:
            terminal = await self._terminal(run_id, RunState.REJECTED)
            if terminal:
                yield terminal
            self._active.pop(run_id, None)
            return

        self.db.update_state(run_id, RunState.RUNNING.value)
        yield await self._append(run_id, "running", {})
        yield await self._append(run_id, "provider_started", {"provider": provider.__class__.__name__})

        output_parts: list[str] = []
        provider_iter = provider.stream(user_input, cancel_event).__aiter__()
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds

        try:
            while True:
                if cancel_event.is_set():
                    terminal = await self._terminal(run_id, RunState.CANCELLED)
                    if terminal:
                        yield terminal
                    return

                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    cancel_event.set()
                    yield await self._append(run_id, "provider_error", {"code": "timeout"})
                    terminal = await self._terminal(run_id, RunState.TIMED_OUT)
                    if terminal:
                        yield terminal
                    return

                next_task = asyncio.create_task(provider_iter.__anext__())
                try:
                    chunk = await asyncio.wait_for(next_task, timeout=remaining)
                except StopAsyncIteration:
                    if cancel_event.is_set():
                        terminal = await self._terminal(run_id, RunState.CANCELLED)
                    else:
                        terminal = await self._terminal(run_id, RunState.COMPLETED, output="".join(output_parts))
                    if terminal:
                        yield terminal
                    return
                except asyncio.TimeoutError:
                    cancel_event.set()
                    next_task.cancel()
                    await asyncio.gather(next_task, return_exceptions=True)
                    yield await self._append(run_id, "provider_error", {"code": "timeout"})
                    terminal = await self._terminal(run_id, RunState.TIMED_OUT)
                    if terminal:
                        yield terminal
                    return
                except ProviderTimeout:
                    yield await self._append(run_id, "provider_error", {"code": "provider_timeout"})
                    terminal = await self._terminal(run_id, RunState.TIMED_OUT)
                    if terminal:
                        yield terminal
                    return
                except ProviderError:
                    yield await self._append(run_id, "provider_error", {"code": "provider_error"})
                    terminal = await self._terminal(run_id, RunState.FAILED)
                    if terminal:
                        yield terminal
                    return
                except asyncio.CancelledError:
                    next_task.cancel()
                    await asyncio.gather(next_task, return_exceptions=True)
                    raise
                except Exception as exc:
                    yield await self._append(run_id, "provider_error", {"code": type(exc).__name__})
                    terminal = await self._terminal(run_id, RunState.FAILED)
                    if terminal:
                        yield terminal
                    return

                # The provider may set the cancellation flag while producing this
                # chunk. That chunk was yielded only after the cancellation point,
                # so it is intentionally not displayed.
                if cancel_event.is_set():
                    terminal = await self._terminal(run_id, RunState.CANCELLED)
                    if terminal:
                        yield terminal
                    return

                output_parts.append(chunk)
                yield await self._append(run_id, "chunk", {"text": chunk})

        except asyncio.CancelledError:
            cancel_event.set()
            terminal = await self._terminal(run_id, RunState.CANCELLED)
            if terminal:
                yield terminal
            raise
        finally:
            current = self.db.get_run(run_id)
            if current is not None:
                self.db.update_state(run_id, current["state"], provider_calls=getattr(provider, "calls", 0))
            self._active.pop(run_id, None)

    async def execute(self, user_input: str, provider: Provider, run_id: str | None = None) -> RunResult:
        events: list[RuntimeEvent] = []
        async for event in self.stream_turn(user_input, provider, run_id=run_id):
            events.append(event)
        final = self.db.get_run(events[0].run_id)
        return RunResult(
            run_id=events[0].run_id,
            state=RunState(final["state"]),
            output=final.get("assistant_output") or "",
            provider_calls=getattr(provider, "calls", 0),
        )
