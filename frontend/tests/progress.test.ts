import { describe, expect, it } from "vitest";

import {
  initialProgressState,
  mapRunToProgress,
  PIPELINE_STEPS,
  progressPercent,
  reduceRunEvents,
  type ProgressState,
  type RunEvent,
} from "@/lib/progress";
import type { RunRead } from "@/lib/api/types";

function apply(state: ProgressState, ...events: RunEvent[]): ProgressState {
  return events.reduce(reduceRunEvents, state);
}

function stepAt(state: ProgressState, step: string) {
  const row = state.steps.find((candidate) => candidate.step === step);
  if (!row) throw new Error(`missing step ${step}`);
  return row;
}

describe("initialProgressState", () => {
  it("starts with every pipeline step queued, in order", () => {
    expect(initialProgressState.steps.map((step) => step.step)).toEqual([...PIPELINE_STEPS]);
    expect(initialProgressState.steps.every((step) => step.status === "queued")).toBe(true);
    expect(initialProgressState.costUsd).toBe(0);
  });
});

describe("reduceRunEvents", () => {
  it("walks the full pipeline: started -> completed rows with elapsed time", () => {
    let state = initialProgressState;
    PIPELINE_STEPS.forEach((step, index) => {
      const start = 1_000 + index * 100;
      state = apply(
        state,
        { type: "step_started", step, receivedAt: start },
        { type: "step_completed", step, receivedAt: start + 50 },
      );
    });

    expect(state.status).toBe("running");
    expect(state.steps.every((step) => step.status === "done")).toBe(true);
    expect(stepAt(state, "classify")).toMatchObject({ elapsedMs: 50, error: null });
    expect(state.currentStep).toBe("critic");

    state = apply(state, {
      type: "run_done",
      status: "done",
      cost_usd: 0.42,
      failed_sections: [],
      receivedAt: 2_000,
    });
    expect(state.status).toBe("done");
    expect(state.costUsd).toBeCloseTo(0.42);
    expect(state.currentStep).toBeNull();
  });

  it("tracks cost updates and assigns the delta to the named step", () => {
    let state = apply(initialProgressState, {
      type: "step_started",
      step: "classify",
      receivedAt: 1_000,
    });
    state = apply(state, {
      type: "cost_update",
      cost_usd: 0.03,
      cap_usd: 0.75,
      step: "classify",
      receivedAt: 1_100,
    });
    state = apply(state, {
      type: "cost_update",
      cost_usd: 0.05,
      cap_usd: 0.75,
      step: "refine",
      receivedAt: 1_200,
    });

    expect(state.costUsd).toBeCloseTo(0.05);
    expect(state.costCapUsd).toBeCloseTo(0.75);
    expect(stepAt(state, "classify").costUsd).toBeCloseTo(0.03);
    expect(stepAt(state, "refine").costUsd).toBeCloseTo(0.02);
  });

  it("pauses on run_paused with the clarifying questions", () => {
    const state = apply(initialProgressState, {
      type: "run_paused",
      questions: [{ question: "Who is the buyer?", why: "pricing depends on it" }],
      receivedAt: 1_500,
    });
    expect(state.status).toBe("awaiting_input");
    expect(state.questions).toHaveLength(1);
    expect(state.questions[0]?.question).toBe("Who is the buyer?");
  });

  it("shows the paused clarify step as running, not stuck queued", () => {
    const state = apply(initialProgressState, {
      type: "run_paused",
      step: "clarify",
      questions: [{ question: "Which city?", why: "rules differ" }],
      receivedAt: 1_500,
    });
    expect(stepAt(state, "clarify").status).toBe("running");
    expect(stepAt(state, "clarify").startedAt).toBe(1_500);
    expect(state.currentStep).toBe("clarify");
  });

  it("does not reopen a settled step when run_paused names it", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "clarify", receivedAt: 1_000 },
      { type: "step_completed", step: "clarify", receivedAt: 1_100 },
      { type: "run_paused", step: "clarify", questions: [], receivedAt: 1_500 },
    );
    expect(stepAt(state, "clarify").status).toBe("done");
    expect(state.status).toBe("awaiting_input");
  });

  it("flips back to running when a paused run resumes with a new step", () => {
    let state = apply(initialProgressState, {
      type: "run_paused",
      step: "clarify",
      questions: [],
      receivedAt: 1_500,
    });
    expect(state.status).toBe("awaiting_input");

    state = apply(state, { type: "step_started", step: "market", receivedAt: 2_000 });
    expect(state.status).toBe("running");
    expect(state.currentStep).toBe("market");
  });

  it("handles failures: failed step, partial run, remaining steps skipped", () => {
    let state = apply(
      initialProgressState,
      { type: "step_started", step: "classify", receivedAt: 1_000 },
      { type: "step_completed", step: "classify", receivedAt: 1_050 },
      { type: "step_started", step: "refine", receivedAt: 1_100 },
      { type: "step_completed", step: "refine", receivedAt: 1_160 },
      { type: "step_started", step: "market", receivedAt: 1_200 },
      { type: "step_failed", step: "market", error: "tavily timeout", receivedAt: 1_900 },
    );

    expect(stepAt(state, "market")).toMatchObject({
      status: "failed",
      error: "tavily timeout",
      elapsedMs: 700,
    });
    expect(state.error).toBe("tavily timeout");

    state = apply(state, {
      type: "run_done",
      status: "partial",
      cost_usd: 0.2,
      failed_sections: ["market"],
      receivedAt: 2_000,
    });

    expect(state.status).toBe("partial");
    expect(stepAt(state, "market").status).toBe("failed");
    expect(stepAt(state, "refine").status).toBe("done");
    expect(stepAt(state, "competitors").status).toBe("skipped");
    expect(state.failedSections).toEqual(["market"]);
  });

  it("settles queued steps to skipped when the run fails outright", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "classify", receivedAt: 1_000 },
      { type: "step_failed", step: "classify", error: "boom", receivedAt: 1_100 },
      { type: "run_done", status: "failed", cost_usd: 0.01, receivedAt: 1_200 },
    );
    expect(stepAt(state, "classify").status).toBe("failed");
    expect(stepAt(state, "critic").status).toBe("skipped");
    expect(state.status).toBe("failed");
  });

  it("marks explicitly skipped steps", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "refine", receivedAt: 1_000 },
      { type: "step_completed", step: "refine", status: "skipped", receivedAt: 1_100 },
    );
    expect(stepAt(state, "refine").status).toBe("skipped");
  });

  it("applies clarify step events to the timeline", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "clarify", receivedAt: 1_000 },
      { type: "step_completed", step: "clarify", receivedAt: 1_100 },
    );
    expect(stepAt(state, "refine").status).toBe("queued");
    expect(stepAt(state, "clarify")).toMatchObject({ status: "done", elapsedMs: 100 });
    expect(stepAt(state, "market").status).toBe("queued");
  });

  it("ignores unknown steps and malformed events without crashing", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "teleport", receivedAt: 1_000 },
      { type: "step_completed", step: "teleport", receivedAt: 1_100 },
    );
    expect(state).toEqual(initialProgressState);
  });

  it("never produces negative elapsed time on out-of-order timestamps", () => {
    const state = apply(
      initialProgressState,
      { type: "step_started", step: "classify", receivedAt: 2_000 },
      { type: "step_completed", step: "classify", receivedAt: 1_000 },
    );
    expect(stepAt(state, "classify").elapsedMs).toBe(0);
  });
});

describe("mapRunToProgress", () => {
  it("maps persisted steps with timestamps into rows", () => {
    const run: RunRead = {
      id: "run-1",
      idea_id: "idea-1",
      version_id: "version-1",
      status: "running",
      step: "market",
      cost_usd: 0.12,
      cost_cap_usd: 0.75,
      error: null,
      questions: null,
      started_at: "2026-10-14T10:00:00.000Z",
      finished_at: null,
      steps: [
        {
          id: "s1",
          step: "classify",
          status: "done",
          output: null,
          cost_usd: 0.01,
          model: "gpt-4o-mini",
          attempts: 1,
          error: null,
          started_at: "2026-10-14T10:00:00.000Z",
          finished_at: "2026-10-14T10:00:02.000Z",
        },
        {
          id: "s2",
          step: "market",
          status: "running",
          output: null,
          cost_usd: 0.05,
          model: "gpt-4o-mini",
          attempts: 1,
          error: null,
          started_at: "2026-10-14T10:00:03.000Z",
          finished_at: null,
        },
      ],
    };

    const state = mapRunToProgress(run);
    expect(state.runId).toBe("run-1");
    expect(state.status).toBe("running");
    expect(state.currentStep).toBe("market");
    expect(state.costUsd).toBeCloseTo(0.12);
    expect(state.costCapUsd).toBeCloseTo(0.75);
    expect(stepAt(state, "classify")).toMatchObject({ status: "done", elapsedMs: 2_000 });
    expect(stepAt(state, "market")).toMatchObject({ status: "running", costUsd: 0.05 });
    expect(stepAt(state, "clarify").status).toBe("queued");
    expect(stepAt(state, "critic").status).toBe("queued");
    expect(progressPercent(state)).toBe(11);
  });

  it("shows clarify as the running current step when the run awaits input", () => {
    const run: RunRead = {
      id: "run-paused",
      idea_id: "idea-1",
      version_id: "version-1",
      status: "awaiting_input",
      step: "clarify",
      cost_usd: 0.02,
      cost_cap_usd: 0.75,
      error: null,
      questions: [{ question: "Which city?", why: "rules differ" }],
      started_at: "2026-10-14T10:00:00.000Z",
      finished_at: null,
      steps: [
        {
          id: "s1",
          step: "refine",
          status: "done",
          output: null,
          cost_usd: 0.01,
          model: "gpt-4o-mini",
          attempts: 1,
          error: null,
          started_at: "2026-10-14T10:00:00.000Z",
          finished_at: "2026-10-14T10:00:02.000Z",
        },
        {
          id: "s2",
          step: "clarify",
          status: "running",
          output: null,
          cost_usd: 0.01,
          model: "gpt-4o-mini",
          attempts: 1,
          error: null,
          started_at: "2026-10-14T10:00:02.000Z",
          finished_at: null,
        },
      ],
    };

    const state = mapRunToProgress(run);
    expect(state.status).toBe("awaiting_input");
    expect(state.currentStep).toBe("clarify");
    expect(stepAt(state, "clarify").status).toBe("running");
    expect(state.questions).toHaveLength(1);
  });

  it("treats the current step as running when its row is still queued", () => {
    const run: RunRead = {
      id: "run-paused",
      idea_id: "idea-1",
      version_id: "version-1",
      status: "awaiting_input",
      step: "clarify",
      cost_usd: 0,
      cost_cap_usd: 0.75,
      error: null,
      questions: [],
      started_at: "2026-10-14T10:00:00.000Z",
      finished_at: null,
      steps: [],
    };

    const state = mapRunToProgress(run);
    expect(stepAt(state, "clarify")).toMatchObject({ status: "running", startedAt: null });
  });
});
