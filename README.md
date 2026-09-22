# Caygnus — Problem 5: Reliable AI Conversation Runtime

A small deterministic conversation runtime implementing the acceptance requirements for **Reliable AI Conversation Runtime**.

## What is implemented

- Stable `run_id`
- Explicit state machine: `accepted -> running -> terminal`
- Pre-response deterministic policy gate
- Provider abstraction with deterministic fake provider
- Ordered streamed text chunks
- SQLite persistence for runs and operational events
- Exactly one terminal state
- Cancellation, timeout, and provider-failure paths
- Trace redaction: no API keys, tokens, prompts, or hidden reasoning in operational events
- FastAPI SSE endpoint for streaming
- Focused pytest suite
- Repeatable benchmark

## Architecture

```text
HTTP/CLI
   |
   v
ConversationRuntime
   |----> Policy (before provider)
   |----> Provider interface
   |       `-- FakeProvider (deterministic)
   `----> SQLite Repository
             |-- runs
             `-- events
```

### State rules

`accepted` and `running` are non-terminal. Exactly one of `completed`, `rejected`, `cancelled`, `timed_out`, or `failed` can win. Later terminal transitions are ignored.

### Persistence boundary

The user turn and every operational/chunk event are durable. The assembled assistant response is persisted **only on successful completion**. Partial output remains inspectable as chunk history but is never represented as a successful assistant response.

### Restart policy

SQLite survives process restart. An already-terminal run remains terminal. An in-progress run that is found after a process restart is not silently resumed as successful; a production implementation should explicitly reconcile such a run as interrupted/failed. This prototype keeps the policy deterministic and avoids inventing output that the restarted process did not generate.

### Timeout testing

Production-facing execution can be placed behind an asyncio timeout at the API/service boundary. To keep the exercise deterministic and avoid arbitrary sleeps, the fake provider raises a controlled timeout after a configured number of chunks; the runtime maps it to `timed_out`.

## Setup

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run tests:

```powershell
pytest -q
```

Run the demo:

```powershell
python demo.py
```

Run the benchmark:

```powershell
python benchmark.py
```

Run the API:

```powershell
uvicorn app.main:app --reload
```

Then stream a deterministic turn using `POST /turns/stream`, for example:

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/turns/stream `
  -H "Content-Type: application/json" `
  -d '{"user_input":"hello","mode":"success","chunks":["Hello ","from ","Caygnus."]}'
```

## Demo scenario

1. Successful streaming shows ordered chunks and terminal completion.
2. `BLOCK_ME` demonstrates policy rejection before provider invocation.
3. A fake provider failure after partial chunks demonstrates non-success terminal state.
4. A fake provider timeout demonstrates bounded non-success handling.
5. The same SQLite file is opened by a new runtime instance to show durable state across restart.

## Important trade-off

I intentionally kept the transport thin and concentrated correctness in the runtime state machine and durable event log. A distributed event broker, multiple workers, model integration, authentication, and production observability would add complexity without improving the core acceptance behaviour for this exercise.
