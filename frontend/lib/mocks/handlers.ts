import { http, HttpResponse } from "msw";
import { API_URL } from "@/lib/api/client";
import type { Report, RunEvent } from "@/lib/api/types";
import * as db from "./data";

const base = API_URL;

function notFound(detail = "Not found") {
  return HttpResponse.json({ detail }, { status: 404 });
}

function validationError(detail: { loc: (string | number)[]; msg: string; type: string }[]) {
  return HttpResponse.json({ detail }, { status: 422 });
}

function checkRawInput(raw: unknown) {
  if (typeof raw !== "string" || raw.trim().length === 0) {
    return validationError([
      { loc: ["body", "raw_input"], msg: "Input is required", type: "value_error" },
    ]);
  }
  if (raw.length > 5000) {
    return validationError([
      {
        loc: ["body", "raw_input"],
        msg: "Input must be 5,000 characters or fewer",
        type: "value_error",
      },
    ]);
  }
  return null;
}

function reportToMarkdown(report: Report, ideaTitle: string): string {
  const lines: string[] = [];
  lines.push(`# ${report.header.title || ideaTitle}`, "");
  if (report.header.one_liner) lines.push(`> ${report.header.one_liner}`, "");
  lines.push(
    `**Verdict:** ${report.header.verdict ?? "unscored"} · **Score:** ${
      report.header.overall_score ?? "n/a"
    }/100${report.header.partial ? " · partial run" : ""}`,
    "",
    "## Scorecard",
    "",
  );
  for (const dim of report.scorecard.dimensions) {
    lines.push(
      `- **${dim.label}** — ${dim.not_scored ? "not scored" : `${dim.score}/5`}${
        dim.needs_review ? " (needs review)" : ""
      }`,
    );
  }
  lines.push("", "## Sources", "");
  for (const source of report.sources)
    lines.push(`${source.number}. [${source.title}](${source.url})`);
  lines.push("");
  return lines.join("\n");
}

function minimalPdf(title: string): Uint8Array {
  const text = title.replace(/[()\\]/g, " ").slice(0, 80) || "Idea Forge report";
  const content = `BT /F1 18 Tf 72 720 Td (${text}) Tj ET`;
  const objects = [
    "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
    "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
    "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
    `4 0 obj << /Length ${content.length} >> stream\n${content}\nendstream endobj`,
    "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (const obj of objects) {
    offsets.push(pdf.length);
    pdf += `${obj}\n`;
  }
  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
  return new TextEncoder().encode(pdf);
}

function sseStream(
  runId: string,
  lastEventId: string | null,
  signal: AbortSignal,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      let cursor = lastEventId ? Math.max(0, Number.parseInt(lastEventId, 10) || 0) : 0;
      let closed = false;
      const close = () => {
        if (closed) return;
        closed = true;
        try {
          controller.close();
        } catch {
          // already closed
        }
      };
      if (signal.aborted) {
        close();
        return;
      }
      signal.addEventListener("abort", close, { once: true });

      while (!closed) {
        if (signal.aborted) return;
        const store = db.getDb();
        const events = store.runEvents.get(runId) ?? [];
        const next = events[cursor];
        if (next) {
          const payload = `id: ${cursor + 1}\nevent: ${next.type}\ndata: ${JSON.stringify(next)}\n\n`;
          try {
            controller.enqueue(encoder.encode(payload));
          } catch {
            return;
          }
          cursor += 1;
          continue;
        }
        const run = store.runs.get(runId);
        const doneIndex = events.findIndex((event) => event.type === "run_done");
        if (run && (run.status === "done" || run.status === "failed" || run.status === "partial")) {
          if (doneIndex === -1 || cursor > doneIndex) {
            close();
            return;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 120));
      }
    },
  });
}

export const handlers = [
  http.get(`${base}/ideas`, ({ request }) => {
    const url = new URL(request.url);
    const params = {
      q: url.searchParams.get("q") ?? undefined,
      mode: (url.searchParams.get("mode") as "hybrid" | "keyword" | "semantic" | null) ?? undefined,
      status: url.searchParams.get("status") ?? undefined,
      verdict: url.searchParams.get("verdict") ?? undefined,
      category: url.searchParams.get("category") ?? undefined,
      tag: url.searchParams.get("tag") ?? undefined,
      sort: (url.searchParams.get("sort") as "recent" | "score" | "title" | null) ?? undefined,
      min_score: url.searchParams.has("min_score")
        ? Number(url.searchParams.get("min_score"))
        : undefined,
      max_score: url.searchParams.has("max_score")
        ? Number(url.searchParams.get("max_score"))
        : undefined,
      archived: url.searchParams.get("archived") === "true",
      pinned: url.searchParams.has("pinned")
        ? url.searchParams.get("pinned") === "true"
        : undefined,
      cursor: url.searchParams.get("cursor") ?? undefined,
      limit: url.searchParams.has("limit") ? Number(url.searchParams.get("limit")) : undefined,
    } as Parameters<typeof db.searchIdeas>[0];
    return HttpResponse.json(db.searchIdeas(params));
  }),

  http.post(`${base}/ideas`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const invalid = checkRawInput(body.raw_input);
    if (invalid) return invalid;
    const idea = db.createIdea({
      raw_input: body.raw_input as string,
      title: body.title as string | undefined,
      context: body.context as never,
      tags: body.tags as string[] | undefined,
      analyze: body.analyze as boolean | undefined,
    });
    return HttpResponse.json(idea, { status: 201 });
  }),

  http.get(`${base}/ideas/:id`, ({ params }) => {
    const idea = db.getIdea(String(params.id));
    return idea ? HttpResponse.json(idea) : notFound("Idea not found");
  }),

  http.patch(`${base}/ideas/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const idea = db.updateIdea(String(params.id), {
      title: body.title as string | undefined,
      tags: body.tags as string[] | undefined,
      pinned: body.pinned as boolean | undefined,
      archived: body.archived as boolean | undefined,
    });
    return idea ? HttpResponse.json(idea) : notFound("Idea not found");
  }),

  http.post(`${base}/ideas/:id/versions`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const invalid = checkRawInput(body.raw_input);
    if (invalid) return invalid;
    const idea = db.addVersion(String(params.id), {
      raw_input: body.raw_input as string,
      context: body.context as never,
      analyze: body.analyze as boolean | undefined,
    });
    return idea ? HttpResponse.json(idea, { status: 201 }) : notFound("Idea not found");
  }),

  http.get(`${base}/ideas/:id/similar`, ({ params, request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") ?? 5);
    if (!db.getIdea(String(params.id))) return notFound("Idea not found");
    return HttpResponse.json(db.getSimilar(String(params.id), limit));
  }),

  http.get(`${base}/ideas/:id/report`, ({ params, request }) => {
    const url = new URL(request.url);
    const version = url.searchParams.has("version")
      ? Number(url.searchParams.get("version"))
      : undefined;
    const report = db.getReport(String(params.id), version);
    return report ? HttpResponse.json(report) : notFound("Report not ready");
  }),

  http.get(`${base}/ideas/:id/report.md`, ({ params, request }) => {
    const url = new URL(request.url);
    const version = url.searchParams.has("version")
      ? Number(url.searchParams.get("version"))
      : undefined;
    const idea = db.getIdea(String(params.id));
    const report = db.getReport(String(params.id), version);
    if (!idea || !report) return notFound("Report not ready");
    return new HttpResponse(reportToMarkdown(report, idea.title), {
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
    });
  }),

  http.get(`${base}/ideas/:id/report.pdf`, ({ params, request }) => {
    const url = new URL(request.url);
    const version = url.searchParams.has("version")
      ? Number(url.searchParams.get("version"))
      : undefined;
    const idea = db.getIdea(String(params.id));
    const report = db.getReport(String(params.id), version);
    if (!idea || !report) return notFound("Report not ready");
    return new HttpResponse(minimalPdf(report.header.title || idea.title), {
      headers: { "Content-Type": "application/pdf" },
    });
  }),

  http.get(`${base}/tags`, () => HttpResponse.json({ items: db.listTags() })),

  http.get(`${base}/compare`, ({ request }) => {
    const url = new URL(request.url);
    const ids = (url.searchParams.get("ids") ?? "").split(",").filter(Boolean);
    if (ids.length < 2 || ids.length > 3) {
      return validationError([
        { loc: ["query", "ids"], msg: "Compare needs 2 or 3 idea ids", type: "value_error" },
      ]);
    }
    const items = ids.map((id) => {
      const idea = db.getIdea(id);
      if (!idea)
        return { idea: { id, title: "Unknown idea" }, report: null, error: "Idea not found" };
      const { versions: _v, latest_version: _l, latest_run: _r, ...summary } = idea;
      return { idea: summary, report: db.getReport(id) ?? null, error: null };
    });
    return HttpResponse.json({ items });
  }),

  http.post(`${base}/runs/:id/steps/:step/rerun`, ({ params }) => {
    const run = db.rerunStep(String(params.id), String(params.step));
    return run ? HttpResponse.json(run, { status: 202 }) : notFound("Run not found");
  }),

  http.post(`${base}/runs/:id/respond`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const store = db.getDb();
    const existing = store.runs.get(String(params.id));
    if (!existing) return notFound("Run not found");
    if (existing.status !== "awaiting_input") {
      return HttpResponse.json({ detail: "Run is not awaiting input" }, { status: 409 });
    }
    const run = db.respondToRun(String(params.id), {
      answers: body.answers as never,
      skip: body.skip as boolean | undefined,
    });
    return run ? HttpResponse.json(run, { status: 202 }) : notFound("Run not found");
  }),

  http.get(`${base}/runs/:id/events`, ({ params, request }) => {
    const id = String(params.id);
    const store = db.getDb();
    if (!store.runs.has(id)) return notFound("Run not found");
    const url = new URL(request.url);
    const lastEventId =
      url.searchParams.get("last_event_id") ?? request.headers.get("last-event-id");
    const stream = sseStream(id, lastEventId, request.signal);
    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }),
];

export type MockRunEvent = RunEvent;
