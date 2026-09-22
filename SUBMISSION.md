# Caygnus Product Engineering Challenge — Submission

## Candidate

* **Name:** Mourya Aditya
* **Email:** `adityamourya2026@gmail.com`
* **GitHub:** https://github.com/Adityamourya1
* **Selected problem:** Problem 5 — Reliable AI Conversation Runtime
* **Demo video:** `[PASTE YOUR VIDEO LINK HERE]`

## Repository

https://github.com/Adityamourya1/caygnus-reliable-ai-conversation-runtime

## Run the project

### Prerequisites

* Python 3.10
* Windows PowerShell commands below assume Python is available as `py -3.10`

### Setup

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No API key or paid external model provider is required for the submitted deterministic scenarios.

### Run the demo

```powershell
python demo.py
```

The demo demonstrates:

1. Successful streamed completion with ordered chunks
2. Pre-response policy rejection using `BLOCK_ME`
3. Provider failure after partial output
4. Deterministic timeout after partial output
5. Durable terminal state after closing and reopening the same SQLite database

### Run the API

```powershell
uvicorn app.main:app --reload
```

Available endpoints include:

* `GET /health`
* `POST /turns/stream`
* `GET /runs/{run_id}`

Example deterministic stream:

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/turns/stream `
  -H "Content-Type: application/json" `
  -d '{"user_input":"hello","mode":"success","chunks":["Hello ","from ","Caygnus."]}'
```

## Run the tests

```powershell
pytest -q
```

The focused test suite covers:

* successful streaming and ordering
* policy rejection before provider invocation
* cancellation during streaming
* provider failure after partial output
* deterministic timeout
* runtime timeout for a stalled provider
* terminal-state idempotency
* safe operational trace redaction

## Acceptance scenarios and verification

### AC1 — Successful streamed turn

The runtime creates a stable `run_id`, persists ordered events, streams provider chunks in order, and transitions to `completed` only after the provider finishes successfully.

The assembled assistant response is persisted only after successful completion.

### AC2 — Pre-response rejection

The deterministic policy gate runs before provider execution.

Inputs containing `BLOCK_ME` are rejected with terminal state `rejected`, and the provider is not invoked.

### AC3 — Cancellation

Cancellation is cooperative through an `asyncio.Event`.

The runtime checks cancellation before committing the next chunk. A cancelled run reaches terminal state `cancelled` and is not represented as a successful completed response.

### AC4 — Timeout

The deterministic provider can produce a controlled timeout after a configured number of chunks.

The runtime maps this to `timed_out` and does not persist a successful assistant response.

### AC5 — Provider failure

A provider error after partial output moves the run to `failed`.

Previously emitted chunks remain inspectable as durable event history, but no successful assistant response is committed.

### AC6 — Terminal-state idempotency

Terminal transitions are protected by a per-run asyncio lock and a durable state check.

Once a terminal state has been stored, later terminal transitions are ignored.

### AC7 — Safe operational trace

Operational payloads are intentionally narrow.

Provider errors use safe error codes rather than raw provider payloads. Sensitive fields such as API keys, authorization headers, tokens, secrets, prompts, and hidden reasoning are excluded from operational trace payloads.

## Problem-specific verification benchmark

Run:

```powershell
python benchmark.py
```

The benchmark runs 10 deterministic iterations of each scenario:

* success
* policy rejection
* cancellation
* timeout
* provider failure

It verifies:

* exactly one terminal event
* valid terminal state
* provider bypass for rejection
* no successful assistant persistence for rejection, cancellation, timeout, or failure
* cancellation makes progress
* strictly ordered and unique event sequence numbers
* no events are emitted after the terminal event

### Observed benchmark result

Paste the exact output from your local run below.

```text
[PASTE ACTUAL OUTPUT OF: python benchmark.py]
```

Do not manually change the observed counts.

## Architecture and data flow

```text
Client / CLI
     |
     v
FastAPI SSE layer
     |
     v
ConversationRuntime
     |
     +----> DeterministicPolicy
     |          |
     |          +----> allow / reject before provider
     |
     +----> Provider interface
     |          |
     |          +----> FakeProvider
     |
     +----> SQLite Database
                |
                +----> runs
                |
                +----> events
```

`ConversationRuntime` owns orchestration, streaming, cancellation, timeout handling, and terminal-state semantics.

`DeterministicPolicy` runs before provider invocation.

The provider is isolated behind an asynchronous streaming interface so the runtime can be tested without depending on an external paid model API.

SQLite stores durable run state and ordered event history.

A successful run follows:

```text
accepted
  -> policy
  -> running
  -> provider_started
  -> chunk(s)
  -> completed
```

A non-successful run terminates explicitly as:

```text
rejected
cancelled
timed_out
failed
```

Partial streamed output remains inspectable through chunk events but is not treated as a successfully completed assistant response.

## Technology choices

### Python + FastAPI

Python provides a compact asynchronous implementation suitable for an AI/backend runtime. FastAPI provides a thin HTTP/SSE layer while keeping the core correctness logic inside the runtime.

### SQLite

SQLite was chosen because the challenge is a focused single-process prototype and needs durable state without introducing an unnecessary external database dependency.

### Deterministic FakeProvider

A deterministic provider makes success, cancellation, timeout, and failure scenarios repeatable and keeps the tests independent of paid or unreliable external services.

### Alternatives considered

A real LLM provider would demonstrate model integration, but it would introduce credentials, network dependency, cost, and nondeterministic output without improving the core reliability behavior being evaluated.

A distributed queue or broker would be appropriate for a larger production system, but would be disproportionate for this focused exercise.

## Important decisions

### 1. Explicit single terminal outcome

The runtime treats `completed`, `rejected`, `cancelled`, `timed_out`, and `failed` as terminal states.

Once one terminal state is durably recorded, later terminal transitions are ignored.

### 2. Event history is separate from successful assistant output

Chunks and operational events are durable, while the assembled assistant response is committed only on successful completion.

This preserves useful recovery/debugging information without incorrectly treating partial output as a completed turn.

### 3. Thin transport layer

The FastAPI layer converts runtime events into SSE responses.

The state machine and correctness rules remain inside `ConversationRuntime`, where they can be tested directly without HTTP.

## Assumptions and limitations

* One active run per conversation is sufficient for this focused exercise.
* SQLite is used as the durable store for a single service process.
* Cancellation is cooperative through the provider interface.
* Partial assistant output is not considered a successful conversational turn.
* The provider is deterministic and intentionally not a real model integration.
* Authentication, authorization, multi-tenancy, rate limiting, distributed coordination, and production infrastructure are out of scope.
* Event retention is currently unbounded for the prototype.

## Production and scale

The submitted implementation is intentionally single-process and correctness-focused.

For production, I would first:

1. Replace process-local terminal locking with database-level transactional compare-and-set state transitions so multiple workers cannot produce conflicting terminal outcomes.
2. Add external coordination where distributed execution requires it.
3. Use a real provider adapter with native cancellation and request deadlines.
4. Add metrics, tracing, alerting, bounded event retention, and replay-expiration handling.
5. Add authentication, authorization, rate limits, and multi-tenancy.

These are proposed production improvements, not claims about capabilities already implemented in this prototype.

## AI usage

AI tools were used as implementation assistants for code structure, test-case generation, debugging support, and documentation drafting.

I reviewed and adapted the generated output and verified behavior with focused automated tests and the deterministic benchmark.

I remain responsible for the submitted code, architecture, and explanations and can explain or modify the implementation during follow-up discussion.

## Credibility note

I previously built and deployed full-stack/AI projects including SportsConnect, a sports social platform with profiles, posts, leagues, role-based interactions, REST APIs, and AI-powered recommendations.

My contribution included backend/API development, data persistence, AI/recommendation functionality, and deployment integration.

This work involved coordinating frontend and backend components and external services, and influenced the decomposition used in this challenge: keep transport concerns thin, isolate runtime/orchestration logic, define provider boundaries, and persist important state explicitly.

Public evidence:

* GitHub: https://github.com/Adityamourya1
* SportsConnect repository: https://github.com/Adityamourya1/sportsconnect
