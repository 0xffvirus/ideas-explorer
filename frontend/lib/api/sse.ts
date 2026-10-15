"use client";

import { useEffect, useRef, useState } from "react";

import { apiUrl } from "./client";
import {
  initialProgressState,
  isRunStatus,
  reduceRunEvents,
  type ProgressState,
  type RunEvent,
} from "@/lib/progress";
import type { components } from "./schema";

/** Delay before manually re-opening a source the browser has given up on. */
export const SSE_RECONNECT_DELAY_MS = 1000;
/** Cap on manual reconnects after `EventSource` reaches the CLOSED state. */
export const SSE_MAX_RECONNECT_ATTEMPTS = 5;

export const RUN_EVENT_NAMES = [
  "step_started",
  "step_completed",
  "step_failed",
  "cost_update",
  "run_paused",
  "run_done",
] as const;

export type RunEventName = (typeof RUN_EVENT_NAMES)[number];

/**
 * Open an `EventSource` for a run's SSE stream. The URL must be absolute and no
 * custom headers can be sent, so nothing is appended here. The browser
 * reconnects with the last received event id automatically.
 */
export function createRunEventSource(runId: string): EventSource {
  if (typeof EventSource === "undefined") {
    throw new Error("EventSource is not available in this environment");
  }
  return new EventSource(apiUrl(`/runs/${runId}/events`));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseQuestions(value: unknown): components["schemas"]["ClarifyingQuestion"][] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.question !== "string") return [];
    return [{ question: item.question, why: typeof item.why === "string" ? item.why : "" }];
  });
}

/**
 * Parse one SSE event (named event + JSON `data:` payload) into a typed
 * `RunEvent`. Unknown or malformed events return `null` so they can be ignored.
 */
export function parseRunEvent(eventName: string, data: string): RunEvent | null {
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(payload)) return null;

  switch (eventName) {
    case "step_started":
      return typeof payload.step === "string" ? { type: "step_started", step: payload.step } : null;
    case "step_completed":
      return typeof payload.step === "string"
        ? {
            type: "step_completed",
            step: payload.step,
            status: typeof payload.status === "string" ? payload.status : undefined,
          }
        : null;
    case "step_failed":
      return typeof payload.step === "string"
        ? {
            type: "step_failed",
            step: payload.step,
            error: typeof payload.error === "string" ? payload.error : "Step failed",
          }
        : null;
    case "cost_update":
      return typeof payload.cost_usd === "number"
        ? {
            type: "cost_update",
            cost_usd: payload.cost_usd,
            cap_usd: typeof payload.cap_usd === "number" ? payload.cap_usd : 0,
            step: typeof payload.step === "string" ? payload.step : undefined,
          }
        : null;
    case "run_paused":
      return {
        type: "run_paused",
        questions: parseQuestions(payload.questions),
        step: typeof payload.step === "string" ? payload.step : undefined,
      };
    case "run_done": {
      if (typeof payload.status !== "string" || !isRunStatus(payload.status)) return null;
      return {
        type: "run_done",
        status: payload.status,
        cost_usd: typeof payload.cost_usd === "number" ? payload.cost_usd : undefined,
        failed_sections: Array.isArray(payload.failed_sections)
          ? payload.failed_sections.filter((item): item is string => typeof item === "string")
          : undefined,
        error: typeof payload.reason === "string" ? payload.reason : undefined,
      };
    }
    default:
      return null;
  }
}

/** Payloads some SSE servers send as unnamed messages with a `type` field. */
function parseDefaultEvent(data: string): RunEvent | null {
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(payload) || typeof payload.type !== "string") return null;
  const { type, ...rest } = payload;
  return parseRunEvent(type, JSON.stringify(rest));
}

function withReceivedAt(event: RunEvent, receivedAt: number): RunEvent {
  return { ...event, receivedAt };
}

export interface UseRunEventsResult {
  /** Reduced progress state, or `null` until the first event arrives. */
  state: ProgressState | null;
  connected: boolean;
}

export interface UseRunEventsOptions {
  /** Observes every parsed event before it is reduced into state. */
  onEvent?: (event: RunEvent) => void;
}

interface ProgressSnapshot {
  runId: string;
  state: ProgressState;
}

/**
 * Subscribe to a run's SSE stream and reduce it into `ProgressState`.
 * Pass `null` to stay disconnected (e.g. while the run awaits input).
 *
 * - `run_done` and `run_paused` close the source deliberately so it is not
 *   left open (or reconnected) forever; the next re-arm happens when the run
 *   query reports the run active again.
 * - A transient error leaves reconnecting to the browser (`CONNECTING`); the
 *   browser preserves and resends the last event id. If the source reaches
 *   `CLOSED`, the hook retries manually a bounded number of times.
 * - Reduced state is kept per run id, so a pause/resume cycle neither loses
 *   settled rows nor leaks progress between different runs.
 */
export function useRunEvents(
  runId: string | null | undefined,
  options: UseRunEventsOptions = {},
): UseRunEventsResult {
  const [snapshot, setSnapshot] = useState<ProgressSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(options.onEvent);

  useEffect(() => {
    onEventRef.current = options.onEvent;
  });

  useEffect(() => {
    if (!runId || typeof EventSource === "undefined") return;

    let disposed = false;
    let stopped = false;
    let attempts = 0;
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const scheduleReconnect = () => {
      if (disposed || stopped || reconnectTimer !== null) return;
      if (attempts >= SSE_MAX_RECONNECT_ATTEMPTS) return;
      attempts += 1;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, SSE_RECONNECT_DELAY_MS);
    };

    const dispatch = (event: RunEvent) => {
      onEventRef.current?.(event);
      setSnapshot((previous) => {
        const base = previous && previous.runId === runId ? previous.state : initialProgressState;
        return { runId, state: reduceRunEvents(base, withReceivedAt(event, Date.now())) };
      });
      if (event.type === "run_done" || event.type === "run_paused") {
        stopped = true;
        source?.close();
        setConnected(false);
      }
    };

    const connect = () => {
      if (disposed || stopped) return;
      const next = createRunEventSource(runId);
      source = next;
      next.onopen = () => {
        attempts = 0;
        setConnected(true);
      };
      next.onerror = () => {
        setConnected(false);
        if (next.readyState === EventSource.CLOSED) scheduleReconnect();
      };

      for (const name of RUN_EVENT_NAMES) {
        next.addEventListener(name, ((event: Event) => {
          if (!(event instanceof MessageEvent) || typeof event.data !== "string") return;
          const parsed = parseRunEvent(name, event.data);
          if (parsed) dispatch(parsed);
        }) as EventListener);
      }

      next.onmessage = (event: MessageEvent<string>) => {
        if (typeof event.data !== "string") return;
        const parsed = parseDefaultEvent(event.data);
        if (parsed) dispatch(parsed);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      source?.close();
      setConnected(false);
    };
  }, [runId]);

  const state = snapshot && snapshot.runId === runId ? snapshot.state : null;

  return { state, connected };
}
