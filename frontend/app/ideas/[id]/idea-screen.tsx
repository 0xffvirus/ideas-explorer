"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArchiveRestore,
  ChevronDown,
  Download,
  FileText,
  Loader2,
  MoreHorizontal,
  Pin,
  PinOff,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { IdeaCard } from "@/components/ideas/idea-card";
import { IdeaPageSkeleton } from "@/components/ideas/idea-page-skeleton";
import { ClarifyForm } from "@/components/ideas/clarify-form";
import { ProgressTimeline } from "@/components/ideas/progress-timeline";
import { REPORT_TABS, ReportView, type ReportTab } from "@/components/ideas/report-view";
import { TitleEditor } from "@/components/ideas/title-editor";
import { VersionSwitcher } from "@/components/ideas/version-switcher";
import { OverallScore, StatusBadge, VerdictBadge } from "@/components/ideas/badges";
import {
  useAddVersion,
  useIdea,
  useReport,
  useRerunStep,
  useRespondToRun,
  useSimilarIdeas,
  useUpdateIdea,
} from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";
import { useRunEvents } from "@/lib/api/use-run-events";
import type { RunStepName } from "@/lib/api/types";
import { downloadReport } from "@/lib/download";
import { relativeTime } from "@/lib/format";
import { CATEGORY_LABELS } from "@/lib/labels";

function tabFromParam(value: string | null): ReportTab {
  return REPORT_TABS.some((tab) => tab.id === value) ? (value as ReportTab) : "overview";
}

function versionFromParam(value: string | null): number | undefined {
  return value && /^\d+$/.test(value) && Number(value) >= 1 ? Number(value) : undefined;
}

export function IdeaScreen({ ideaId }: { ideaId: string }) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const queryClient = useQueryClient();

  // View-only params (tab, version) are local state mirrored into the URL with
  // the native History API, so switching a tab never triggers an RSC round trip.
  const [activeTab, setActiveTab] = useState<ReportTab>(() =>
    tabFromParam(searchParams.get("tab")),
  );
  const [activeVersion, setActiveVersion] = useState<number | undefined>(() =>
    versionFromParam(searchParams.get("version")),
  );
  // Adjust state during render when searchParams change externally
  // (back/forward, deep links) — the documented alternative to an effect.
  const [viewParams, setViewParams] = useState(searchParams);
  if (viewParams !== searchParams) {
    setViewParams(searchParams);
    setActiveTab(tabFromParam(searchParams.get("tab")));
    setActiveVersion(versionFromParam(searchParams.get("version")));
  }

  const writeViewParams = useCallback(
    (tab: ReportTab, version: number | undefined) => {
      const params = new URLSearchParams(window.location.search);
      if (tab === "overview") params.delete("tab");
      else params.set("tab", tab);
      if (version == null) params.delete("version");
      else params.set("version", String(version));
      const query = params.toString();
      window.history.replaceState(null, "", query ? `${pathname}?${query}` : pathname);
    },
    [pathname],
  );

  const selectTab = useCallback(
    (tab: ReportTab) => {
      setActiveTab(tab);
      writeViewParams(tab, activeVersion);
    },
    [activeVersion, writeViewParams],
  );

  const selectVersion = useCallback(
    (version: number | undefined) => {
      setActiveVersion(version);
      writeViewParams(activeTab, version);
    },
    [activeTab, writeViewParams],
  );

  const ideaQuery = useIdea(ideaId);
  const idea = ideaQuery.data;
  const run = idea?.latest_run ?? null;
  const progress = useRunEvents(run?.id ?? null, { initialRun: run });

  const reportEnabled = Boolean(idea && (idea.status === "done" || progress.done));
  const reportQuery = useReport(ideaId, activeVersion, { enabled: reportEnabled });
  const similarQuery = useSimilarIdeas(ideaId);
  const report = reportQuery.data;

  const updateIdea = useUpdateIdea(ideaId);
  const rerunStep = useRerunStep();
  const respondToRun = useRespondToRun();
  const addVersion = useAddVersion(ideaId);

  const [newVersionOpen, setNewVersionOpen] = useState(false);
  const [newVersionInput, setNewVersionInput] = useState("");
  const [exportState, setExportState] = useState<"idle" | "md" | "pdf">("idle");
  const [exportError, setExportError] = useState<string | null>(null);

  const previousStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!progress.status) return;
    const previous = previousStatus.current;
    previousStatus.current = progress.status;
    // Ignore the initial seed (a page for an already-finished run needs no refetch).
    if (previous !== null && progress.status === "done" && previous !== "done") {
      void queryClient.invalidateQueries({ queryKey: ["ideas", "detail", ideaId] });
      void queryClient.invalidateQueries({ queryKey: ["ideas", "report", ideaId] });
      // Mark the list and similar sections stale without refetching while hidden.
      void queryClient.invalidateQueries({ queryKey: ["ideas", "list"], refetchType: "none" });
      void queryClient.invalidateQueries({
        queryKey: ["ideas", "similar", ideaId],
        refetchType: "none",
      });
    }
  }, [progress.status, queryClient, ideaId]);

  const handleRerun = (step: RunStepName) => {
    if (!run) return;
    rerunStep.mutate({ runId: run.id, step });
  };

  const rerunningStep = rerunStep.isPending ? (rerunStep.variables?.step as RunStepName) : null;
  const questions = progress.questions.length > 0 ? progress.questions : (run?.questions ?? []);
  const awaitingInput =
    progress.status === "awaiting_input" || (!progress.status && run?.status === "awaiting_input");

  const similar = useMemo(() => (similarQuery.data?.items ?? []).slice(0, 3), [similarQuery.data]);

  async function handleExport(format: "md" | "pdf") {
    if (!idea) return;
    setExportError(null);
    setExportState(format);
    try {
      await downloadReport(idea.id, idea.title, format, activeVersion);
    } catch (error) {
      setExportError(
        isApiError(error) && error.status === 404
          ? "No report is available yet for this version."
          : "Export failed. Try again.",
      );
    } finally {
      setExportState("idle");
    }
  }

  if (ideaQuery.isError) {
    const notFound = isApiError(ideaQuery.error) && ideaQuery.error.status === 404;
    return (
      <div className="container--reading container pt-[calc(var(--header-offset)+var(--space-8))] pb-24">
        <h1 className="t-section">{notFound ? "Idea not found" : "Could not load this idea"}</h1>
        <p className="t-body mt-3">
          {notFound
            ? "It may have been deleted, or this link is wrong."
            : "The API did not answer. Check the connection and try again."}
        </p>
        <div className="mt-6 flex gap-3">
          <Button asChild className="rounded-pill font-bold">
            <Link href="/ideas">Back to library</Link>
          </Button>
          {!notFound && (
            <Button
              variant="outline"
              className="rounded-pill font-bold"
              onClick={() => void ideaQuery.refetch()}
            >
              Retry
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (ideaQuery.isPending || !idea) {
    return <IdeaPageSkeleton />;
  }

  const showReport = report != null && (idea.status === "done" || progress.done);
  const missingSections = (
    ["market", "competitors", "customers", "business_model"] as const
  ).filter((key) => report?.sections_status?.[key] === "not_completed");

  return (
    <div className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="t-meta">
          <Link href="/ideas" className="link">
            Library
          </Link>{" "}
          / {idea.category ? (CATEGORY_LABELS[idea.category] ?? idea.category) : "idea"}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <VersionSwitcher
            versions={idea.versions}
            activeNumber={activeVersion}
            onChange={selectVersion}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="rounded-pill font-bold">
                <MoreHorizontal size={16} aria-hidden="true" /> Actions
                <ChevronDown size={14} aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-52">
              <DropdownMenuItem onSelect={() => setNewVersionOpen(true)}>
                <Plus size={15} aria-hidden="true" /> New version…
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void handleExport("md")}>
                <FileText size={15} aria-hidden="true" /> Export Markdown
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void handleExport("pdf")}>
                <Download size={15} aria-hidden="true" /> Export PDF
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => updateIdea.mutate({ pinned: !idea.pinned })}>
                {idea.pinned ? (
                  <>
                    <PinOff size={15} aria-hidden="true" /> Unpin
                  </>
                ) : (
                  <>
                    <Pin size={15} aria-hidden="true" /> Pin
                  </>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => updateIdea.mutate({ archived: !idea.archived_at })}>
                {idea.archived_at ? (
                  <>
                    <ArchiveRestore size={15} aria-hidden="true" /> Unarchive
                  </>
                ) : (
                  <>
                    <Archive size={15} aria-hidden="true" /> Archive
                  </>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <header className="mb-8">
        <TitleEditor title={idea.title} onSave={(title) => updateIdea.mutate({ title })} />
        {idea.one_liner && <p className="t-lead measure mt-2">{idea.one_liner}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <StatusBadge status={idea.status} />
          <VerdictBadge verdict={idea.verdict} />
          {idea.overall_score != null && <OverallScore score={idea.overall_score} />}
          {idea.archived_at && <span className="badge">Archived</span>}
          {idea.tags.map((tag) => (
            <span key={tag} className="badge">
              #{tag}
            </span>
          ))}
          <span className="t-meta">updated {relativeTime(idea.updated_at)}</span>
        </div>
        {exportState !== "idle" && (
          <p className="t-meta mt-3" aria-live="polite">
            Preparing {exportState === "md" ? "Markdown" : "PDF"} export…
          </p>
        )}
        {exportError && (
          <p className="status status--error mt-3" role="alert">
            {exportError}
          </p>
        )}
      </header>

      <div className="grid gap-8">
        {awaitingInput && questions.length > 0 && (
          <ClarifyForm
            questions={questions}
            isPending={respondToRun.isPending}
            onSubmit={(answers) => {
              if (run) respondToRun.mutate({ runId: run.id, body: { answers } });
            }}
            onSkip={() => {
              if (run) respondToRun.mutate({ runId: run.id, body: { skip: true } });
            }}
          />
        )}

        {run && !showReport && (
          <ProgressTimeline run={run} progress={progress} onRetry={handleRerun} />
        )}

        {run && showReport && (
          <details className="rounded-card border border-line bg-surface">
            <summary className="flex cursor-pointer items-center justify-between gap-3 p-4 font-bold">
              <span>Run details</span>
              <span className="t-meta font-normal">
                {run.status} · ${run.cost_usd.toFixed(2)} of ${run.cost_cap_usd.toFixed(2)}
              </span>
            </summary>
            <div className="border-t border-line p-4">
              <ProgressTimeline
                run={run}
                progress={progress}
                onRetry={handleRerun}
                variant="plain"
              />
            </div>
          </details>
        )}

        {idea.status === "failed" && !run && (
          <p className="status status--error" role="alert">
            The analysis failed before starting. Create a new version to retry.
          </p>
        )}

        {reportEnabled && reportQuery.isPending && (
          <div className="grid gap-4" aria-busy="true">
            <div className="h-40 animate-pulse rounded-card bg-surface-subtle" />
            <div className="h-64 animate-pulse rounded-card bg-surface-subtle" />
          </div>
        )}

        {reportEnabled && reportQuery.isError && (
          <p className="t-body" role="alert">
            Could not load the report.{" "}
            <button
              type="button"
              className="link cursor-pointer"
              onClick={() => void reportQuery.refetch()}
            >
              Retry
            </button>
          </p>
        )}

        {showReport && report && (
          <>
            {report.header.partial && (
              <div
                className="flex items-start gap-3 rounded-card border border-line bg-surface-subtle p-4"
                role="status"
                data-testid="partial-banner"
              >
                <AlertTriangle size={18} className="mt-1 text-warning" aria-hidden="true" />
                <div>
                  <p className="t-body font-bold text-ink">Partial report</p>
                  <p className="t-body">
                    The run stopped before finishing.
                    {missingSections.length > 0 &&
                      ` Not completed: ${missingSections
                        .map((key) => REPORT_TABS.find((tab) => tab.id === key)?.label)
                        .join(", ")}.`}
                  </p>
                </div>
              </div>
            )}

            <Tabs
              value={activeTab}
              onValueChange={(value) => selectTab(value as ReportTab)}
              className="min-w-0"
            >
              <div className="overflow-x-auto pb-1">
                <TabsList aria-label="Report sections">
                  {REPORT_TABS.map((tab) => (
                    <TabsTrigger key={tab.id} value={tab.id} className="min-h-9 px-4">
                      {tab.label}
                      {report.sections_status?.[tab.id as keyof typeof report.sections_status] ===
                        "not_completed" && " —"}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>
              {REPORT_TABS.map((tab) => (
                <TabsContent key={tab.id} value={tab.id} className="pt-6">
                  <ReportView
                    report={report}
                    tab={tab.id}
                    onRerun={activeVersion == null ? handleRerun : undefined}
                    rerunningStep={rerunningStep}
                  />
                </TabsContent>
              ))}
            </Tabs>
          </>
        )}

        {!reportEnabled && !run && idea.status === "draft" && (
          <p className="t-body">
            This idea has not been analyzed yet. Create a new version to start the pipeline.
          </p>
        )}
      </div>

      {similar.length > 0 && (
        <section aria-labelledby="similar-heading" className="mt-16">
          <h2 id="similar-heading" className="t-subsection mb-4">
            Similar ideas
          </h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {similar.map((item) => (
              <IdeaCard key={item.id} idea={item} headingLevel={3} />
            ))}
          </div>
        </section>
      )}

      <Dialog open={newVersionOpen} onOpenChange={setNewVersionOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New version</DialogTitle>
            <DialogDescription>
              Editing the input starts a fresh analysis run. Old versions stay readable.
            </DialogDescription>
          </DialogHeader>
          <div className="field">
            <label className="field__label" htmlFor="new-version-input">
              Updated description
            </label>
            <textarea
              id="new-version-input"
              className="field__control min-h-32"
              value={newVersionInput}
              onChange={(event) => setNewVersionInput(event.target.value)}
              maxLength={5000}
              placeholder={idea.latest_version?.raw_input.slice(0, 200)}
            />
          </div>
          <DialogFooter>
            <Button
              className="rounded-pill font-bold"
              disabled={newVersionInput.trim().length === 0 || addVersion.isPending}
              onClick={() => {
                addVersion.mutate(
                  { raw_input: newVersionInput.trim(), analyze: true },
                  {
                    onSuccess: () => {
                      setNewVersionOpen(false);
                      setNewVersionInput("");
                      selectVersion(undefined);
                      void queryClient.invalidateQueries({ queryKey: ["ideas"] });
                    },
                  },
                );
              }}
            >
              {addVersion.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" /> Queuing…
                </>
              ) : (
                "Start analysis"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
