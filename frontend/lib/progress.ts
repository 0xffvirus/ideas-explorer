import type { components } from "@/lib/api/schema";

/** Lifecycle of one analysis run (mirrors `RunRead.status`). */
export type RunStatus = "pending" | "running" | "awaiting_input" | "done" | "failed" | "partial";

export type StepStageStatus = "queued" | "running" | "done" | "failed" | "skipped";

/** Agent pipeline steps in execution order. */
export const PIPELINE_STEPS = [
  "classify",
  "refine",
  "clarify",
  "market",
  "competitors",
  "customers",
  "feasibility",
  "business_model",
  "critic",
] as const;

export type PipelineStep = (typeof PIPELINE_STEPS)[number];

export const PIPELINE_STEP_LABELS: Record<PipelineStep, string> = {
  classify: "Classify",
  refine: "Refine",
  clarify: "Clarify",
  market: "Market",
  competitors: "Competitors",
  customers: "Customers",
  feasibility: "Feasibility",
  business_model: "Business model",
  critic: "Critic",
};

export interface ProgressStep {
  step: PipelineStep;
  label: string;
  status: StepStageStatus;
  /** Wall-clock duration once the step settles. */
  elapsedMs: number;
  costUsd: number;
  error: string | null;
  /** Epoch ms of the step's start, used to compute `elapsedMs`. */
  startedAt: number | null;
}

export interface ProgressState {
  runId: string | null;
  status: RunStatus;
  currentStep: string | null;
  steps: ProgressStep[];
  costUsd: number;
  costCapUsd: number;
  questions: components["schemas"]["ClarifyingQuestion"][];
  failedSections: string[];
  error: string | null;
}

type RunEventBase = { receivedAt?: number };

export type RunEvent =
  | (RunEventBase & { type: "step_started"; step: string })
  | (RunEventBase & { type: "step_completed"; step: string; status?: string })
  | (RunEventBase & { type: "step_failed"; step: string; error: string })
  | (RunEventBase & { type: "cost_update"; cost_usd: number; cap_usd: number; step?: string })
  | (RunEventBase & {
      type: "run_paused";
      questions: components["schemas"]["ClarifyingQuestion"][];
      /** Step that paused; the backend pauses on `clarify`. */
      step?: string;
    })
  | (RunEventBase & {
      type: "run_done";
      status: RunStatus;
      cost_usd?: number;
      failed_sections?: string[];
      error?: string;
    });

export const initialProgressState: ProgressState = {
  runId: null,
  status: "pending",
  currentStep: null,
  steps: PIPELINE_STEPS.map((step) => ({
    step,
    label: PIPELINE_STEP_LABELS[step],
    status: "queued",
    elapsedMs: 0,
    costUsd: 0,
    error: null,
    startedAt: null,
  })),
  costUsd: 0,
  costCapUsd: 0,
  questions: [],
  failedSections: [],
  error: null,
};

export function isPipelineStep(value: string): value is PipelineStep {
  return (PIPELINE_STEPS as readonly string[]).includes(value);
}

const RUN_STATUSES: readonly RunStatus[] = [
  "pending",
  "running",
  "awaiting_input",
  "done",
  "failed",
  "partial",
];

export function isRunStatus(value: string): value is RunStatus {
  return (RUN_STATUSES as readonly string[]).includes(value);
}

function mapStepStatus(status: string | undefined): StepStageStatus {
  switch (status) {
    case "running":
      return "running";
    case "done":
      return "done";
    case "failed":
      return "failed";
    case "skipped":
      return "skipped";
    default:
      return "queued";
  }
}

function settleStep(row: ProgressStep, status: StepStageStatus, at: number): ProgressStep {
  const elapsedMs =
    row.status === "running" && row.startedAt !== null && at > row.startedAt
      ? at - row.startedAt
      : row.elapsedMs;
  return { ...row, status, elapsedMs };
}

/**
 * Pure reducer over SSE / `RunRead` data. Missing timestamps are tolerated:
 * `receivedAt` is attached by the SSE layer in the browser and passed
 * explicitly in tests.
 */
export function reduceRunEvents(state: ProgressState, event: RunEvent): ProgressState {
  const at = event.receivedAt ?? 0;
  switch (event.type) {
    case "step_started": {
      if (!isPipelineStep(event.step)) return state;
      return {
        ...state,
        // A resumed run (awaiting_input -> running) continues from the first
        // new `step_started`, so any non-running status flips back here.
        status: "running",
        currentStep: event.step,
        steps: state.steps.map((row) =>
          row.step === event.step
            ? { ...row, status: "running", startedAt: at > 0 ? at : row.startedAt, error: null }
            : row,
        ),
      };
    }
    case "step_completed": {
      if (!isPipelineStep(event.step)) return state;
      const status: StepStageStatus =
        event.status === "failed" ? "failed" : event.status === "skipped" ? "skipped" : "done";
      return {
        ...state,
        steps: state.steps.map((row) =>
          row.step === event.step ? settleStep(row, status, at) : row,
        ),
      };
    }
    case "step_failed": {
      if (!isPipelineStep(event.step)) return state;
      return {
        ...state,
        error: event.error,
        steps: state.steps.map((row) =>
          row.step === event.step ? { ...settleStep(row, "failed", at), error: event.error } : row,
        ),
      };
    }
    case "cost_update": {
      const delta = Math.max(event.cost_usd - state.costUsd, 0);
      return {
        ...state,
        costUsd: event.cost_usd,
        costCapUsd: event.cap_usd > 0 ? event.cap_usd : state.costCapUsd,
        steps:
          event.step && isPipelineStep(event.step) && delta > 0
            ? state.steps.map((row) =>
                row.step === event.step ? { ...row, costUsd: row.costUsd + delta } : row,
              )
            : state.steps,
      };
    }
    case "run_paused": {
      const step = event.step;
      return {
        ...state,
        status: "awaiting_input",
        currentStep: step && isPipelineStep(step) ? step : state.currentStep,
        questions: event.questions,
        steps: state.steps.map((row) => {
          // The paused step is still in flight, not queued: show it running so
          // the timeline matches the waiting state.
          if (row.step !== step || !isPipelineStep(step)) return row;
          if (row.status === "done" || row.status === "failed" || row.status === "skipped") {
            return row;
          }
          return {
            ...row,
            status: "running",
            startedAt: row.startedAt ?? (at > 0 ? at : row.startedAt),
          };
        }),
      };
    }
    case "run_done": {
      const failed = new Set(event.failed_sections ?? []);
      return {
        ...state,
        status: event.status,
        currentStep: null,
        costUsd: typeof event.cost_usd === "number" ? event.cost_usd : state.costUsd,
        failedSections: event.failed_sections ?? state.failedSections,
        error: event.error ?? state.error,
        steps: state.steps.map((row) => {
          if (failed.has(row.step)) return settleStep(row, "failed", at);
          if (row.status === "running") {
            return settleStep(row, event.status === "failed" ? "failed" : "done", at);
          }
          if (row.status === "queued") return { ...row, status: "skipped" };
          return row;
        }),
      };
    }
  }
}

function parseTimestamp(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? null : parsed;
}

/** Map a persisted `RunRead` (from `GET /runs/{id}`) into progress rows. */
export function mapRunToProgress(run: components["schemas"]["RunRead"]): ProgressState {
  const byName = new Map((run.steps ?? []).map((row) => [row.step, row]));
  const running = run.status === "running" || run.status === "awaiting_input";
  const current = running ? run.step : null;
  const steps = PIPELINE_STEPS.map((step): ProgressStep => {
    const row = byName.get(step);
    const startedAt = parseTimestamp(row?.started_at);
    const finishedAt = parseTimestamp(row?.finished_at);
    const mapped = mapStepStatus(row?.status);
    return {
      step,
      label: PIPELINE_STEP_LABELS[step],
      // The current step is in flight even if its persisted row has not caught
      // up yet (e.g. a run paused on `clarify` between polls).
      status: step === current && mapped === "queued" ? "running" : mapped,
      elapsedMs:
        startedAt !== null && finishedAt !== null ? Math.max(finishedAt - startedAt, 0) : 0,
      costUsd: row?.cost_usd ?? 0,
      error: row?.error ?? null,
      startedAt,
    };
  });
  return {
    runId: run.id,
    status: isRunStatus(run.status) ? run.status : "running",
    currentStep: current,
    steps,
    costUsd: run.cost_usd,
    costCapUsd: run.cost_cap_usd,
    questions: run.questions ?? [],
    failedSections: [],
    error: run.error,
  };
}

/** Percentage of pipeline steps that have settled (done, failed or skipped). */
export function progressPercent(state: ProgressState): number {
  if (state.steps.length === 0) return 0;
  const settled = state.steps.filter(
    (step) => step.status !== "queued" && step.status !== "running",
  );
  return Math.round((settled.length / state.steps.length) * 100);
}

export function isRunActive(status: RunStatus): boolean {
  return status === "pending" || status === "running" || status === "awaiting_input";
}
