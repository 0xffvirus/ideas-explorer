"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, CircleDashed, Loader2, X } from "lucide-react";
import { cn } from "cn";
import type { Run, RunStepName } from "@/lib/api/types";
import type { RunEventsState } from "@/lib/api/use-run-events";
import { PIPELINE_STEPS, STEP_STATUS_LABELS } from "@/lib/pipeline-steps";
import { formatCost, formatSeconds } from "@/lib/format";

function elapsedLabel(
  startedAt: string | null | undefined,
  now: number,
  finishedAt?: string | null,
): string {
  if (!startedAt) return "";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : now;
  return formatSeconds(Math.max(0, end - start));
}

function StepIcon({ status }: { status: keyof typeof STEP_STATUS_LABELS }) {
  if (status === "running") {
    return <Loader2 size={16} className="animate-spin text-ink" aria-hidden="true" />;
  }
  if (status === "done") {
    return <Check size={16} className="text-success" aria-hidden="true" />;
  }
  if (status === "failed") {
    return <X size={16} className="text-error" aria-hidden="true" />;
  }
  return <CircleDashed size={16} className="text-ink-muted" aria-hidden="true" />;
}

export function ProgressTimeline({
  run,
  progress,
  onRetry,
  variant = "card",
}: {
  run: Run | null;
  progress: RunEventsState;
  onRetry?: (step: RunStepName) => void;
  /** "plain" drops the card chrome when nested inside another surface. */
  variant?: "card" | "plain";
}) {
  const [now, setNow] = useState(() => Date.now());
  const hasRunning = useMemo(
    () => Object.values(progress.steps).some((status) => status === "running"),
    [progress.steps],
  );
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!hasRunning) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [hasRunning]);

  if (!run) return null;

  const steps = PIPELINE_STEPS.filter((step) => {
    if (step.id === "clarify") {
      return Boolean(progress.steps.clarify || run.questions?.length);
    }
    return true;
  });

  const cost = progress.costUsd ?? run.cost_usd;
  const cap = progress.costCapUsd ?? run.cost_cap_usd ?? 0.75;
  const pct = Math.min(100, Math.round((cost / Math.max(cap, 0.01)) * 100));

  const status = progress.status ?? run.status;
  const statusLabel =
    status === "partial"
      ? "Stopped at cost cap"
      : status === "awaiting_input"
        ? "Waiting for input"
        : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <section
      aria-label="Analysis progress"
      className={cn(
        "rounded-card border border-line bg-surface p-6",
        variant === "plain" && "rounded-none border-0 bg-transparent p-0",
      )}
      data-testid="progress-timeline"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="t-card">
          {status === "queued" && "Queued"}
          {status === "running" && "Analyzing…"}
          {status === "awaiting_input" && "Waiting for your answers"}
          {status === "done" && "Analysis complete"}
          {status === "failed" && "Analysis failed"}
          {status === "partial" && "Partial analysis (cost cap)"}
        </h2>
        <div className="flex items-center gap-4">
          {progress.connected && status === "running" && (
            <span className="t-meta flex items-center gap-1.5" data-testid="live-indicator">
              <span className="size-2 animate-pulse rounded-full bg-success" aria-hidden="true" />
              live
            </span>
          )}
          <span className="t-meta" data-testid="run-status">
            {statusLabel}
          </span>
        </div>
      </div>

      <ol className="mt-5 grid gap-1" data-testid="step-list">
        {steps.map((step) => {
          const stepStatus = progress.steps[step.id] ?? "pending";
          const runStep = run.steps?.find((s) => s.step === step.id);
          return (
            <li
              key={step.id}
              className="flex items-center gap-3 border-b border-line py-2.5 last:border-b-0"
              data-step={step.id}
              data-status={stepStatus}
            >
              <StepIcon status={stepStatus} />
              <span className={cn("t-body", stepStatus === "pending" && "text-ink-muted")}>
                {step.label}
              </span>
              <span className="t-meta ms-auto">
                {stepStatus === "running" && elapsedLabel(runStep?.started_at, now)}
                {stepStatus === "done" &&
                  runStep?.finished_at &&
                  `took ${elapsedLabel(runStep.started_at, now, runStep.finished_at)}`}
                {stepStatus === "failed" && (
                  <button
                    type="button"
                    className="link cursor-pointer text-error"
                    onClick={() => onRetry?.(step.id)}
                  >
                    Retry
                  </button>
                )}
                {stepStatus === "pending" && "waiting"}
              </span>
            </li>
          );
        })}
      </ol>

      {progress.error && (
        <p className="status status--error mt-4" role="alert">
          {progress.error}
        </p>
      )}

      <div className="mt-5">
        <div className="flex items-center justify-between">
          <span className="t-meta">Cost</span>
          <span className="t-meta tabular-nums" data-testid="cost-label">
            {formatCost(cost)} / {formatCost(cap)}
          </span>
        </div>
        <div
          className="mt-2 h-2 overflow-hidden rounded-pill bg-surface-subtle"
          role="progressbar"
          aria-label="Run cost"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
        >
          <div
            className={cn("h-full rounded-pill transition-all", pct >= 100 ? "bg-error" : "bg-ink")}
            style={{ width: `${pct}%` }}
          />
        </div>
        {status === "partial" && (
          <p className="t-meta mt-2">
            The run stopped before the cap was exceeded; completed sections are kept.
          </p>
        )}
      </div>
    </section>
  );
}
