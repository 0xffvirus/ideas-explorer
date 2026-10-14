import { describe, expect, it } from "vitest";
import { parseRunEvent, progressReducer, seedProgress, initialProgress } from "./run-events";
import type { Run, RunEvent } from "./types";

function event(partial: Partial<RunEvent> & Pick<RunEvent, "type">): RunEvent {
  return {
    id: partial.id ?? "1",
    run_id: "run-1",
    at: "2026-10-01T09:00:00.000Z",
    step: null,
    status: null,
    error: null,
    cost_usd: null,
    cost_cap_usd: 0.75,
    questions: [],
    ...partial,
  } as RunEvent;
}

function run(partial: Partial<Run> = {}): Run {
  return {
    id: "run-1",
    idea_id: "idea-1",
    idea_version_id: "version-1",
    status: "queued",
    step: null,
    cost_usd: 0,
    cost_cap_usd: 0.75,
    error: null,
    steps: [
      {
        step: "refine",
        status: "pending",
        cost_usd: 0,
        model: null,
        attempts: 0,
        error: null,
        started_at: null,
        finished_at: null,
      },
    ],
    questions: [],
    created_at: "2026-10-01T09:00:00.000Z",
    started_at: null,
    finished_at: null,
    ...partial,
  } as Run;
}

describe("parseRunEvent", () => {
  it("parses a valid step event", () => {
    const parsed = parseRunEvent(
      JSON.stringify({
        id: "3",
        type: "step_started",
        run_id: "run-1",
        at: "2026-10-01T09:00:00Z",
        step: "market",
      }),
    );
    expect(parsed?.type).toBe("step_started");
    expect(parsed?.step).toBe("market");
  });

  it("falls back to the SSE id and event name when missing from data", () => {
    const parsed = parseRunEvent(
      JSON.stringify({ run_id: "run-1", at: "2026-10-01T09:00:00Z", step: "refine" }),
      "7",
      "step_completed",
    );
    expect(parsed?.id).toBe("7");
    expect(parsed?.type).toBe("step_completed");
  });

  it("returns null for malformed frames instead of throwing", () => {
    expect(parseRunEvent("not json")).toBeNull();
    expect(parseRunEvent(JSON.stringify({ type: "unknown_type" }))).toBeNull();
  });
});

describe("progressReducer", () => {
  it("runs a step lifecycle and promotes queued to running", () => {
    let state = seedProgress(run());
    expect(state.status).toBe("queued");
    expect(state.steps.refine).toBe("pending");

    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "1", type: "step_started", step: "refine" }),
    });
    expect(state.status).toBe("running");
    expect(state.steps.refine).toBe("running");
    expect(state.activeStep).toBe("refine");

    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "2", type: "step_completed", step: "refine", cost_usd: 0.05 }),
    });
    expect(state.steps.refine).toBe("done");
    expect(state.activeStep).toBeNull();
    expect(state.costUsd).toBe(0.05);
  });

  it("deduplicates replayed events by id", () => {
    const first = progressReducer(initialProgress, {
      kind: "seed",
      run: run({ id: "run-1" }),
    });
    const replay = {
      kind: "event",
      event: event({ id: "9", type: "cost_update", cost_usd: 0.1 }),
    } as const;
    const once = progressReducer(first, replay);
    const twice = progressReducer(once, replay);
    expect(once.events).toHaveLength(1);
    expect(twice.events).toHaveLength(1);
  });

  it("ignores events from a different run", () => {
    const state = seedProgress(run());
    const next = progressReducer(state, {
      kind: "event",
      event: event({ id: "1", type: "step_started", run_id: "other-run", step: "refine" }),
    });
    expect(next.events).toHaveLength(0);
    expect(next.steps.refine).toBe("pending");
  });

  it("captures clarifying questions on awaiting_input", () => {
    const state = progressReducer(seedProgress(run()), {
      kind: "event",
      event: event({
        id: "1",
        type: "awaiting_input",
        status: "awaiting_input",
        questions: [{ id: "q1", question: "Who is the customer?" }],
      }),
    });
    expect(state.status).toBe("awaiting_input");
    expect(state.questions).toHaveLength(1);
    expect(state.done).toBe(false);
  });

  it("keeps the event cursor and history when re-seeding the same run", () => {
    let state = seedProgress(run({ status: "done" }));
    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "7", type: "run_done", status: "done" }),
    });
    expect(state.lastEventId).toBe("7");

    // A section re-run reports the same run as active again.
    state = progressReducer(state, {
      kind: "seed",
      run: run({ status: "running", step: "market" }),
    });
    expect(state.status).toBe("running");
    expect(state.done).toBe(false);
    expect(state.lastEventId).toBe("7");
    expect(state.events).toHaveLength(1);
  });

  it("resets the cursor when seeding a different run", () => {
    let state = seedProgress(run({ id: "run-1" }));
    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "3", type: "run_done", status: "done" }),
    });
    state = progressReducer(state, { kind: "seed", run: run({ id: "run-2", status: "queued" }) });
    expect(state.runId).toBe("run-2");
    expect(state.lastEventId).toBeNull();
  });

  it("marks the run done on run_done and records failures", () => {
    let state = seedProgress(run());
    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "1", type: "step_failed", step: "market", error: "boom" }),
    });
    expect(state.steps.market).toBe("failed");
    expect(state.error).toBe("boom");
    expect(state.done).toBe(false);

    state = progressReducer(state, {
      kind: "event",
      event: event({ id: "2", type: "run_done", status: "partial", cost_usd: 0.75 }),
    });
    expect(state.status).toBe("partial");
    expect(state.done).toBe(true);
  });
});
