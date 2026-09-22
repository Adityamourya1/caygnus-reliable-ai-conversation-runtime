from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunState(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


TERMINAL_STATES = {
    RunState.COMPLETED,
    RunState.REJECTED,
    RunState.CANCELLED,
    RunState.TIMED_OUT,
    RunState.FAILED,
}


@dataclass(frozen=True)
class RuntimeEvent:
    run_id: str
    seq: int
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    run_id: str
    state: RunState
    output: str = ""
    provider_calls: int = 0
