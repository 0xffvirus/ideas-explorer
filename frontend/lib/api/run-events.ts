import type {
  ClarifyingQuestion,
  Run,
  RunEvent,
  RunStatus,
  RunStepName,
  StepStatus,
} from "./types";

const RUN_EVENT_TYPES = [
  "step_started",
  "step_completed",
  "step_failed",
  "cost_update",
  "awaiting_input",
  "run_done",
] as const;

const RUN_STEP_NAMES = [
  "refine",
  "clarify",
  "market",
  "competitors",
  "customers",
  "feasibility",
  "business_model",
  "critic",
] as const;

const RUN_STATUSES = ["queued", "running", "awaiting_input", "done", "failed", "partial"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isOneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === "string" && (options as readonly string[]).includes(value);
}

function optionalString(value: unknown): string | null | undefined {
  if (value === undefined || value === null) return null;
  return typeof value === "string" ? value : undefined;
}

function optionalNumber(value: unknown): number | null | undefined {
  if (value === undefined || value === null) return null;
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function parseQuestions(value: unknown): ClarifyingQuestion[] | null {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) return null;
  const questions: ClarifyingQuestion[] = [];
  for (const item of value) {
    if (!isRecord(item) || typeof item.id !== "string" || typeof item.question !== "string") {
      return null;
    }
    questions.push({
      id: item.id,
      question: item.question,
      help: typeof item.help === "string" ? item.help : null,
    });
  }
  return questions;
}

/**
 * Parse one SSE `data:` payload. Returns null on malformed input — a bad frame
 * must not kill the stream. Hand-rolled instead of zod: this runs per frame on
 * the hot path and the shape is fixed and small.
 */
export function parseRunEvent(
  data: string,
  fallbackId?: string,
  fallbackType?: string,
): RunEvent | null {
  let json: unknown;
  try {
    json = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(json)) return null;
  const candidate = !("type" in json) && fallbackType ? { ...json, type: fallbackType } : json;

  const { id, type, run_id, at, step, status, error, cost_usd, cost_cap_usd, questions } =
    candidate as Record<string, unknown>;

  if (!isOneOf(type, RUN_EVENT_TYPES)) return null;
  if (typeof run_id !== "string" || typeof at !== "string") return null;

  const parsedStep = optionalString(step);
  if (parsedStep === undefined) return null;
  if (parsedStep !== null && !isOneOf(parsedStep, RUN_STEP_NAMES)) return null;

  const parsedStatus = optionalString(status);
  if (parsedStatus === undefined) return null;
  if (parsedStatus !== null && !isOneOf(parsedStatus, RUN_STATUSES)) return null;

  const parsedError = optionalString(error);
  const parsedCost = optionalNumber(cost_usd);
  const parsedCap = optionalNumber(cost_cap_usd);
  const parsedQuestions = parseQuestions(questions);
  if (parsedError === undefined || parsedCost === undefined || parsedCap === undefined) return null;
  if (parsedQuestions === null) return null;

  return {
    id: typeof id === "string" ? id : (fallbackId ?? ""),
    type,
    run_id,
    at,
    step: parsedStep as RunStepName | null,
    status: parsedStatus as RunStatus | null,
    error: parsedError,
    cost_usd: parsedCost,
    cost_cap_usd: parsedCap,
    questions: parsedQuestions,
  };
}

export type RunProgress = {
  runId: string | null;
  events: RunEvent[];
  seenIds: Set<string>;
  steps: Partial<Record<RunStepName, StepStatus>>;
  activeStep: RunStepName | null;
  costUsd: number | null;
  costCapUsd: number | null;
  status: RunStatus | null;
  questions: ClarifyingQuestion[];
  error: string | null;
  lastEventId: string | null;
  done: boolean;
};

export type RunProgressAction =
  | { kind: "reset" }
  | { kind: "seed"; run: Run }
  | { kind: "event"; event: RunEvent }
  | { kind: "stream_error"; message: string };

export const initialProgress: RunProgress = {
  runId: null,
  events: [],
  seenIds: new Set(),
  steps: {},
  activeStep: null,
  costUsd: null,
  costCapUsd: null,
  status: null,
  questions: [],
  error: null,
  lastEventId: null,
  done: false,
};

const TERMINAL: RunStatus[] = ["done", "failed", "partial"];

export function seedProgress(run: Run): RunProgress {
  const steps: Partial<Record<RunStepName, StepStatus>> = {};
  for (const step of run.steps ?? []) {
    steps[step.step] = step.status;
  }
  return {
    ...initialProgress,
    runId: run.id,
    steps,
    activeStep: run.status === "running" ? (run.step ?? null) : null,
    costUsd: run.cost_usd,
    costCapUsd: run.cost_cap_usd,
    status: run.status,
    questions: run.questions ?? [],
    error: run.error ?? null,
    done: TERMINAL.includes(run.status),
  };
}

export function progressReducer(state: RunProgress, action: RunProgressAction): RunProgress {
  switch (action.kind) {
    case "reset":
      return { ...initialProgress, seenIds: new Set() };
    case "seed": {
      const seeded = seedProgress(action.run);
      // Re-seeding the same run (a section re-run) must keep the event cursor
      // and history; otherwise the stream would replay old events, including
      // an old run_done.
      if (state.runId === action.run.id) {
        return {
          ...seeded,
          events: state.events,
          seenIds: state.seenIds,
          lastEventId: state.lastEventId,
        };
      }
      return seeded;
    }
    case "stream_error":
      return { ...state, error: action.message };
    case "event": {
      const event = action.event;
      if (event.run_id !== state.runId) return state;
      if (event.id && state.seenIds.has(event.id)) return state;

      const seenIds = new Set(state.seenIds);
      if (event.id) seenIds.add(event.id);
      // Bound memory: keep a window of recent ids only.
      if (seenIds.size > 500) {
        const recent = state.events.slice(-400).map((e) => e.id);
        for (const id of seenIds) if (!recent.includes(id)) seenIds.delete(id);
      }

      const steps = { ...state.steps };
      let activeStep = state.activeStep;
      let error = state.error;
      let costUsd = state.costUsd;
      const costCapUsd = event.cost_cap_usd ?? state.costCapUsd;
      let status = state.status;
      let questions = state.questions;
      let done = state.done;

      if (event.step) {
        if (event.type === "step_started") steps[event.step] = "running";
        if (event.type === "step_completed") steps[event.step] = "done";
        if (event.type === "step_failed") steps[event.step] = "failed";
      }
      if (
        (event.type === "step_started" ||
          event.type === "step_completed" ||
          event.type === "step_failed" ||
          event.type === "cost_update") &&
        (status == null || status === "queued")
      ) {
        status = "running";
      }
      if (event.type === "step_started") activeStep = event.step ?? null;
      if (event.type === "step_completed" || event.type === "step_failed") {
        activeStep = activeStep === event.step ? null : activeStep;
      }
      if (event.type === "step_failed") error = event.error ?? "Step failed";
      if (event.cost_usd != null) costUsd = event.cost_usd;
      if (event.type === "awaiting_input") {
        status = "awaiting_input";
        questions = event.questions ?? [];
      }
      if (event.type === "run_done") {
        status = event.status ?? "done";
        done = TERMINAL.includes(status);
      }

      return {
        ...state,
        events: [...state.events, event].slice(-500),
        seenIds,
        steps,
        activeStep,
        costUsd,
        costCapUsd,
        status,
        questions,
        error,
        lastEventId: event.id || state.lastEventId,
        done,
      };
    }
  }
}
