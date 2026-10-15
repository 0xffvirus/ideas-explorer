import { http, HttpResponse } from "msw";

import { API_BASE_URL } from "@/lib/api/client";
import type {
  ClarifyingQuestion,
  IdeaCreate,
  IdeaUpdate,
  RunRead,
  RunStepRead,
  SearchMode,
} from "@/lib/api/types";
import {
  BASE_IDEAS,
  BASE_RUNS,
  CLARIFY_QUESTIONS,
  compareReportFor,
  ideaDetail,
  ideaSummary,
  MOCK_IDEA_IDS,
  MOCK_RUN_IDS,
  reportFor,
  type MockIdea,
} from "./fixtures";

const api = `${API_BASE_URL}`;

/** One scripted SSE event, optionally delayed before it is emitted. */
export interface SseScriptEvent {
  event: string;
  data: Record<string, unknown>;
  /** Milliseconds to wait before emitting (default 60). */
  delay?: number;
}

/** Pause the stream until the run's clarifier is answered or skipped. */
export interface SseScriptWait {
  wait: "clarify";
}

export type SseScriptEntry = SseScriptEvent | SseScriptWait;

/** Mutable store backing every mock handler; reset between tests. */
let ideas: MockIdea[] = [];
let runsById = new Map<string, RunRead>();
let runsByIdea = new Map<string, string[]>();
let runScripts = new Map<string, SseScriptEntry[]>();
/** Next script index per run, so a reconnect continues instead of replaying. */
let runScriptCursor = new Map<string, number>();
let runClosers = new Map<string, () => void>();

function pipelineTail(startCost: number): SseScriptEntry[] {
  const steps: Array<[string, number]> = [
    ["market", 0.08],
    ["competitors", 0.07],
    ["customers", 0.09],
    ["feasibility", 0.06],
    ["business_model", 0.06],
    ["critic", 0.03],
  ];
  const entries: SseScriptEntry[] = [];
  let total = startCost;
  for (const [step, cost] of steps) {
    total = Number((total + cost).toFixed(2));
    entries.push({ event: "step_started", data: { step } });
    entries.push({ event: "cost_update", data: { cost_usd: total, cap_usd: 0.75, step } });
    entries.push({ event: "step_completed", data: { step, status: "done" } });
  }
  entries.push({ event: "run_done", data: { status: "done", cost_usd: total, failed_sections: [] } });
  return entries;
}

/** Full happy-path script used for freshly created runs. */
function pipelineScript(): SseScriptEntry[] {
  const entries: SseScriptEntry[] = [
    { event: "step_started", data: { step: "classify" } },
    { event: "cost_update", data: { cost_usd: 0.01, cap_usd: 0.75, step: "classify" } },
    { event: "step_completed", data: { step: "classify", status: "done" } },
    { event: "step_started", data: { step: "refine" } },
    { event: "cost_update", data: { cost_usd: 0.02, cap_usd: 0.75, step: "refine" } },
    { event: "step_completed", data: { step: "refine", status: "done" } },
  ];
  return [...entries, ...pipelineTail(0.02)];
}

/** Script that pauses for the clarifier after the refine step. */
function clarifyScript(): SseScriptEntry[] {
  return [
    { event: "step_started", data: { step: "classify" } },
    { event: "cost_update", data: { cost_usd: 0.01, cap_usd: 0.75, step: "classify" } },
    { event: "step_completed", data: { step: "classify", status: "done" } },
    { event: "step_started", data: { step: "refine" } },
    { event: "cost_update", data: { cost_usd: 0.02, cap_usd: 0.75, step: "refine" } },
    { event: "step_completed", data: { step: "refine", status: "done" } },
    { event: "step_started", data: { step: "clarify" } },
    { event: "run_paused", data: { step: "clarify", questions: CLARIFY_QUESTIONS } },
    { wait: "clarify" },
    ...pipelineTail(0.02),
  ];
}

/** Short script re-running a single section, kept running long enough to see. */
function rerunScript(step: string, currentCost: number): SseScriptEntry[] {
  const total = Number((currentCost + 0.02).toFixed(2));
  return [
    { event: "step_started", data: { step }, delay: 300 },
    { event: "cost_update", data: { cost_usd: total, cap_usd: 0.75, step }, delay: 100 },
    { event: "step_completed", data: { step, status: "done" }, delay: 1500 },
    { event: "run_done", data: { status: "partial", cost_usd: total, failed_sections: [] } },
  ];
}

export function resetMockStore(): void {
  ideas = BASE_IDEAS.map((idea) => ({ ...idea, tags: [...(idea.tags ?? [])] }));
  runsById = new Map();
  runsByIdea = new Map();
  runScripts = new Map();
  runScriptCursor = new Map();
  runClosers = new Map();
  for (const run of BASE_RUNS) {
    const copy: RunRead = { ...run, steps: (run.steps ?? []).map((step) => ({ ...step })) };
    runsById.set(copy.id, copy);
    runsByIdea.set(copy.idea_id, [...(runsByIdea.get(copy.idea_id) ?? []), copy.id]);
  }
  runScripts.set(MOCK_RUN_IDS.clarifyDemo, clarifyScript());
}

resetMockStore();

/** Test seam: insert or replace a run, optionally with an SSE script. */
export function seedRun(run: RunRead, script?: SseScriptEntry[]): void {
  const copy: RunRead = { ...run, steps: (run.steps ?? []).map((step) => ({ ...step })) };
  runsById.set(copy.id, copy);
  const existing = runsByIdea.get(copy.idea_id) ?? [];
  if (!existing.includes(copy.id)) runsByIdea.set(copy.idea_id, [...existing, copy.id]);
  if (script) {
    runScripts.set(copy.id, script);
    runScriptCursor.delete(copy.id);
  }
}

/** Test seam: insert or replace an idea fixture. */
export function seedIdea(idea: MockIdea): void {
  const index = ideas.findIndex((item) => item.id === idea.id);
  if (index >= 0) ideas[index] = idea;
  else ideas = [idea, ...ideas];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function deriveTitle(rawInput: string): string {
  const trimmed = rawInput.trim();
  const firstSentence = trimmed.split(/[.!?\n]/)[0]?.trim() || trimmed;
  const words = firstSentence.split(/\s+/);
  const short = words.slice(0, 8).join(" ");
  return words.length > 8 ? `${short}…` : short;
}

function matchScore(value: number | null | undefined, min: number | null, max: number | null) {
  if (min === null && max === null) return true;
  if (value === null || value === undefined) return false;
  if (min !== null && value < min) return false;
  if (max !== null && value > max) return false;
  return true;
}

function searchableText(idea: MockIdea, mode: SearchMode): string {
  const title = idea.title.toLowerCase();
  const raw = idea.raw_input.toLowerCase();
  const brief = idea.brief.toLowerCase();
  switch (mode) {
    case "keyword":
      return `${title} ${raw}`;
    case "semantic":
      return `${brief} ${raw}`;
    default:
      return `${title} ${brief} ${raw}`;
  }
}

function toNumber(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function ensureStep(run: RunRead, step: string): RunStepRead {
  const existing = (run.steps ?? []).find((row) => row.step === step);
  if (existing) return existing;
  const row: RunStepRead = {
    id: `${run.id}:${step}`,
    step,
    status: "queued",
    output: null,
    cost_usd: 0,
    model: null,
    attempts: 1,
    error: null,
    started_at: null,
    finished_at: null,
  };
  run.steps = [...(run.steps ?? []), row];
  return row;
}

function parseQuestions(value: unknown): ClarifyingQuestion[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.question !== "string") return [];
    return [{ question: item.question, why: typeof item.why === "string" ? item.why : "" }];
  });
}

/** Keep the persisted run/idea consistent with the scripted event stream. */
function applyScriptEvent(runId: string, entry: SseScriptEvent): void {
  const run = runsById.get(runId);
  if (!run) return;
  const data = entry.data;

  switch (entry.event) {
    case "step_started": {
      const step = typeof data.step === "string" ? data.step : "";
      if (step === "") return;
      const row = ensureStep(run, step);
      row.status = "running";
      row.started_at = new Date().toISOString();
      run.status = "running";
      run.step = step;
      break;
    }
    case "cost_update": {
      const step = typeof data.step === "string" ? data.step : "";
      const nextCost = typeof data.cost_usd === "number" ? data.cost_usd : run.cost_usd;
      const delta = Math.max(nextCost - run.cost_usd, 0);
      run.cost_usd = nextCost;
      if (step !== "") ensureStep(run, step).cost_usd += delta;
      break;
    }
    case "step_completed": {
      const step = typeof data.step === "string" ? data.step : "";
      if (step === "") return;
      const row = ensureStep(run, step);
      row.status = typeof data.status === "string" ? data.status : "done";
      row.finished_at = new Date().toISOString();
      break;
    }
    case "run_paused": {
      run.status = "awaiting_input";
      run.questions = parseQuestions(data.questions);
      break;
    }
    case "run_done": {
      const status = typeof data.status === "string" ? data.status : "done";
      run.status = status;
      run.finished_at = new Date().toISOString();
      run.cost_usd = typeof data.cost_usd === "number" ? data.cost_usd : run.cost_usd;
      const idea = ideas.find((item) => item.id === run.idea_id);
      if (!idea) return;
      idea.updated_at = new Date().toISOString();
      if (status === "failed") {
        idea.status = "failed";
        return;
      }
      idea.status = "done";
      idea.verdict = idea.verdict ?? "pursue";
      idea.overall_score = idea.overall_score ?? 67.5;
      idea.category = idea.category ?? "Consumer";
      break;
    }
    default:
      break;
  }
}

export const handlers = [
  http.get(`${api}/ideas`, ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get("q") ?? "").trim().toLowerCase();
    const mode = (url.searchParams.get("mode") ?? "hybrid") as SearchMode;
    const status = url.searchParams.get("status");
    const verdict = url.searchParams.get("verdict");
    const category = url.searchParams.get("category");
    const tag = url.searchParams.get("tag");
    const pinned = url.searchParams.get("pinned");
    const includeArchived = url.searchParams.get("archived") === "true";
    const scoreMin = toNumber(url.searchParams.get("score_min"));
    const scoreMax = toNumber(url.searchParams.get("score_max"));
    const sort = url.searchParams.get("sort") ?? "recent";
    const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? "30") || 30, 1), 100);
    const cursor = url.searchParams.get("cursor") ?? "";
    const offset = cursor.startsWith("offset:") ? Number(cursor.slice("offset:".length)) || 0 : 0;

    let items = ideas.filter((idea) => {
      if (!includeArchived && idea.archived_at !== null) return false;
      if (status && idea.status !== status) return false;
      if (verdict && idea.verdict !== verdict) return false;
      if (category && idea.category !== category) return false;
      if (tag && !(idea.tags ?? []).includes(tag)) return false;
      if (pinned === "true" && !idea.pinned) return false;
      if (pinned === "false" && idea.pinned) return false;
      if (!matchScore(idea.overall_score, scoreMin, scoreMax)) return false;
      if (q && !searchableText(idea, mode).includes(q)) return false;
      return true;
    });

    if (sort === "title") {
      items = [...items].sort((a, b) => a.title.localeCompare(b.title));
    } else if (sort === "score") {
      items = [...items].sort((a, b) => (b.overall_score ?? -1) - (a.overall_score ?? -1));
    } else {
      items = [...items].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
    }

    const page = items.slice(offset, offset + limit);
    const nextOffset = offset + limit;
    const nextCursor = nextOffset < items.length ? `offset:${nextOffset}` : null;
    return HttpResponse.json({ items: page.map(ideaSummary), next_cursor: nextCursor });
  }),

  http.post(`${api}/ideas`, async ({ request }) => {
    const payload: unknown = await request.json();
    if (
      !isRecord(payload) ||
      typeof payload.raw_input !== "string" ||
      payload.raw_input.trim() === ""
    ) {
      return HttpResponse.json(
        {
          detail: [{ loc: ["body", "raw_input"], msg: "Field required", type: "missing" }],
        },
        { status: 422 },
      );
    }
    const body = payload as Partial<IdeaCreate> & { raw_input: string };
    const now = new Date().toISOString();
    const idea: MockIdea = {
      id: crypto.randomUUID(),
      version_id: crypto.randomUUID(),
      title:
        typeof body.title === "string" && body.title.trim() !== ""
          ? body.title
          : deriveTitle(body.raw_input),
      status: body.analyze === false ? "draft" : "queued",
      verdict: null,
      category: null,
      overall_score: null,
      pinned: false,
      archived_at: null,
      created_at: now,
      updated_at: now,
      tags: Array.isArray(body.tags) ? body.tags : [],
      latest_version_number: 1,
      raw_input: body.raw_input,
      brief: body.raw_input,
    };
    ideas = [idea, ...ideas];
    if (idea.status === "queued") {
      const runId = crypto.randomUUID();
      const run: RunRead = {
        id: runId,
        idea_id: idea.id,
        version_id: idea.version_id,
        status: "pending",
        step: "classify",
        cost_usd: 0,
        cost_cap_usd: 0.75,
        error: null,
        questions: null,
        started_at: now,
        finished_at: null,
        steps: [],
      };
      runsById.set(runId, run);
      runsByIdea.set(idea.id, [runId]);
      runScripts.set(runId, pipelineScript());
    }
    return HttpResponse.json(ideaDetail(idea), { status: 201 });
  }),

  http.get(`${api}/ideas/:ideaId`, ({ params }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    return HttpResponse.json(ideaDetail(idea));
  }),

  http.patch(`${api}/ideas/:ideaId`, async ({ params, request }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    const body = (await request.json()) as IdeaUpdate;
    if (typeof body.title === "string") idea.title = body.title;
    if (Array.isArray(body.tags)) idea.tags = body.tags;
    if (typeof body.pinned === "boolean") idea.pinned = body.pinned;
    if (typeof body.archived === "boolean") {
      idea.archived_at = body.archived ? new Date().toISOString() : null;
    }
    idea.updated_at = new Date().toISOString();
    return HttpResponse.json(ideaDetail(idea));
  }),

  http.post(`${api}/ideas/:ideaId/versions`, async ({ params, request }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    const payload: unknown = await request.json();
    if (!isRecord(payload) || typeof payload.raw_input !== "string") {
      return HttpResponse.json({ detail: "raw_input is required" }, { status: 422 });
    }
    idea.latest_version_number += 1;
    idea.version_id = crypto.randomUUID();
    idea.raw_input = payload.raw_input;
    idea.updated_at = new Date().toISOString();
    if (payload.analyze !== false) {
      const now = new Date().toISOString();
      idea.status = "queued";
      const runId = crypto.randomUUID();
      const run: RunRead = {
        id: runId,
        idea_id: idea.id,
        version_id: idea.version_id,
        status: "pending",
        step: "classify",
        cost_usd: 0,
        cost_cap_usd: 0.75,
        error: null,
        questions: null,
        started_at: now,
        finished_at: null,
        steps: [],
      };
      runsById.set(runId, run);
      runsByIdea.set(idea.id, [runId, ...(runsByIdea.get(idea.id) ?? [])]);
      runScripts.set(runId, pipelineScript());
    }
    return HttpResponse.json(ideaDetail(idea), { status: 201 });
  }),

  http.get(`${api}/ideas/:ideaId/similar`, ({ params }) => {
    const similar = ideas
      .filter((item) => item.id !== params.ideaId)
      .slice(0, 3)
      .map((item) => ({ id: item.id, title: item.title, distance: 0.2 }));
    return HttpResponse.json(similar);
  }),

  http.get(`${api}/tags`, () => {
    const counts = new Map<string, number>();
    for (const idea of ideas) {
      for (const tag of idea.tags ?? []) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return HttpResponse.json([...counts.entries()].map(([name, count]) => ({ name, count })));
  }),

  http.get(`${api}/ideas/:ideaId/runs`, ({ params }) => {
    const runIds = runsByIdea.get(String(params.ideaId)) ?? [];
    const runs = runIds
      .map((id) => runsById.get(id))
      .filter((run): run is RunRead => Boolean(run))
      .sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at));
    return HttpResponse.json(runs);
  }),

  http.get(`${api}/runs/:runId`, ({ params }) => {
    const run = runsById.get(String(params.runId));
    if (!run) return HttpResponse.json({ detail: "run not found" }, { status: 404 });
    return HttpResponse.json(run);
  }),

  // Mirrors the API: POST enqueues the rerun, resets the run to `pending` with
  // the target step, and the worker later streams progress. Keeping the run
  // `pending` (active) here is what lets the client re-arm its SSE subscription
  // and swap the stale report for the progress panel.
  http.post(`${api}/runs/:runId/steps/:step/rerun`, ({ params }) => {
    const run = runsById.get(String(params.runId));
    if (!run) return HttpResponse.json({ detail: "run not found" }, { status: 404 });
    const step = String(params.step);
    runClosers.get(run.id)?.();
    runScripts.set(run.id, rerunScript(step, run.cost_usd));
    runScriptCursor.set(run.id, 0);
    const updated: RunRead = {
      ...run,
      status: "pending",
      step,
      questions: null,
      finished_at: null,
    };
    runsById.set(updated.id, updated);
    return HttpResponse.json(updated, { status: 202 });
  }),

  http.post(`${api}/runs/:runId/clarify`, ({ params }) => {
    const run = runsById.get(String(params.runId));
    if (!run) return HttpResponse.json({ detail: "run not found" }, { status: 404 });
    const clarify = ensureStep(run, "clarify");
    clarify.status = "done";
    clarify.finished_at = new Date().toISOString();
    const updated: RunRead = { ...run, status: "running", questions: null };
    runsById.set(updated.id, updated);
    // The client closed the stream when the run paused; the next connection
    // skips the script's `wait` entry and continues from the cursor.
    return HttpResponse.json(updated, { status: 202 });
  }),

  // SSE stream: scripted events (per run) from a persistent cursor, so closing
  // and reconnecting (pause -> clarify -> resume) continues instead of
  // replaying. Once the script is exhausted the stream stays open with pings.
  http.get(`${api}/runs/:runId/events`, ({ params }) => {
    const run = runsById.get(String(params.runId));
    if (!run) return new HttpResponse(null, { status: 404 });

    const script: SseScriptEntry[] = runScripts.get(run.id) ?? [
      { event: "step_started", data: { step: "classify" } },
      {
        event: "cost_update",
        data: { cost_usd: 0.01, cap_usd: run.cost_cap_usd, step: "classify" },
      },
      { event: "step_completed", data: { step: "classify" } },
      { event: "step_started", data: { step: "refine" } },
    ];

    const encoder = new TextEncoder();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ping: ReturnType<typeof setInterval> | undefined;
    let closed = false;

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        let index = runScriptCursor.get(run.id) ?? 0;

        const stop = () => {
          closed = true;
          if (timer) clearTimeout(timer);
          if (ping) clearInterval(ping);
          runClosers.delete(run.id);
        };

        const keepAlive = () => {
          if (closed || ping) return;
          ping = setInterval(() => {
            if (!closed) controller.enqueue(encoder.encode(": ping\n\n"));
          }, 15_000);
        };

        const push = () => {
          if (closed) return;
          if (index >= script.length) {
            runScriptCursor.set(run.id, index);
            keepAlive();
            return;
          }
          const entry = script[index];
          let nextDelay = 100;
          if ("wait" in entry) {
            // The real stream ends after the pause event. While the run still
            // awaits input there is nothing more to send; after the clarifier
            // is answered the next connection skips the wait and continues.
            if (run.status === "awaiting_input") {
              runScriptCursor.set(run.id, index);
              stop();
              controller.close();
              return;
            }
            index += 1;
          } else {
            index += 1;
            nextDelay = entry.delay ?? 100;
            applyScriptEvent(run.id, entry);
            controller.enqueue(
              encoder.encode(
                `id: ${index}\nevent: ${entry.event}\ndata: ${JSON.stringify(entry.data)}\n\n`,
              ),
            );
          }
          runScriptCursor.set(run.id, index);
          timer = setTimeout(push, nextDelay);
        };

        runClosers.set(run.id, stop);
        timer = setTimeout(push, 20);
      },
      cancel() {
        closed = true;
        if (timer) clearTimeout(timer);
        if (ping) clearInterval(ping);
        runClosers.delete(run.id);
      },
    });

    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }),

  http.get(`${api}/ideas/:ideaId/report`, ({ params, request }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    if (idea.status !== "done") {
      return HttpResponse.json({ detail: "no completed run for this idea" }, { status: 404 });
    }
    const report = reportFor(idea);
    const version = new URL(request.url).searchParams.get("version");
    if (version !== null && version !== "" && Number(version) !== idea.latest_version_number) {
      report.header = { ...report.header, one_liner: `${idea.brief} · version ${version}` };
    }
    return HttpResponse.json(report);
  }),

  http.get(`${api}/ideas/:ideaId/report.md`, ({ params }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    return new HttpResponse(`# ${idea.title}\n\n${idea.brief}\n`, {
      headers: { "Content-Type": "text/markdown" },
    });
  }),

  http.get(`${api}/ideas/:ideaId/report.pdf`, ({ params }) => {
    const idea = ideas.find((item) => item.id === params.ideaId);
    if (!idea) return HttpResponse.json({ detail: "idea not found" }, { status: 404 });
    return new HttpResponse("%PDF-1.4 mock", {
      headers: { "Content-Type": "application/pdf" },
    });
  }),

  http.get(`${api}/compare`, ({ request }) => {
    const url = new URL(request.url);
    const ids = (url.searchParams.get("ids") ?? "")
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    if (ids.length < 2 || ids.length > 3) {
      return HttpResponse.json({ detail: "compare requires 2 to 3 idea ids" }, { status: 422 });
    }
    const entries = ids.flatMap((id) => {
      const idea = ideas.find((item) => item.id === id);
      return idea ? [idea] : [];
    });
    return HttpResponse.json(compareReportFor(entries));
  }),
];

export const MOCK_API = api;
export { MOCK_IDEA_IDS };
