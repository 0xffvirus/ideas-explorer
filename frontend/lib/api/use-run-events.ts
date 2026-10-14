"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { API_URL } from "./client";
import { initialProgress, parseRunEvent, progressReducer, type RunProgress } from "./run-events";
import type { Run, RunStatus } from "./types";

const TERMINAL_STATUSES: RunStatus[] = ["done", "failed", "partial"];

const MAX_RECONNECTS = 5;
const BASE_BACKOFF_MS = 800;

export type RunEventsState = RunProgress & { connected: boolean };

type Options = {
  enabled?: boolean;
  /** Run snapshot from the API; seeds the timeline so a reload shows the right state. */
  initialRun?: Run | null;
};

function frameBoundary(buffer: string): { start: number; end: number } | null {
  const lf = buffer.indexOf("\n\n");
  const crlf = buffer.indexOf("\r\n\r\n");
  if (lf === -1 && crlf === -1) return null;
  if (lf === -1) return { start: crlf, end: crlf + 4 };
  if (crlf === -1) return { start: lf, end: lf + 2 };
  return lf < crlf ? { start: lf, end: lf + 2 } : { start: crlf, end: crlf + 4 };
}

/**
 * Live-subscribes to a run's SSE stream. Reconnects with the last event id so
 * reopening the app resumes without losing steps.
 */
export function useRunEvents(runId: string | null, options: Options = {}): RunEventsState {
  const { enabled = true, initialRun = null } = options;
  const initialRunStatus = initialRun?.status ?? null;
  const [progress, dispatch] = useReducer(progressReducer, initialProgress);
  const [connected, setConnected] = useState(false);
  const lastEventIdRef = useRef<string | null>(null);
  const doneRef = useRef(false);
  const prevRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    const runChanged = prevRunIdRef.current !== runId;
    prevRunIdRef.current = runId;
    if (runChanged) {
      // Fresh run: replay from the beginning. Re-seeds of the same run (section
      // re-runs) keep the cursor so old events are not replayed.
      lastEventIdRef.current = null;
    }
    // Seed the "done" flag from the authoritative run status so a finished run
    // does not open (and endlessly reopen) a terminal stream.
    if (runId && initialRun?.id === runId) {
      doneRef.current = TERMINAL_STATUSES.includes(initialRun.status);
      dispatch({ kind: "seed", run: initialRun });
    } else {
      doneRef.current = false;
      dispatch({ kind: "reset" });
    }
    // Only reset when the run identity or its coarse state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, initialRun?.id, initialRun?.status, initialRun?.step, initialRun?.cost_usd]);

  useEffect(() => {
    lastEventIdRef.current = progress.lastEventId;
    doneRef.current = progress.done;
  }, [progress.lastEventId, progress.done]);

  useEffect(() => {
    if (!runId || !enabled) return;
    if (progress.runId !== runId) return;
    // Only skip when the run is known terminal. A re-run keeps the same run id,
    // so the stream must be able to resume even after a done state.
    const runIsActive = initialRunStatus != null && !TERMINAL_STATUSES.includes(initialRunStatus);
    if (doneRef.current && !runIsActive) return;

    const currentRunId = runId;
    const controller = new AbortController();
    let cancelled = false;
    let attempt = 0;

    function streamUrl(): string {
      const suffix = lastEventIdRef.current
        ? `?last_event_id=${encodeURIComponent(lastEventIdRef.current)}`
        : "";
      return `${API_URL}/runs/${encodeURIComponent(currentRunId)}/events${suffix}`;
    }

    function handleFrame(frame: string) {
      let id: string | undefined;
      let type: string | undefined;
      const dataLines: string[] = [];
      for (const rawLine of frame.split(/\r?\n/)) {
        const line = rawLine;
        if (line.startsWith(":")) continue;
        if (line.startsWith("id:")) id = line.slice(3).trim();
        else if (line.startsWith("event:")) type = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length === 0) return;
      const event = parseRunEvent(dataLines.join("\n"), id, type);
      if (!event) return;
      dispatch({ kind: "event", event });
      if (event.type === "run_done") doneRef.current = true;
    }

    async function readStream(body: ReadableStream<Uint8Array>): Promise<number> {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let received = 0;
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let boundary = frameBoundary(buffer);
          while (boundary) {
            const frame = buffer.slice(0, boundary.start);
            buffer = buffer.slice(boundary.end);
            const before = received;
            handleFrame(frame);
            received = before + (frame.trim() ? 1 : 0);
            boundary = frameBoundary(buffer);
          }
        }
      } finally {
        reader.releaseLock();
      }
      return received;
    }

    async function connect() {
      while (!cancelled && !doneRef.current) {
        let received = 0;
        try {
          const response = await fetch(streamUrl(), {
            headers: { Accept: "text/event-stream" },
            signal: controller.signal,
            cache: "no-store",
          });
          if (!response.ok || !response.body) {
            throw new Error(`Event stream failed (${response.status})`);
          }
          setConnected(true);
          received = await readStream(response.body);
          setConnected(false);
          if (cancelled || doneRef.current) return;
          // A clean close with no frames (proxy idle timeout, terminal run)
          // must still count against the retry budget — only real progress
          // resets it, otherwise the loop reconnects forever.
          attempt = received > 0 ? 0 : attempt + 1;
          if (attempt > MAX_RECONNECTS) {
            dispatch({ kind: "stream_error", message: "The run stream stopped sending events." });
            return;
          }
        } catch (cause) {
          if (cancelled) return;
          setConnected(false);
          attempt += 1;
          if (attempt > MAX_RECONNECTS) {
            dispatch({
              kind: "stream_error",
              message: cause instanceof Error ? cause.message : "Lost connection to the run",
            });
            return;
          }
        }
        const delay = Math.min(BASE_BACKOFF_MS * 2 ** Math.max(attempt - 1, 0), 8000);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
    void connect();
    return () => {
      cancelled = true;
      controller.abort();
      setConnected(false);
    };
    // Re-runs reuse the same run id: the run's own status is part of the key so
    // that a finished run becoming active again (or a fresh status) reconnects.
  }, [runId, enabled, progress.runId, progress.done, initialRunStatus]);

  return { ...progress, connected };
}
