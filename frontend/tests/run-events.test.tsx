import { act, render, screen } from "@testing-library/react";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import {
  SSE_MAX_RECONNECT_ATTEMPTS,
  SSE_RECONNECT_DELAY_MS,
  useRunEvents,
} from "@/lib/api/sse";
import { FakeEventSource, installFakeEventSource, waitForEventSource } from "./fake-event-source";

function Harness({ runId }: { runId: string | null }) {
  const { state, connected } = useRunEvents(runId);
  const done = (state?.steps ?? [])
    .filter((step) => step.status === "done")
    .map((step) => step.step)
    .join(",");
  return (
    <div>
      <span data-testid="connected">{connected ? "yes" : "no"}</span>
      <span data-testid="status">{state?.status ?? "none"}</span>
      <span data-testid="current">{state?.currentStep ?? "none"}</span>
      <span data-testid="done">{done === "" ? "none" : done}</span>
    </div>
  );
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

describe("useRunEvents", () => {
  it("closes the source when run_paused arrives", async () => {
    render(<Harness runId="run-1" />);
    const source = await waitForEventSource();

    act(() => {
      source.emit("run_paused", {
        step: "clarify",
        questions: [{ question: "Which city?", why: "rules differ" }],
      });
    });

    expect(source.closed).toBe(true);
    expect(screen.getByTestId("connected")).toHaveTextContent("no");
    expect(screen.getByTestId("status")).toHaveTextContent("awaiting_input");
    expect(screen.getByTestId("current")).toHaveTextContent("clarify");
  });

  it("lets the browser retry a transient error and keeps the last event id", async () => {
    render(<Harness runId="run-1" />);
    const source = await waitForEventSource();

    act(() => {
      source.emit("step_started", { step: "market" }, 7);
    });
    expect(source.lastEventId).toBe("7");
    expect(screen.getByTestId("status")).toHaveTextContent("running");

    act(() => {
      source.simulateError(FakeEventSource.CONNECTING);
    });
    // A live stream in CONNECTING is retried by the browser: no new instance.
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(screen.getByTestId("connected")).toHaveTextContent("no");

    act(() => {
      source.simulateOpen();
    });
    expect(screen.getByTestId("connected")).toHaveTextContent("yes");
    expect(source.lastEventId).toBe("7");
  });

  it("reconnects a CLOSED source a bounded number of times", async () => {
    vi.useFakeTimers();
    try {
      FakeEventSource.autoOpen = false;
      render(<Harness runId="run-1" />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(FakeEventSource.instances).toHaveLength(1);

      for (let attempt = 0; attempt < SSE_MAX_RECONNECT_ATTEMPTS + 2; attempt += 1) {
        const source = FakeEventSource.latest();
        act(() => {
          source?.simulateError(FakeEventSource.CLOSED);
        });
        await act(async () => {
          await vi.advanceTimersByTimeAsync(SSE_RECONNECT_DELAY_MS + 10);
        });
      }

      expect(FakeEventSource.instances).toHaveLength(1 + SSE_MAX_RECONNECT_ATTEMPTS);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps state for the same run across a disconnect and preserves settled rows", async () => {
    const { rerender } = render(<Harness runId="run-1" />);
    const first = await waitForEventSource();

    act(() => {
      first.emit("step_started", { step: "refine" }, 1);
      first.emit("step_completed", { step: "refine" }, 2);
    });
    expect(screen.getByTestId("done")).toHaveTextContent("refine");

    rerender(<Harness runId={null} />);
    expect(first.closed).toBe(true);
    expect(screen.getByTestId("status")).toHaveTextContent("none");

    rerender(<Harness runId="run-1" />);
    expect(screen.getByTestId("status")).toHaveTextContent("running");
    expect(screen.getByTestId("done")).toHaveTextContent("refine");

    const second = FakeEventSource.instances.at(-1);
    expect(second).not.toBe(first);
    act(() => {
      second?.emit("step_started", { step: "market" }, 3);
    });
    expect(screen.getByTestId("current")).toHaveTextContent("market");
    expect(screen.getByTestId("done")).toHaveTextContent("refine");
  });

  it("drops state from a different run", async () => {
    const { rerender } = render(<Harness runId="run-1" />);
    const first = await waitForEventSource();
    act(() => {
      first.emit("step_started", { step: "refine" }, 1);
      first.emit("step_completed", { step: "refine" }, 2);
    });

    rerender(<Harness runId="run-2" />);
    expect(screen.getByTestId("status")).toHaveTextContent("none");
    expect(screen.getByTestId("done")).toHaveTextContent("none");

    const second = FakeEventSource.instances.at(-1);
    expect(second?.url).toContain("/runs/run-2/");
    act(() => {
      second?.emit("step_started", { step: "market" }, 1);
    });
    expect(screen.getByTestId("done")).toHaveTextContent("none");
    expect(screen.getByTestId("current")).toHaveTextContent("market");
  });
});
