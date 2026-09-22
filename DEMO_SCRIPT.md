# 3–5 Minute Demo Script

## 0:00–0:25 — Problem and architecture

“Caygnus Problem 5 asks for a reliable runtime around a streamed AI turn. The important part is not model quality; it is correct state transitions, cancellation, timeout, failure handling, persistence, and safe operational traces.

The runtime has five boundaries: FastAPI presentation, policy gate, provider abstraction, orchestration, and SQLite persistence.”

## 0:25–1:20 — Successful stream

Run:

```powershell
python demo.py
```

Point out:

- `accepted`
- `policy`
- `running`
- `provider_started`
- ordered `chunk` events
- final `completed`

Say: “The assistant response is persisted only at completion. Every chunk remains durable as event history.”

## 1:20–2:00 — Policy rejection

Show the `BLOCK_ME` case.

Say: “The policy gate runs before the provider. The test verifies the provider call count stays zero. Rejected runs do not create a successful assistant response.”

## 2:00–2:45 — Failure and timeout

Show the failure and deterministic timeout cases.

Say: “Partial chunks remain inspectable, but neither failure nor timeout is represented as a successful completed response. Terminal state is explicit.”

## 2:45–3:25 — Persistence and safe trace

Show the final restart section from `demo.py`.

Say: “A new runtime instance opens the same SQLite database and sees the prior terminal states. Operational errors are reduced to safe codes; secrets and hidden reasoning are excluded from the trace payload.”

## 3:25–4:15 — Benchmark and tests

Run:

```powershell
pytest -q
python benchmark.py
```

Say: “The benchmark runs 10 deterministic iterations of success, policy rejection, cancellation, timeout, and provider failure. It verifies one terminal event, ordering, rejection before provider invocation, and no successful assistant persistence for non-success outcomes.”

## 4:15–4:40 — Trade-off

Say: “I chose SQLite and a deterministic fake provider because this exercise is about correctness. I intentionally did not add authentication, distributed workers, a real model provider, or production infrastructure. For multiple workers, I would move terminal transitions to database compare-and-set operations and add external coordination.”
