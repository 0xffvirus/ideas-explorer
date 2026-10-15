# ADR 0002: Postgres-backed job queue, no Redis

Status: accepted (2026-10-14)

## Context

The pipeline needs durable jobs that survive worker crashes: analysis runs and
single-section reruns. SPEC.md fixes the infrastructure: "Postgres-backed job
table with a worker process (SELECT … FOR UPDATE SKIP LOCKED). No Redis."

## Decision

`jobs` and the run tables live in Postgres. `JobQueue.claim_next` claims with
`FOR UPDATE SKIP LOCKED`; workers heartbeat `locked_at` while a job executes;
`requeue_stale` reclaims jobs whose heartbeat expired with a single conditional
`UPDATE`. Analysis runs are created at enqueue time and their id travels in the
job payload, so a reclaimed job resumes the same run instead of paying twice.

## Consequences

- One datastore for data and coordination; `docker compose up -d db` is the
  whole infrastructure.
- Crash-restart resumes from the last completed run step (each step output is
  persisted before the next starts).
- Contention is a row lock, not a separate broker; fine for a single-user MVP.
- If throughput ever demands a broker, the `JobQueue` surface is the seam.
