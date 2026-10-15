"use client";

import { CheckCircle2, Circle, Loader2, MinusCircle, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useRunEvents } from "@/lib/api/sse";
import type { RunRead } from "@/lib/api/types";
import {
  isRunActive,
  isRunStatus,
  mapRunToProgress,
  progressPercent,
  type ProgressState,
  type ProgressStep,
  type RunEvent,
  type StepStageStatus,
} from "@/lib/progress";
import { cn, formatDuration } from "@/lib/utils";

const STEP_STATUS_TEXT: Record<StepStageStatus, string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
  skipped: "Skipped",
};

const STEP_STATUS_CLASS: Record<StepStageStatus, string> = {
  queued: "text-muted-foreground",
  running: "text-foreground",
  done: "text-success",
  failed: "text-destructive",
  skipped: "text-muted-foreground",
};

function StepIcon({ status }: { status: StepStageStatus }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className="size-4 text-success" aria-hidden="true" />;
    case "failed":
      return <XCircle className="size-4 text-destructive" aria-hidden="true" />;
    case "running":
      return (
        <Loader2
          className="size-4 animate-spin text-foreground motion-reduce:animate-none"
          aria-hidden="true"
        />
      );
    case "skipped":
      return <MinusCircle className="size-4 text-muted-foreground" aria-hidden="true" />;
    default:
      return <Circle className="size-4 text-muted-foreground/60" aria-hidden="true" />;
  }
}

function formatUsd(value: number): string {
  return `$${value.toFixed(value > 0 && value < 0.01 ? 3 : 2)}`;
}

export interface RunProgressProps {
  run: RunRead;
  /** Observes every parsed SSE event (e.g. to invalidate queries on `run_done`). */
  onEvent?: (event: RunEvent) => void;
}

/** Elapsed time for a step; running steps tick with a client-side clock. */
function stepElapsedMs(step: ProgressStep, now: number): number {
  if (step.status === "running" && step.startedAt !== null) {
    return Math.max(now - step.startedAt, step.elapsedMs);
  }
  return step.elapsedMs;
}

/**
 * Live pipeline timeline. While the run is active it subscribes to the run's
 * SSE stream; the reducer output supersedes the persisted `RunRead` snapshot.
 * Paused runs (`awaiting_input`) deliberately have no open stream: the run
 * query carries the questions, and answering them makes the run active again,
 * which recreates the subscription.
 */
export function RunProgress({ run, onEvent }: RunProgressProps) {
  const active = isRunStatus(run.status) && isRunActive(run.status);
  const streamRunId = active && run.status !== "awaiting_input" ? run.id : null;
  const { state: streamState, connected } = useRunEvents(streamRunId, { onEvent });

  const progress: ProgressState = useMemo(
    () => streamState ?? mapRunToProgress(run),
    [streamState, run],
  );

  const [now, setNow] = useState(() => Date.now());
  const hasRunningStep = progress.steps.some((step) => step.status === "running");
  useEffect(() => {
    if (!active || !hasRunningStep) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active, hasRunningStep]);

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <CardTitle asChild>
            <h2>Analysis progress</h2>
          </CardTitle>
          <CardDescription aria-live="polite">
            {connected ? "Live updates" : "Progress"}
          </CardDescription>
        </div>
        <div className="text-right text-sm tabular-nums">
          <span>{formatUsd(progress.costUsd)}</span>
          {progress.costCapUsd > 0 ? (
            <span className="text-muted-foreground"> / {formatUsd(progress.costCapUsd)} cap</span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Progress value={progressPercent(progress)} label="Analysis progress" />
        <ol className="flex flex-col gap-1">
          {progress.steps.map((step) => (
            <li
              key={step.step}
              className="flex items-center justify-between gap-3 rounded-md px-1 py-1.5 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <StepIcon status={step.status} />
                <span
                  className={cn(
                    "truncate",
                    step.status === "queued" ? "text-muted-foreground" : "text-foreground",
                  )}
                >
                  {step.label}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-3 text-xs tabular-nums">
                {step.costUsd > 0 ? (
                  <span className="text-muted-foreground">${step.costUsd.toFixed(3)}</span>
                ) : null}
                {stepElapsedMs(step, now) > 0 ? (
                  <span className="text-muted-foreground">
                    {formatDuration(stepElapsedMs(step, now))}
                  </span>
                ) : null}
                <span className={cn("font-medium", STEP_STATUS_CLASS[step.status])}>
                  {STEP_STATUS_TEXT[step.status]}
                </span>
              </span>
            </li>
          ))}
        </ol>
        {progress.questions.length > 0 ? (
          <div className="rounded-lg border border-border bg-muted/40 p-4">
            <p className="text-sm font-medium">The analysis is waiting for your answers</p>
            <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
              {progress.questions.map((question) => (
                <li key={question.question}>
                  {question.question}
                  {question.why ? (
                    <span className="text-muted-foreground/80"> — {question.why}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {progress.failedSections.length > 0 ? (
          <p className="text-sm text-muted-foreground">
            Some sections failed: {progress.failedSections.join(", ")}.
          </p>
        ) : null}
        {progress.error && progress.status === "failed" ? (
          <p className="text-sm text-destructive">{progress.error}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
