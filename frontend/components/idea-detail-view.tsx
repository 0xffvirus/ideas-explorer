"use client";

import { ArrowLeft, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ClarifierForm } from "@/components/idea-detail/clarifier-form";
import { IdeaHeader } from "@/components/idea-detail/idea-header";
import { ReportTabs } from "@/components/idea-detail/report-tabs";
import { SimilarIdeas } from "@/components/idea-detail/similar-ideas";
import { RunProgress } from "@/components/run-progress";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { ideaKeys, runKeys } from "@/lib/api/keys";
import { useAddVersion, useIdea, useReport, useRerunStep, useRun, useRuns } from "@/lib/api/queries";
import type { IdeaDetail, RunRead } from "@/lib/api/types";
import {
  isPipelineStep,
  isRunActive,
  isRunStatus,
  PIPELINE_STEP_LABELS,
  type RunEvent,
} from "@/lib/progress";

function StartAnalysisCard({ idea }: { idea: IdeaDetail }) {
  const addVersion = useAddVersion(idea.id);
  return (
    <Card>
      <CardHeader>
        <CardTitle asChild>
          <h2>No analysis yet</h2>
        </CardTitle>
        <CardDescription>
          Start the agents to refine this idea and research it. You can re-run any section later.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3">
        <Button
          onClick={() =>
            addVersion.mutate({ raw_input: idea.latest_version.raw_input, analyze: true })
          }
          disabled={addVersion.isPending}
        >
          <Sparkles aria-hidden="true" />
          {addVersion.isPending ? "Starting…" : "Start analysis"}
        </Button>
        {addVersion.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {addVersion.error instanceof ApiError
              ? addVersion.error.detail
              : "Could not start the analysis. Try again."}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function WaitingForRunCard({ onRefresh }: { onRefresh: () => void }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-6">
        <p className="text-sm text-muted-foreground">
          No run has been recorded for this idea yet.
        </p>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw aria-hidden="true" />
          Refresh
        </Button>
      </CardContent>
    </Card>
  );
}

function FailedRunPanel({ run }: { run: RunRead }) {
  const rerun = useRerunStep(run.id);
  const step = isPipelineStep(run.step) ? run.step : null;

  return (
    <Card className="border-destructive/40">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
        <p className="text-sm text-muted-foreground">
          The run stopped before finishing. Re-run the failed step to pick up from the last good
          result.
        </p>
        {step ? (
          <Button size="sm" onClick={() => rerun.mutate(step)} disabled={rerun.isPending}>
            {rerun.isPending ? "Re-running…" : `Re-run ${PIPELINE_STEP_LABELS[step]}`}
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">This run cannot be resumed automatically.</p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Idea screen: header actions, live run progress (with clarifier and failure
 * recovery), the versioned report tabs, and similar ideas.
 */
export function IdeaDetailView({ ideaId }: { ideaId: string }) {
  const queryClient = useQueryClient();
  const [versionNumber, setVersionNumber] = useState<number | null>(null);

  const { data: idea, isLoading, isError, refetch } = useIdea(ideaId);
  const { data: runs, isLoading: runsLoading } = useRuns(ideaId);
  const latestRun = runs?.[0] ?? null;
  const { data: liveRun } = useRun(latestRun?.id);
  const run: RunRead | null = liveRun ?? latestRun ?? null;

  const report = useReport(ideaId, versionNumber ?? undefined);

  const handleRunEvent = useCallback(
    (event: RunEvent) => {
      if (event.type === "run_done" || event.type === "run_paused") {
        void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
        void queryClient.invalidateQueries({ queryKey: runKeys.all });
      }
    },
    [queryClient],
  );

  if (isLoading) {
    return (
      <div className="space-y-6" aria-hidden="true">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !idea) {
    return (
      <Card>
        <CardContent className="flex flex-col items-start gap-3 p-6">
          <p className="text-sm text-muted-foreground">
            Could not load this idea. It may not exist, or the API is down.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Try again
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ideas">Back to library</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const versions = idea.versions ?? [idea.latest_version];
  const selectedVersion =
    versions.find((version) => version.number === (versionNumber ?? idea.latest_version.number)) ??
    idea.latest_version;
  const active = run !== null && isRunStatus(run.status) && isRunActive(run.status);
  const settled = run !== null && isRunStatus(run.status) && !isRunActive(run.status);
  const showEmptyState = run === null && !runsLoading && idea.status === "draft";
  const waitingForRun = run === null && !runsLoading && idea.status !== "draft";
  const reportReady = report.data !== undefined;

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <Link
          href="/ideas"
          className="inline-flex items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Library
        </Link>
        <IdeaHeader
          idea={idea}
          selectedVersion={selectedVersion}
          onSelectVersion={(number) =>
            setVersionNumber(number === idea.latest_version.number ? null : number)
          }
        />
        <p className="max-w-3xl whitespace-pre-wrap text-muted-foreground">
          {selectedVersion.raw_input}
        </p>
      </div>

      {active && run ? (
        <div className="flex flex-col gap-4">
          <RunProgress run={run} onEvent={handleRunEvent} />
          {run.status === "awaiting_input" && (run.questions?.length ?? 0) > 0 ? (
            <ClarifierForm runId={run.id} questions={run.questions ?? []} />
          ) : null}
        </div>
      ) : null}

      {run && run.status === "failed" ? (
        <div className="flex flex-col gap-4">
          <RunProgress run={run} />
          <FailedRunPanel run={run} />
        </div>
      ) : null}

      {showEmptyState ? <StartAnalysisCard idea={idea} /> : null}
      {waitingForRun ? <WaitingForRunCard onRefresh={() => void refetch()} /> : null}

      {/* While a run is active the progress panel is the source of truth; the
          previous version's report would be stale (e.g. after a re-run). */}
      {!active && reportReady && report.data ? (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <div className="min-w-0">
            <ReportTabs report={report.data} run={run} />
          </div>
          <aside aria-label="Related ideas">
            <SimilarIdeas ideaId={ideaId} />
          </aside>
        </div>
      ) : null}

      {settled && !reportReady && report.isLoading ? (
        <div className="space-y-3" aria-hidden="true">
          <Skeleton className="h-10 w-full max-w-md" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      ) : null}

      {settled && !reportReady && report.isError ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            The report for this version is not ready yet. Try again in a moment.
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
