import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { IdeaDetailView } from "@/components/idea-detail-view";
import { API_BASE_URL } from "@/lib/api/client";
import { runKeys } from "@/lib/api/keys";
import type { IdeaDetail, IdeaVersionRead } from "@/lib/api/types";
import {
  BASE_IDEAS,
  BASE_RUNS,
  ideaDetail,
  MOCK_IDEA_IDS,
  MOCK_RUN_IDS,
  reportFor,
} from "@/mocks/fixtures";
import { seedIdea } from "@/mocks/handlers";
import { renderWithProviders } from "./render";
import { server } from "./mocks/server";

const api = API_BASE_URL;

function ideaFixture(id: string) {
  const idea = BASE_IDEAS.find((item) => item.id === id);
  if (!idea) throw new Error(`Missing idea fixture ${id}`);
  return idea;
}

describe("report rendering", () => {
  it("renders every report tab from the typed report", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.petTracker} />);

    expect(await screen.findByRole("tab", { name: "Overview" })).toBeInTheDocument();

    // Overview: verdict, scorecard, brief, next steps, claims.
    expect(screen.getByRole("heading", { name: "Scorecard" })).toBeInTheDocument();
    // Overall score (header + overview) is on the 0-100 scale; dimension
    // badges stay on the 1-5 scale.
    expect(screen.getAllByText("76.4/100").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("76.4/5")).not.toBeInTheDocument();
    expect(screen.getByText("Problem severity")).toBeInTheDocument();
    expect(screen.getAllByText("Pursue").length).toBeGreaterThan(0);
    expect(screen.getByText("Catch illness weeks earlier without daily checking.")).toBeInTheDocument();
    expect(screen.getByText("Pre-sell to 20 owners from a landing page")).toBeInTheDocument();
    expect(screen.getByText("Cat ownership is growing in urban households.")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Needs review").length).toBeGreaterThan(0);

    // Market: structured payload, citations, unverified pill.
    await user.click(screen.getByRole("tab", { name: "Market" }));
    expect(await screen.findByRole("heading", { name: "Market Size" })).toBeInTheDocument();
    expect(screen.getByText("Pet tech spend reached $8.2B in 2025.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Source 1/ })).toHaveAttribute(
      "href",
      "https://example.com/pet-tech-market",
    );
    expect(screen.getByText("Urban cat ownership is growing by double digits every year.")).toBeInTheDocument();
    expect(screen.getAllByText("unverified").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("tab", { name: "Competitors" }));
    expect(await screen.findByText("Whisker")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Customers" }));
    expect(await screen.findByText("Cat owners aged 28-45 in cities")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Feasibility" }));
    expect(
      await screen.findByText("$18k including hardware prototypes and a vet advisor."),
    ).toBeInTheDocument();

    // Not-completed section placeholder.
    await user.click(screen.getByRole("tab", { name: "Business model" }));
    expect(await screen.findByText("Not completed")).toBeInTheDocument();

    // Sources list.
    await user.click(screen.getByRole("tab", { name: "Sources" }));
    expect(await screen.findByRole("link", { name: /Pet tech market report 2025/ })).toHaveAttribute(
      "href",
      "https://example.com/pet-tech-market",
    );
  });

  it("flags a partial score basis in the overview", async () => {
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    server.use(
      http.get(`${api}/ideas/${idea.id}/report`, () => {
        const report = reportFor(idea);
        return HttpResponse.json({
          ...report,
          header: { ...report.header, score_basis: "partial" },
        });
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    expect(await screen.findByText("Partial evidence")).toBeInTheDocument();
  });

  it("falls back to the section markdown when there is no structured payload", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    server.use(
      http.get(`${api}/ideas/${idea.id}/report`, () => {
        const report = reportFor(idea);
        const sections = (report.sections ?? []).map((section) =>
          section.name === "market"
            ? {
                ...section,
                json_payload: {},
                markdown: "### Fallback heading\n\nFallback **body** text.",
              }
            : section,
        );
        return HttpResponse.json({ ...report, sections });
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Market" }));

    expect(await screen.findByRole("heading", { name: "Fallback heading" })).toBeInTheDocument();
    expect(screen.getByText("body").tagName).toBe("STRONG");
  });

  it("re-runs a section through the run step endpoint", async () => {
    const user = userEvent.setup();
    const petRun = BASE_RUNS.find((run) => run.id === MOCK_RUN_IDS.petTracker);
    if (!petRun) throw new Error("missing pet run fixture");
    let rerunCalled = false;
    server.use(
      http.post(`${api}/runs/${MOCK_RUN_IDS.petTracker}/steps/business_model/rerun`, () => {
        rerunCalled = true;
        // The real API returns the reset run (pending on the target step).
        return HttpResponse.json(
          { ...petRun, status: "pending", step: "business_model", finished_at: null },
          { status: 202 },
        );
      }),
    );

    const { client } = renderWithProviders(
      <IdeaDetailView ideaId={MOCK_IDEA_IDS.petTracker} />,
    );
    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Business model" }));
    const panel = await screen.findByRole("tabpanel");
    const spy = vi.spyOn(client, "invalidateQueries");
    await user.click(within(panel).getByRole("button", { name: /Re-run Business model/i }));

    await waitFor(() => expect(rerunCalled).toBe(true));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ queryKey: runKeys.detail(MOCK_RUN_IDS.petTracker) }),
    );
  });
});

describe("header actions", () => {
  it("saves an inline title edit on Enter via PATCH", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    let patched: unknown = null;
    server.use(
      http.patch(`${api}/ideas/${idea.id}`, async ({ request }) => {
        patched = await request.json();
        const next = { ...idea, title: "Cats, but proactive" };
        seedIdea(next);
        return HttpResponse.json(ideaDetail(next));
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("heading", { name: idea.title });

    await user.click(screen.getByRole("button", { name: "Edit title" }));
    const input = screen.getByRole("textbox", { name: "Idea title" });
    await user.clear(input);
    await user.type(input, "Cats, but proactive{Enter}");

    await waitFor(() => expect(patched).toEqual({ title: "Cats, but proactive" }));
    expect(
      await screen.findByRole("heading", { name: "Cats, but proactive" }),
    ).toBeInTheDocument();
  });

  it("cancels an inline title edit on Escape without a request", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    let patchCalls = 0;
    server.use(
      http.patch(`${api}/ideas/${idea.id}`, () => {
        patchCalls += 1;
        return HttpResponse.json(ideaDetail(idea));
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("heading", { name: idea.title });

    await user.click(screen.getByRole("button", { name: "Edit title" }));
    const input = screen.getByRole("textbox", { name: "Idea title" });
    await user.clear(input);
    await user.type(input, "Discarded{Escape}");

    expect(screen.queryByRole("textbox", { name: "Idea title" })).not.toBeInTheDocument();
    expect(patchCalls).toBe(0);
  });

  it("adds and removes tags via PATCH", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    const patched: unknown[] = [];
    server.use(
      http.patch(`${api}/ideas/${idea.id}`, async ({ request }) => {
        const body = await request.json();
        patched.push(body);
        const tags = (body as { tags?: string[] }).tags ?? idea.tags ?? [];
        const next = { ...idea, tags };
        seedIdea(next);
        return HttpResponse.json(ideaDetail(next));
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("button", { name: "Add tag" });

    await user.click(screen.getByRole("button", { name: "Add tag" }));
    await user.type(screen.getByRole("textbox", { name: "New tag" }), "sensors{Enter}");
    await waitFor(() => expect(patched).toContainEqual({ tags: ["pets", "health", "sensors"] }));

    await user.click(await screen.findByRole("button", { name: "Remove tag pets" }));
    await waitFor(() =>
      expect(patched).toContainEqual({ tags: ["health", "sensors"] }),
    );
  });

  it("refetches the report when the version changes", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    const base: IdeaDetail = ideaDetail(idea);
    const v1: IdeaVersionRead = {
      ...base.latest_version,
      id: "1b000000-0000-4000-8000-000000000011",
      number: 1,
      raw_input: "Original pet idea",
      created_at: "2026-10-08T09:00:00.000Z",
    };
    const v2: IdeaVersionRead = {
      ...base.latest_version,
      number: 2,
      created_at: "2026-10-11T09:00:00.000Z",
    };
    const detail: IdeaDetail = { ...base, latest_version: v2, versions: [v1, v2] };

    const reportRequests: string[] = [];
    server.use(
      http.get(`${api}/ideas/${idea.id}`, () => HttpResponse.json(detail)),
      http.get(`${api}/ideas/${idea.id}/report`, ({ request }) => {
        reportRequests.push(request.url);
        const version = new URL(request.url).searchParams.get("version");
        const report = reportFor(idea);
        if (version) {
          report.header = {
            ...report.header,
            one_liner: `${report.header.one_liner} · version ${version}`,
          };
        }
        return HttpResponse.json(report);
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("tab", { name: "Overview" });
    expect(screen.queryByText(/· version/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Switch version" }));
    await user.click(await screen.findByRole("menuitem", { name: /v1 ·/ }));

    await waitFor(() =>
      expect(reportRequests.some((url) => url.includes("version=1"))).toBe(true),
    );
    expect(await screen.findByText(/· version 1/)).toBeInTheDocument();
  });

  it("archives the idea via PATCH", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.petTracker);
    let archived: boolean | undefined;
    server.use(
      http.patch(`${api}/ideas/${idea.id}`, async ({ request }) => {
        const body = (await request.json()) as { archived?: boolean };
        archived = body.archived;
        const next = {
          ...idea,
          archived_at: body.archived ? new Date().toISOString() : null,
        };
        seedIdea(next);
        return HttpResponse.json(ideaDetail(next));
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);
    await screen.findByRole("button", { name: "Archive idea" });
    await user.click(screen.getByRole("button", { name: "Archive idea" }));

    await waitFor(() => expect(archived).toBe(true));
    expect(await screen.findByText("Archived")).toBeInTheDocument();
  });

  it("links the export menu to the markdown and PDF report URLs", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.petTracker} />);
    await screen.findByRole("button", { name: "Export report" });

    await user.click(screen.getByRole("button", { name: "Export report" }));

    expect(await screen.findByRole("menuitem", { name: "Download Markdown" })).toHaveAttribute(
      "href",
      `${API_BASE_URL}/ideas/${MOCK_IDEA_IDS.petTracker}/report.md`,
    );
    expect(screen.getByRole("menuitem", { name: "Download PDF" })).toHaveAttribute(
      "href",
      `${API_BASE_URL}/ideas/${MOCK_IDEA_IDS.petTracker}/report.pdf`,
    );
  });
});
