from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .db import Database
from .policy import DeterministicPolicy
from .provider import FakeProvider, FakeProviderConfig
from .runtime import ConversationRuntime


class TurnRequest(BaseModel):
    user_input: str
    mode: str = "success"
    fail_after: int | None = None
    timeout_after: int | None = None
    chunks: list[str] | None = None


DB = Database("runtime.db")
RUNTIME = ConversationRuntime(DB, DeterministicPolicy())
app = FastAPI(title="Caygnus Problem 5 Runtime")


def build_provider(req: TurnRequest) -> FakeProvider:
    chunks = req.chunks or ["Hello", ", ", "this ", "is ", "a ", "deterministic ", "streamed ", "reply."]
    return FakeProvider(FakeProviderConfig(
        chunks=chunks,
        fail_after=req.fail_after if req.mode == "failure" else None,
        timeout_after=req.timeout_after if req.mode == "timeout" else None,
    ))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = DB.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": run, "events": DB.get_events(run_id)}


@app.post("/turns/stream")
async def stream_turn(req: TurnRequest):
    provider = build_provider(req)

    async def body() -> AsyncIterator[str]:
        async for event in RUNTIME.stream_turn(req.user_input, provider):
            yield f"data: {json.dumps({'seq': event.seq, 'kind': event.kind, 'payload': event.payload})}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream")
