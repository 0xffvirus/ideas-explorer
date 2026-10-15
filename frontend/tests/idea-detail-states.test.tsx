import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { IdeaDetailView } from "@/components/idea-detail-view";
import { API_BASE_URL } from "@/lib/api/client";
import { ideaKeys } from "@/lib/api/keys";
import type { RunRead } from "@/lib/api/types";
import {
  BASE_IDEAS,
  BASE_RUNS,
  CLARIFY_QUESTIONS,
  ideaDetail,
  MOCK_IDEA_IDS,
  MOCK_RUN_IDS,
} from "@/mocks/fixtures";
import { seedRun } from "@/mocks/handlers";
import {
  FakeEventSource,
  installFakeEventSource,
  waitForEventSourceFor,
} from "./fake-event-source";
import { renderWithProviders } from "./render";
import { server } from "./mocks/server";

function ideaFixture(id: string) {
  const idea = BASE_IDEAS.find((item) => item.id === id);
  if (!idea) throw new Error(`Missing idea fixture ${id}`);
  return idea;
}

const api = API_BASE_URL;

function runFixture(overrides: Partial<RunRead> & Pick<RunRead, "id" | "idea_id">): RunRead {
  return {
    version_id: crypto.randomUUID(),
    status: "pending",
    step: "classify",
    cost_usd: 0,
    cost_cap_usd: 0.75,
    error: null,
    questions: null,
    started_at: new Date().toISOString(),
    finished_at: null,
    steps: [],
    ...overrides,
  };
}

let restoreEventSource: () => void;

beforeAll(() => {
  restoreEventSource = installFakeEventSource();
});

afterAll(() => {
  restoreEventSource();
});

beforeEach(() => {
  FakeEventSource.reset();
});

describe("draft ideas", () => {
  it("offers Start analysis and posts a new analyzing version", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.quantumBackup);
    let posted: unknown = null;
    server.use(
      http.post(`${api}/ideas/${idea.id}/versions`, async ({ request }) => {
        posted = await request.json();
        seedRun(runFixture({ id: "draft-run", idea_id: idea.id }));
        return HttpResponse.json(ideaDetail({ ...idea, status: "queued" }), { status: 201 });
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);

    expect(await screen.findByRole("heading", { name: "No analysis yet" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start analysis" }));

    await waitFor(() => {
      expect(posted).toEqual({ raw_input: idea.raw_input, analyze: true });
    });
    expect(await screen.findByRole("heading", { name: "Analysis progress" })).toBeInTheDocument();
  });
});

describe("running ideas", () => {
  it("reduces the SSE event union into the timeline", async () => {
    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.invoiceBot} />);
    expect(await screen.findByRole("heading", { name: "Analysis progress" })).toBeInTheDocument();

    const source = await waitForEventSourceFor(MOCK_RUN_IDS.invoiceBot);
    act(() => {
      source.emit("step_started", { step: "classify" });
      source.emit("cost_update", { cost_usd: 0.01, cap_usd: 0.75, step: "classify" });
      source.emit("step_completed", { step: "classify" });
      source.emit("step_started", { step: "refine" });
    });

    const doneRow = screen.getByText("Classify").closest("li");
    expect(doneRow).toHaveTextContent("Done");
    expect(doneRow).toHaveTextContent("$0.010");

    const refineRow = screen.getByText("Refine").closest("li");
    expect(refineRow).toHaveTextContent("Running");
    expect(await screen.findByText("Live updates")).toBeInTheDocument();
  });

  it("ticks the elapsed timer for a running step", async () => {
    // Deterministic clock: the step started exactly 2s before "now", then the
    // 1s tick moves it to exactly 3s. No wall-clock races.
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-10-14T10:00:02.000Z"));
      const idea = ideaFixture(MOCK_IDEA_IDS.invoiceBot);
      seedRun(
        runFixture({
          id: MOCK_RUN_IDS.invoiceBot,
          idea_id: idea.id,
          status: "running",
          step: "market",
          started_at: "2026-10-14T10:00:00.000Z",
          steps: [
            {
              id: "market-step",
              step: "market",
              status: "running",
              output: null,
              cost_usd: 0,
              model: null,
              attempts: 1,
              error: null,
              started_at: "2026-10-14T10:00:00.000Z",
              finished_at: null,
            },
          ],
        }),
      );

      renderWithProviders(<IdeaDetailView ideaId={idea.id} />);

      // Flush the initial fetch with timers (avoid findBy*, which polls).
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10);
      });
      expect(screen.getByRole("heading", { name: "Analysis progress" })).toBeInTheDocument();
      expect(screen.getByText("2.0s")).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(screen.getByText("3.0s")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("re-arms progress and the SSE stream from the rerun response itself", async () => {
    const user = userEvent.setup();
    const petRun = BASE_RUNS.find((run) => run.id === MOCK_RUN_IDS.petTracker);
    if (!petRun) throw new Error("missing pet run fixture");
    // Make every refetch after the rerun hang: the progress panel can only
    // appear if the mutation's `pending` response was seeded into the caches.
    let rerunStarted = false;
    server.use(
      http.get(`${api}/runs/${MOCK_RUN_IDS.petTracker}`, async () => {
        if (rerunStarted) await delay("infinite");
        return HttpResponse.json(petRun);
      }),
      http.get(`${api}/ideas/${MOCK_IDEA_IDS.petTracker}/runs`, async () => {
        if (rerunStarted) await delay("infinite");
        return HttpResponse.json([petRun]);
      }),
      http.post(`${api}/runs/${MOCK_RUN_IDS.petTracker}/steps/market/rerun`, () => {
        rerunStarted = true;
        return HttpResponse.json(
          { ...petRun, status: "pending", step: "market", finished_at: null },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.petTracker} />);

    await screen.findByRole("tab", { name: "Overview" });
    expect(screen.queryByRole("heading", { name: "Analysis progress" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Market" }));
    const panel = await screen.findByRole("tabpanel");
    await user.click(within(panel).getByRole("button", { name: /Re-run Market/i }));

    // The run flips done -> pending, so the progress panel replaces the report
    // and a fresh stream is opened for the rerun.
    expect(await screen.findByRole("heading", { name: "Analysis progress" })).toBeInTheDocument();
    const source = await waitForEventSourceFor(MOCK_RUN_IDS.petTracker);
    act(() => {
      source.emit("step_started", { step: "market" });
    });

    const marketRow = screen
      .getAllByText("Market")
      .map((element) => element.closest("li"))
      .find((element) => element !== null);
    expect(marketRow).toHaveTextContent("Running");
  });

  it("invalidates idea and run queries on run_done", async () => {
    const { client } = renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.invoiceBot} />);
    await screen.findByRole("heading", { name: "Analysis progress" });
    const source = await waitForEventSourceFor(MOCK_RUN_IDS.invoiceBot);
    const spy = vi.spyOn(client, "invalidateQueries");

    act(() => {
      source.emit("run_done", { status: "done", cost_usd: 0.42, failed_sections: [] });
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ideaKeys.all });
    });
  });
});

describe("clarifier", () => {
  const seedAwaitingRun = () =>
    seedRun(
      runFixture({
        id: MOCK_RUN_IDS.clarifyDemo,
        idea_id: MOCK_IDEA_IDS.clarifyDemo,
        status: "awaiting_input",
        step: "refine",
        cost_usd: 0.02,
        questions: CLARIFY_QUESTIONS,
      }),
    );

  it("submits answers and invalidates the run", async () => {
    const user = userEvent.setup();
    seedAwaitingRun();
    let posted: unknown = null;
    server.use(
      http.post(`${api}/runs/${MOCK_RUN_IDS.clarifyDemo}/clarify`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(
          runFixture({
            id: MOCK_RUN_IDS.clarifyDemo,
            idea_id: MOCK_IDEA_IDS.clarifyDemo,
            status: "running",
          }),
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.clarifyDemo} />);

    expect(
      await screen.findByRole("heading", { name: "Help the analysis continue" }),
    ).toBeInTheDocument();
    const first = screen.getByRole("textbox", { name: CLARIFY_QUESTIONS[0]?.question ?? "" });
    const second = screen.getByRole("textbox", { name: CLARIFY_QUESTIONS[1]?.question ?? "" });
    await user.type(first, "Lisbon, Portugal");
    await user.type(second, "$12 monthly membership");
    await user.click(screen.getByRole("button", { name: "Submit answers" }));

    await waitFor(() => {
      expect(posted).toEqual({
        answers: ["Lisbon, Portugal", "$12 monthly membership"],
        skip: false,
      });
    });
  });

  it("reopens the SSE stream once the answers resume the run", async () => {
    const user = userEvent.setup();
    seedAwaitingRun();
    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.clarifyDemo} />);

    expect(
      await screen.findByRole("heading", { name: "Help the analysis continue" }),
    ).toBeInTheDocument();
    // Paused runs deliberately hold no open stream.
    expect(FakeEventSource.instances).toHaveLength(0);

    await user.type(
      screen.getByRole("textbox", { name: CLARIFY_QUESTIONS[0]?.question ?? "" }),
      "Lisbon, Portugal",
    );
    await user.click(screen.getByRole("button", { name: "Submit answers" }));

    const source = await waitForEventSourceFor(MOCK_RUN_IDS.clarifyDemo);
    expect(source.closed).toBe(false);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("skips the questions", async () => {
    const user = userEvent.setup();
    seedAwaitingRun();
    let posted: unknown = null;
    server.use(
      http.post(`${api}/runs/${MOCK_RUN_IDS.clarifyDemo}/clarify`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(
          runFixture({
            id: MOCK_RUN_IDS.clarifyDemo,
            idea_id: MOCK_IDEA_IDS.clarifyDemo,
            status: "running",
          }),
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={MOCK_IDEA_IDS.clarifyDemo} />);

    await screen.findByRole("heading", { name: "Help the analysis continue" });
    await user.click(screen.getByRole("button", { name: "Skip" }));

    await waitFor(() => {
      expect(posted).toEqual({ skip: true });
    });
  });
});

describe("failed runs", () => {
  it("shows the error and re-runs the failed step", async () => {
    const user = userEvent.setup();
    const idea = ideaFixture(MOCK_IDEA_IDS.mealPlanner);
    seedRun(
      runFixture({
        id: "failed-run",
        idea_id: idea.id,
        status: "failed",
        step: "market",
        cost_usd: 0.03,
        error: "Market search timed out",
      }),
    );
    let rerunCalled = false;
    server.use(
      http.post(`${api}/runs/failed-run/steps/market/rerun`, () => {
        rerunCalled = true;
        return HttpResponse.json(
          runFixture({ id: "failed-run", idea_id: idea.id, status: "running", step: "market" }),
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<IdeaDetailView ideaId={idea.id} />);

    expect(await screen.findByText("Market search timed out")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Re-run Market" }));

    await waitFor(() => expect(rerunCalled).toBe(true));
  });
});
