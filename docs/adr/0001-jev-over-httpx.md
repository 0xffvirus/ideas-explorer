# ADR 0001: Jev over HTTP with httpx, not the TypeSafe SDK

Status: accepted (2026-10-14)

## Context

SPEC.md lists `typesafe-sdk` as the Jev client, while SPEC-jev-gate.md leaves the
question open: "Does the Python SDK expose async? If not, wrap it with httpx
directly against the REST endpoint (preferred anyway)."

The pipeline is fully async and needs per-call control over timeouts, bounded
retries on 429/5xx, question-batch chunking, and per-call usage/cost accounting.

## Decision

Implement `app/jev/client.py` directly against `POST /v1/systemone` with
`httpx.AsyncClient`. The wire format (question types, answer shapes, usage) is
pinned by recorded fixtures and contract tests under `tests/fixtures/jev/`.

## Consequences

- Native async, no thread offloading.
- Exact control of retries, chunk concurrency, usage metering, and error mapping
  (`JevProtocolError` vs `JevUnavailableError`).
- We own the request/response models; a wire-format change on TypeSafe's side
  fails the recorded-fixture contract tests loudly.
- If the official SDK later offers async and typed usage, swapping it behind the
  `JevLike` protocol is a local change.
