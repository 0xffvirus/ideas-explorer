import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRunEvents } from "./use-run-events";
import type { Run, RunStatus } from "./types";

function baseRun(status: RunStatus): Run {
  return {
    id: "run-1",
    idea_id: "idea-1",
    idea_version_id: "version-1",
    status,
    step: status === "running" ? "market" : null,
    cost_usd: 0.1,
    cost_cap_usd: 0.75,
    error: null,
    steps: [],
    questions: [],
    created_at: "2026-10-01T09:00:00.000Z",
    started_at: null,
    finished_at: null,
  } as Run;
}

function sseStream(frames: string[], close = true): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      if (close) controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function frame(id: string, type: string, data: Record<string, unknown>): string {
  return `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify({ id, type, run_id: "run-1", at: "2026-10-01T09:00:00.000Z", ...data })}\n\n`;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useRunEvents", () => {
  it("does not open a stream for an already-finished run", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRunEvents("run-1", { initialRun: baseRun("done") }));
    await waitFor(() => expect(result.current.done).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the cursor across a same-run re-seed and resumes from it", async () => {
    const calls: string[] = [];
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      calls.push(String(url));
      if (calls.length === 1) {
        return sseStream([
          frame("1", "step_started", { step: "market" }),
          frame("2", "step_completed", { step: "market", cost_usd: 0.2 }),
          frame("3", "run_done", { status: "done", cost_usd: 0.2 }),
        ]);
      }
      return sseStream([], false);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result, rerender } = renderHook(
      ({ status }: { status: RunStatus }) => useRunEvents("run-1", { initialRun: baseRun(status) }),
      { initialProps: { status: "running" as RunStatus } },
    );

    await waitFor(() => expect(result.current.done).toBe(true));
    expect(result.current.lastEventId).toBe("3");

    // Completion refetch reports the run as done — no stream should open.
    rerender({ status: "done" });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // A section re-run reports the run as active again under the same id.
    rerender({ status: "running" });
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    expect(calls[1]).toContain("last_event_id=3");
    expect(calls[1]).not.toMatch(/last_event_id=1($|&)/);
  });

  it("bounds clean-close reconnects instead of looping forever", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(async () => sseStream([]));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRunEvents("run-1", { initialRun: baseRun("running") }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    // MAX_RECONNECTS is 5: the budget is respected and a stream error surfaces.
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(7);
    expect(result.current.error).toBeTruthy();
    vi.useRealTimers();
  });
});
