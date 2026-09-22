from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Protocol


class ProviderError(RuntimeError):
    pass


class ProviderTimeout(RuntimeError):
    pass


class Provider(Protocol):
    async def stream(self, user_input: str, cancel_event: asyncio.Event) -> AsyncIterator[str]:
        ...


@dataclass
class FakeProviderConfig:
    chunks: list[str]
    fail_after: int | None = None
    timeout_after: int | None = None
    per_chunk_delay: float = 0.0
    stall_after: int | None = None


class FakeProvider:
    """Deterministic provider used by tests, benchmark and demo."""

    def __init__(self, config: FakeProviderConfig):
        self.config = config
        self.calls = 0

    async def stream(self, user_input: str, cancel_event: asyncio.Event) -> AsyncIterator[str]:
        self.calls += 1
        for index, chunk in enumerate(self.config.chunks):
            if cancel_event.is_set():
                return
            if self.config.timeout_after is not None and index >= self.config.timeout_after:
                raise ProviderTimeout("deterministic timeout")
            if self.config.fail_after is not None and index >= self.config.fail_after:
                raise ProviderError("deterministic provider failure")
            if self.config.stall_after is not None and index >= self.config.stall_after:
                await cancel_event.wait()
                return
            if self.config.per_chunk_delay:
                await asyncio.sleep(self.config.per_chunk_delay)
            if cancel_event.is_set():
                return
            yield chunk
