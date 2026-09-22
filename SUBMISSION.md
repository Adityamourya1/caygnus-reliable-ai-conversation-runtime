# Caygnus Product Engineering Challenge — Submission

## Selected problem

**Problem 5 — Reliable AI Conversation Runtime**

## Demo video

TODO: add Loom / YouTube / Google Drive link.

## Repository

TODO: paste the public GitHub fork URL.

## Setup and verification

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
python demo.py
python benchmark.py
```

Expected setup time is a few minutes on a clean Python 3.10 environment.

## Architecture

The runtime is split into four responsibilities:

1. `ConversationRuntime` owns orchestration and terminal-state transitions.
2. `DeterministicPolicy` makes the pre-provider decision.
3. `FakeProvider` implements a provider-shaped async stream for deterministic tests/demo.
4. `Database` owns durable run and event history in SQLite.

The FastAPI layer is intentionally thin and presents the runtime as an SSE stream plus run-inspection endpoint.

## Completed acceptance scenarios

### AC1 — Successful streamed turn

The runtime persists ordered events and streams chunks in sequence. A successful run ends in `completed`, and only then is the assembled assistant response persisted.

### AC2 — Pre-response rejection

Inputs containing the demo policy marker `BLOCK_ME` are rejected before the provider is invoked. Tests assert provider call count is zero.

### AC3 — Cancellation

The runtime owns an `asyncio.Event` cancellation signal and checks it before committing the next chunk. Cancellation wins over completion and produces the `cancelled` terminal state.

### AC4 — Timeout

The deterministic fake provider can raise a controlled timeout after N chunks. The runtime records a safe provider error event and transitions to `timed_out` without persisting a successful assistant response.

### AC5 — Provider failure

A provider error after partial output is recorded as an operational event and moves the run to `failed`. Partial chunks remain inspectable, but no successful assistant response is committed.

### AC6 — Terminal-state race

Terminal transitions are guarded by a per-run asyncio lock and a durable state check. Once a terminal state is stored, later terminal transitions become no-ops.

### AC7 — Safe operational trace

Trace payloads are intentionally narrow. Error events contain safe error codes rather than raw provider payloads. Fields such as `api_key`, `authorization`, `token`, `secret`, `prompt`, and `reasoning` are excluded.

## Verification benchmark

`python benchmark.py` runs 10 deterministic iterations of each required scenario: success, rejection, cancellation, timeout, and provider failure. It reports terminal-state counts and checks exactly one terminal event, provider bypass on rejection, non-success persistence rules, and event ordering.

The benchmark focuses on the Problem 5 state-machine scenarios required by the brief. The demo and tests exercise partial-stream failure, timeout, cancellation, terminal-state protection, and durable state across a fresh database connection.

## Assumptions

- One active run per conversation is enough for this focused exercise.
- SQLite is the durable store for a single service process.
- Partial assistant output is not a successful conversational turn and is therefore not committed as assistant response content.
- Cancellation is cooperative through the provider interface.

## Limitations / production changes

- Multiple service workers would require an external coordination primitive and compare-and-set state transitions in the database.
- A production model provider would expose cancellation/timeout capabilities directly.
- Event retention could be bounded and archived; clients would need a replay-expired response when their cursor is no longer available.
- Authentication, authorization, multi-tenancy, rate limits, and external tracing are intentionally out of scope.

## Technology choice and trade-offs

Python + FastAPI keeps the prototype close to my existing full-stack/AI experience while allowing a small asynchronous streaming API. SQLite was chosen because the challenge is single-process and correctness-focused; it provides durable state without introducing an unnecessary external dependency.

The main trade-off is deliberate simplicity: the repository is strong on state transitions, persistence, deterministic fakes, and tests, but it does not attempt distributed coordination or a real model integration.

## AI usage disclosure

AI tools were used as an implementation assistant for code structure, test-case generation, and documentation drafting. I reviewed the generated code, ran the automated tests and benchmark, and remain responsible for the design and submitted implementation.

## Credibility note

I previously built and deployed full-stack/AI projects including SportsConnect, a sports social platform with profiles, posts, leagues, role-based interactions, REST APIs, and AI recommendations, and a recommendation engine using Python/FastAPI. These projects informed the API, async runtime, data persistence, and product-oriented decomposition used here.

Public portfolio/repositories: https://github.com/Adityamourya1
