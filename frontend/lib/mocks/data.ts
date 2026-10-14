import type {
  CreateIdeaRequest,
  CreateVersionRequest,
  IdeaDetail,
  IdeaList,
  IdeaSummary,
  IdeaVersion,
  ListIdeasParams,
  Report,
  RespondRunRequest,
  Run,
  RunEvent,
  RunStep,
  RunStepName,
  UpdateIdeaRequest,
} from "@/lib/api/types";
import {
  ALL_STEPS,
  BASE_TIME,
  buildBrief,
  buildReport,
  CATEGORIES,
  completedRun,
  FIXED_IDS,
  makeRunEvent,
  minutesAfter,
  mulberry32,
  pick,
  QUESTIONS,
  rawInputFor,
  TAG_POOL,
  titleFor,
  uuidFor,
} from "./seed";

export type MockDb = {
  ideas: Map<string, IdeaDetail>;
  runs: Map<string, Run>;
  runEvents: Map<string, RunEvent[]>;
  reports: Map<string, Report>;
  timers: Set<ReturnType<typeof setTimeout> | ReturnType<typeof setInterval>>;
  nextIndex: number;
};

const DATASET_SIZE = 1000;

let db: MockDb | null = null;

export function resetDb(): void {
  if (db) {
    for (const timer of db.timers) clearTimeout(timer as ReturnType<typeof setTimeout>);
    db.timers.clear();
  }
  db = null;
}

export function getDb(): MockDb {
  if (db) return db;
  const store: MockDb = {
    ideas: new Map(),
    runs: new Map(),
    runEvents: new Map(),
    reports: new Map(),
    timers: new Set(),
    nextIndex: 5000,
  };
  db = store;
  for (let i = 0; i < DATASET_SIZE; i += 1) seedIdea(store, i);
  return store;
}

function reportKey(ideaId: string, version: number): string {
  return `${ideaId}:${version}`;
}

function seedIdea(store: MockDb, index: number): void {
  const rand = mulberry32(index * 7919 + 13);
  const id =
    index === 0
      ? FIXED_IDS.dogWalking
      : index === 1
        ? FIXED_IDS.invoiceAi
        : index === 2
          ? FIXED_IDS.awaitingInput
          : index === 3
            ? FIXED_IDS.partialRun
            : uuidFor(index);
  const title =
    index === 0
      ? "Dog walking marketplace for pet owners"
      : index === 1
        ? "AI invoice reconciliation for freelancers"
        : index === 2
          ? "Therapy scheduling for small clinics"
          : index === 3
            ? "Restaurant inventory for independent shops"
            : titleFor(index);
  const rawInput = rawInputFor(title, index);
  const category =
    index === 0 ? "marketplace" : index === 1 ? "b2b_saas" : CATEGORIES[index % CATEGORIES.length];
  const createdAt = minutesAfter(BASE_TIME, -(index * 37 + 15));
  const tags =
    index === 0
      ? ["marketplace", "community", "mobile"]
      : index === 1
        ? ["ai", "fintech", "b2b"]
        : [TAG_POOL[index % TAG_POOL.length], TAG_POOL[(index * 3 + 1) % TAG_POOL.length]].filter(
            (tag, i, arr) => arr.indexOf(tag) === i,
          );

  const failed = index % 23 === 5 && index > 3;
  const queued = index % 17 === 3 && index > 3;
  const awaiting = index === 2;
  const version: IdeaVersion = {
    id: uuidFor(10_000 + index),
    idea_id: id,
    number: 1,
    raw_input: rawInput,
    context: index === 0 ? { target_region: "Austin, TX", audience_hint: "pet owners" } : null,
    brief: null,
    created_at: createdAt,
  };

  let detail: IdeaDetail = {
    id,
    title,
    status: queued ? "queued" : "done",
    verdict: null,
    category,
    overall_score: null,
    one_liner: null,
    pinned: index % 223 === 0,
    archived_at: index > 0 && index % 41 === 0 ? minutesAfter(BASE_TIME, -(index * 37)) : null,
    tags,
    created_at: createdAt,
    updated_at: createdAt,
    versions: [version],
    latest_version: version,
    latest_run: null,
  };

  if (failed) {
    const run: Run = queuedRun(detail, index);
    run.status = "failed";
    run.step = null;
    run.error = "Market step failed: web search provider returned 503 after retries.";
    run.steps = run.steps.map((step) =>
      step.step === "refine"
        ? { ...step, status: "done" }
        : step.step === "market"
          ? { ...step, status: "failed", error: run.error }
          : step,
    );
    detail = { ...detail, status: "failed", latest_run: run };
    store.runs.set(run.id, run);
  } else if (awaiting) {
    // A run paused for clarification — exercises the inline question form.
    const run = queuedRun(detail, index);
    run.status = "awaiting_input";
    run.step = "clarify";
    run.questions = QUESTIONS;
    run.steps = run.steps.map((step) =>
      step.step === "refine" ? { ...step, status: "done" } : step,
    );
    detail = { ...detail, status: "analyzing", latest_run: run };
    store.runs.set(run.id, run);
    store.runEvents.set(run.id, [
      makeRunEvent(run.id, "1", { type: "step_started", step: "refine", status: "running" }),
      makeRunEvent(run.id, "2", { type: "step_completed", step: "refine", cost_usd: 0.02 }),
      makeRunEvent(run.id, "3", {
        type: "awaiting_input",
        status: "awaiting_input",
        questions: QUESTIONS,
      }),
    ]);
  } else if (!queued) {
    const partial = index === 3;
    const run = completedRun(detail, index, { partial });
    const report = buildReport(
      rand,
      detail,
      run,
      partial ? { exclude: ["monetization_clarity"] } : undefined,
    );
    const brief = buildBrief(rand, title);
    version.brief = brief;
    detail = {
      ...detail,
      status: "done",
      title: brief.title,
      verdict: report.header.verdict,
      overall_score: report.header.overall_score,
      one_liner: brief.one_liner,
      latest_run: run,
    };
    store.runs.set(run.id, run);
    store.reports.set(reportKey(id, 1), report);
  } else {
    const run = queuedRun(detail, index);
    detail = { ...detail, latest_run: run };
    store.runs.set(run.id, run);
  }

  store.ideas.set(id, detail);
}

function queuedRun(idea: IdeaDetail, index: number): Run {
  const steps: RunStep[] = ALL_STEPS.map((step) => ({
    step,
    status: "pending",
    cost_usd: 0,
    model: null,
    attempts: 0,
    error: null,
    started_at: null,
    finished_at: null,
  }));
  return {
    id: uuidFor(20_000 + index),
    idea_id: idea.id,
    idea_version_id: idea.latest_version?.id ?? uuidFor(index),
    status: "queued",
    step: null,
    cost_usd: 0,
    cost_cap_usd: 0.75,
    error: null,
    steps,
    questions: [],
    created_at: new Date(BASE_TIME - index * 60_000).toISOString(),
    started_at: null,
    finished_at: null,
  };
}

/* ------------------------------------------------------------------ *
 * Querying
 * ------------------------------------------------------------------ */

const SYNONYMS: Record<string, string[]> = {
  pets: ["dog", "pet", "walking", "vet", "animal"],
  pet: ["dog", "walking"],
  dogs: ["dog"],
  invoices: ["invoice"],
  billing: ["invoice", "payments"],
  clinics: ["clinic", "therapy", "health"],
  food: ["restaurant", "meal", "grocery"],
  money: ["fintech", "payments", "invoice", "budget"],
  ai: ["ai"],
};

function haystack(idea: IdeaDetail): string {
  const brief = idea.latest_version?.brief;
  return [
    idea.title,
    idea.one_liner ?? "",
    brief?.problem ?? "",
    brief?.solution ?? "",
    brief?.target_users ?? "",
    idea.latest_version?.raw_input ?? "",
    idea.tags.join(" "),
  ]
    .join(" ")
    .toLowerCase();
}

export function searchIdeas(params: ListIdeasParams): IdeaList {
  const store = getDb();
  const all = [...store.ideas.values()];
  let items = all.filter((idea) => (params.archived ? true : !idea.archived_at));
  if (params.status) items = items.filter((idea) => idea.status === params.status);
  if (params.verdict) items = items.filter((idea) => idea.verdict === params.verdict);
  if (params.category) items = items.filter((idea) => idea.category === params.category);
  if (params.tag) items = items.filter((idea) => idea.tags.includes(params.tag as string));
  if (params.pinned != null) items = items.filter((idea) => idea.pinned === params.pinned);
  if (params.min_score != null)
    items = items.filter((idea) => (idea.overall_score ?? -1) >= params.min_score!);
  if (params.max_score != null)
    items = items.filter((idea) => (idea.overall_score ?? 101) <= params.max_score!);

  let matchMode: IdeaList["mode"] = null;
  const query = params.q?.trim().toLowerCase() ?? "";
  if (query) {
    const tokens = query.split(/\s+/).filter(Boolean);
    let sawDirect = false;
    let sawSemantic = false;
    const matched = items.filter((idea) => {
      const hay = haystack(idea);
      return tokens.every((token) => {
        if (hay.includes(token)) {
          sawDirect = true;
          return true;
        }
        const syn = SYNONYMS[token] ?? [];
        if (syn.some((s) => hay.includes(s))) {
          sawSemantic = true;
          return true;
        }
        return false;
      });
    });
    items = matched;
    if (params.mode === "keyword") matchMode = "keyword";
    else if (params.mode === "semantic") matchMode = "semantic";
    else matchMode = sawDirect ? "keyword" : sawSemantic ? "semantic" : "hybrid";
    if (params.mode === "semantic" && !sawSemantic && !sawDirect) matchMode = "semantic";
  }

  const sort = params.sort ?? "recent";
  items = [...items].sort((a, b) => {
    if (sort === "recent") {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return b.created_at.localeCompare(a.created_at);
    }
    if (sort === "score") {
      const sa = a.overall_score ?? -1;
      const sb = b.overall_score ?? -1;
      if (sa !== sb) return sb - sa;
      return b.created_at.localeCompare(a.created_at);
    }
    return a.title.localeCompare(b.title);
  });

  const limit = params.limit ?? 30;
  const offset = params.cursor ? Math.max(0, Number.parseInt(params.cursor, 10) || 0) : 0;
  const page = items.slice(offset, offset + limit);
  const next = offset + limit < items.length ? String(offset + limit) : null;
  return { items: page.map(summary), next_cursor: next, mode: matchMode };
}

function summary(detail: IdeaDetail): IdeaSummary {
  const {
    versions: _versions,
    latest_version: _latestVersion,
    latest_run: _latestRun,
    ...rest
  } = detail;
  return rest;
}

export function getIdea(id: string): IdeaDetail | undefined {
  return getDb().ideas.get(id);
}

export function getSimilar(id: string, limit: number): IdeaList {
  const store = getDb();
  const idea = store.ideas.get(id);
  if (!idea) return { items: [], next_cursor: null, mode: null };
  const scored = [...store.ideas.values()]
    .filter((other) => other.id !== id && !other.archived_at)
    .map((other) => {
      let score = 0;
      if (other.category && other.category === idea.category) score += 2;
      score += other.tags.filter((tag) => idea.tags.includes(tag)).length;
      return { other, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.other.title.localeCompare(b.other.title))
    .slice(0, limit)
    .map((entry) => summary(entry.other));
  return { items: scored, next_cursor: null, mode: null };
}

export function listTags(): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const idea of getDb().ideas.values()) {
    if (idea.archived_at) continue;
    for (const tag of idea.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

/* ------------------------------------------------------------------ *
 * Mutations
 * ------------------------------------------------------------------ */

export function createIdea(body: CreateIdeaRequest): IdeaDetail {
  const store = getDb();
  const index = store.nextIndex;
  store.nextIndex += 1;
  const now = new Date().toISOString();
  const id = uuidFor(index);
  const title = body.title?.trim() || body.raw_input.trim().slice(0, 60);
  const version: IdeaVersion = {
    id: uuidFor(30_000 + index),
    idea_id: id,
    number: 1,
    raw_input: body.raw_input,
    context: body.context ?? null,
    brief: null,
    created_at: now,
  };
  let detail: IdeaDetail = {
    id,
    title,
    status: body.analyze === false ? "draft" : "queued",
    verdict: null,
    category: null,
    overall_score: null,
    one_liner: null,
    pinned: false,
    archived_at: null,
    tags: [...new Set(body.tags ?? [])],
    created_at: now,
    updated_at: now,
    versions: [version],
    latest_version: version,
    latest_run: null,
  };
  if (body.analyze !== false) {
    const run = createSimulatedRun(detail, 1);
    detail = { ...detail, latest_run: run };
  }
  store.ideas.set(id, detail);
  return detail;
}

export function updateIdea(id: string, body: UpdateIdeaRequest): IdeaDetail | undefined {
  const store = getDb();
  const current = store.ideas.get(id);
  if (!current) return undefined;
  const next: IdeaDetail = {
    ...current,
    title: body.title?.trim() || current.title,
    tags: body.tags ? [...new Set(body.tags)] : current.tags,
    pinned: body.pinned ?? current.pinned,
    archived_at:
      body.archived === undefined
        ? current.archived_at
        : body.archived
          ? new Date().toISOString()
          : null,
    updated_at: new Date().toISOString(),
  };
  store.ideas.set(id, next);
  return next;
}

export function addVersion(id: string, body: CreateVersionRequest): IdeaDetail | undefined {
  const store = getDb();
  const current = store.ideas.get(id);
  if (!current) return undefined;
  const number = Math.max(...current.versions.map((v) => v.number)) + 1;
  const now = new Date().toISOString();
  const version: IdeaVersion = {
    id: uuidFor(40_000 + store.nextIndex),
    idea_id: id,
    number,
    raw_input: body.raw_input,
    context: body.context ?? null,
    brief: null,
    created_at: now,
  };
  let next: IdeaDetail = {
    ...current,
    status: body.analyze === false ? "draft" : "queued",
    versions: [...current.versions, version],
    latest_version: version,
    updated_at: now,
  };
  if (body.analyze !== false) {
    const run = createSimulatedRun(next, number);
    next = { ...next, latest_run: run };
  }
  store.ideas.set(id, next);
  return next;
}

/* ------------------------------------------------------------------ *
 * Run simulation
 * ------------------------------------------------------------------ */

export const SIM_STEP_MS = Number(process.env.NEXT_PUBLIC_MOCK_STEP_MS ?? 450);
// Re-runs are given their own (slower) clock so the progress window is observable in e2e.
export const SIM_RERUN_MS = Number(process.env.NEXT_PUBLIC_MOCK_RERUN_MS ?? SIM_STEP_MS * 2);

type SimOptions = { startAt?: number };

function createSimulatedRun(
  idea: IdeaDetail,
  versionNumber: number,
  options: SimOptions = {},
): Run {
  const store = getDb();
  const run: Run = queuedRun(idea, store.nextIndex);
  run.id = uuidFor(50_000 + store.nextIndex);
  run.idea_version_id = idea.latest_version?.id ?? run.idea_version_id;
  run.status = "queued";
  store.nextIndex += 1;
  store.runs.set(run.id, run);
  store.runEvents.set(run.id, []);

  const steps = ALL_STEPS;
  const start = options.startAt ?? 0;

  const updateRun = (mutate: (run: Run) => Run) => {
    const existing = store.runs.get(run.id);
    if (!existing) return;
    store.runs.set(run.id, mutate(existing));
  };

  const push = (event: Partial<RunEvent> & Pick<RunEvent, "type">) => {
    const events = store.runEvents.get(run.id) ?? [];
    const ev = makeRunEvent(run.id, String(events.length + 1), event);
    ev.at = new Date().toISOString();
    events.push(ev);
    store.runEvents.set(run.id, events);
  };

  let elapsed = 0;
  let cost = 0;
  const schedule = (offset: number, fn: () => void) => {
    const timer = setTimeout(() => {
      store.timers.delete(timer);
      fn();
    }, offset);
    store.timers.add(timer);
  };

  schedule(start, () => {
    updateRun((r) => ({ ...r, status: "running", started_at: new Date().toISOString() }));
    const current = store.ideas.get(idea.id);
    if (current)
      store.ideas.set(idea.id, {
        ...current,
        status: "analyzing",
        updated_at: new Date().toISOString(),
      });
  });

  for (let i = 0; i < steps.length; i += 1) {
    const step = steps[i];
    elapsed += SIM_STEP_MS;
    schedule(start + elapsed - SIM_STEP_MS + 30, () => {
      push({ type: "step_started", step, status: "running" });
      updateRun((r) => ({
        ...r,
        step,
        steps: r.steps.map((s) =>
          s.step === step
            ? {
                ...s,
                status: "running",
                started_at: new Date().toISOString(),
                attempts: s.attempts + 1,
              }
            : s,
        ),
      }));
    });
    const stepCost = Math.round((0.02 + (i % 4) * 0.015) * 1000) / 1000;
    elapsed += SIM_STEP_MS;
    schedule(start + elapsed - SIM_STEP_MS + 20, () => {
      cost = Math.round((cost + stepCost) * 1000) / 1000;
      push({ type: "step_completed", step, cost_usd: cost });
      push({ type: "cost_update", cost_usd: cost, cost_cap_usd: 0.75 });
      updateRun((r) => ({
        ...r,
        cost_usd: cost,
        steps: r.steps.map((s) =>
          s.step === step
            ? { ...s, status: "done", cost_usd: stepCost, finished_at: new Date().toISOString() }
            : s,
        ),
      }));
    });
  }

  elapsed += SIM_STEP_MS;
  schedule(start + elapsed, () => {
    const draftIdea = store.ideas.get(idea.id);
    if (!draftIdea) return;
    const latestRun = store.runs.get(run.id) ?? run;
    const finalRun: Run = {
      ...latestRun,
      status: "done",
      step: null,
      cost_usd: cost,
      finished_at: new Date().toISOString(),
    };
    const rand = mulberry32(idea.id.split("-")[0].length * 999 + cost * 1000);
    const report = buildReport(rand, draftIdea, finalRun);
    const brief = buildBrief(rand, draftIdea.title);
    const version = draftIdea.latest_version;
    if (version) version.brief = brief;
    const done: IdeaDetail = {
      ...draftIdea,
      status: "done",
      title: brief.title,
      verdict: report.header.verdict,
      overall_score: report.header.overall_score,
      one_liner: brief.one_liner,
      category: draftIdea.category ?? pick(rand, CATEGORIES),
      updated_at: new Date().toISOString(),
      latest_run: finalRun,
    };
    store.ideas.set(idea.id, done);
    store.runs.set(run.id, finalRun);
    store.reports.set(
      reportKey(idea.id, draftIdea.latest_version?.number ?? versionNumber),
      report,
    );
    push({ type: "run_done", status: "done", cost_usd: cost, cost_cap_usd: 0.75 });
  });

  return run;
}

export function rerunStep(runId: string, step: string): Run | undefined {
  const store = getDb();
  const run = store.runs.get(runId);
  if (!run) return undefined;
  const push = (event: Partial<RunEvent> & Pick<RunEvent, "type">) => {
    const events = store.runEvents.get(runId) ?? [];
    const ev = makeRunEvent(runId, String(events.length + 1), event);
    ev.at = new Date().toISOString();
    events.push(ev);
    store.runEvents.set(runId, events);
  };
  const next: Run = {
    ...run,
    status: "running",
    step: step as RunStepName,
    steps: run.steps.map((s) =>
      s.step === step ? { ...s, status: "running", attempts: s.attempts + 1 } : s,
    ),
  };
  store.runs.set(runId, next);
  const rerunIdea = store.ideas.get(next.idea_id);
  if (rerunIdea) {
    store.ideas.set(next.idea_id, {
      ...rerunIdea,
      status: "analyzing",
      updated_at: new Date().toISOString(),
      latest_run: next,
    });
  }
  push({ type: "step_started", step: step as RunStepName, status: "running" });
  const timer = setTimeout(() => {
    store.timers.delete(timer);
    const current = store.runs.get(runId);
    if (!current) return;
    const cost = Math.round((current.cost_usd + 0.04) * 100) / 100;
    const finished: Run = {
      ...current,
      status: "done",
      step: null,
      cost_usd: cost,
      finished_at: new Date().toISOString(),
      steps: current.steps.map((s) =>
        s.step === step
          ? {
              ...s,
              status: "done",
              cost_usd: (s.cost_usd ?? 0) + 0.04,
              finished_at: new Date().toISOString(),
            }
          : s,
      ),
    };
    store.runs.set(runId, finished);
    const finishedIdea = store.ideas.get(finished.idea_id);
    if (finishedIdea) {
      store.ideas.set(finished.idea_id, {
        ...finishedIdea,
        status: "done",
        updated_at: new Date().toISOString(),
        latest_run: finished,
      });
    }
    push({ type: "step_completed", step: step as RunStepName, cost_usd: cost });
    push({ type: "run_done", status: "done", cost_usd: cost, cost_cap_usd: finished.cost_cap_usd });
  }, SIM_RERUN_MS);
  store.timers.add(timer);
  return next;
}

export function respondToRun(runId: string, body: RespondRunRequest): Run | undefined {
  const store = getDb();
  const run = store.runs.get(runId);
  if (!run || run.status !== "awaiting_input") return undefined;
  const events = store.runEvents.get(runId) ?? [];
  const push = (event: Partial<RunEvent> & Pick<RunEvent, "type">) => {
    const ev = makeRunEvent(runId, String(events.length + 1), event);
    ev.at = new Date().toISOString();
    events.push(ev);
    store.runEvents.set(runId, events);
  };
  push({ type: "step_completed", step: "clarify", cost_usd: run.cost_usd });
  const resumed: Run = {
    ...run,
    status: "running",
    step: "market",
    questions: [],
    steps: run.steps.map((s) =>
      s.step === "clarify" ? { ...s, status: "done", finished_at: new Date().toISOString() } : s,
    ),
  };
  store.runs.set(runId, resumed);
  const resumedIdea = store.ideas.get(resumed.idea_id);
  if (resumedIdea) {
    store.ideas.set(resumed.idea_id, {
      ...resumedIdea,
      status: "analyzing",
      updated_at: new Date().toISOString(),
      latest_run: resumed,
    });
  }

  for (let i = 0; i < 3; i += 1) {
    const step = (["market", "competitors", "customers"] as RunStepName[])[i];
    const timer = setTimeout(
      () => {
        store.timers.delete(timer);
        const current = store.runs.get(runId);
        if (!current) return;
        push({ type: "step_started", step, status: "running" });
        push({ type: "step_completed", step, cost_usd: current.cost_usd + 0.03 });
        const updated: Run = {
          ...current,
          status: "running",
          step,
          steps: current.steps.map((s) =>
            s.step === step
              ? { ...s, status: "done", cost_usd: 0.03, finished_at: new Date().toISOString() }
              : s,
          ),
        };
        store.runs.set(runId, updated);
        if (i === 2) {
          const idea = store.ideas.get(updated.idea_id);
          if (idea) {
            const finalRun: Run = {
              ...updated,
              status: "done",
              step: null,
              finished_at: new Date().toISOString(),
            };
            const rand = mulberry32(idea.title.length * 131 + 7);
            const report = buildReport(rand, idea, finalRun);
            const brief = buildBrief(rand, idea.title);
            const version = idea.latest_version;
            if (version) version.brief = brief;
            push({
              type: "run_done",
              status: "done",
              cost_usd: updated.cost_usd,
              cost_cap_usd: updated.cost_cap_usd,
            });
            store.runs.set(runId, finalRun);
            store.reports.set(reportKey(idea.id, idea.latest_version?.number ?? 1), report);
            store.ideas.set(idea.id, {
              ...idea,
              status: "done",
              title: brief.title,
              verdict: report.header.verdict,
              overall_score: report.header.overall_score,
              one_liner: brief.one_liner,
              updated_at: new Date().toISOString(),
              latest_run: finalRun,
            });
          }
        }
      },
      500 + i * 700,
    );
    store.timers.add(timer);
  }
  push({ type: "cost_update", cost_usd: run.cost_usd, cost_cap_usd: run.cost_cap_usd });
  void body;
  return resumed;
}

/* ------------------------------------------------------------------ *
 * Reports
 * ------------------------------------------------------------------ */

export function getReport(ideaId: string, version?: number): Report | undefined {
  const store = getDb();
  const idea = store.ideas.get(ideaId);
  if (!idea) return undefined;
  const targets = version != null ? [version] : idea.versions.map((v) => v.number).reverse();
  for (const number of targets) {
    const report = store.reports.get(reportKey(ideaId, number));
    if (report) return report;
  }
  return undefined;
}
