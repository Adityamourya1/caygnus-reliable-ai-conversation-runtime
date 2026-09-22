=== Successful streamed turn ===
[01] accepted
[02] policy
[03] running
[04] provider_started
[05] chunk: 'Hello '
[06] chunk: 'from '
[07] chunk: 'Caygnus '
[08] chunk: 'runtime.'
[09] terminal: completed

=== Policy rejection ===
[01] accepted
[02] policy
[03] terminal: rejected

=== Provider failure after partial output ===
[01] accepted
[02] policy
[03] running
[04] provider_started
[05] chunk: 'partial '
[06] chunk: 'output '
[07] provider_error
[08] terminal: failed

=== Deterministic timeout ===
[01] accepted
[02] policy
[03] running
[04] provider_started
[05] chunk: 'one '
[06] chunk: 'two '
[07] provider_error
[08] terminal: timed_out

=== Persisted restart view ===
51f6344e-9e4c-44d1-9723-ea313f6cc3b4 -> completed
b3b1cf4d-3fdc-4962-91d2-926f564013c7 -> rejected
b71fab8b-3043-4236-94fb-0a9b72e4b5c4 -> failed
86c499a3-0b4f-4959-8d99-053ab8be3a6e -> timed_out
