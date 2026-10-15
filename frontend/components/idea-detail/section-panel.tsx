"use client";

import { RotateCw } from "lucide-react";

import { ClaimList } from "@/components/idea-detail/claim-list";
import { SafeMarkdown } from "@/components/idea-detail/safe-markdown";
import {
  hasStructuredContent,
  StructuredPayload,
} from "@/components/idea-detail/structured-payload";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ReportSection, Source } from "@/lib/api/types";
import type { PipelineStep } from "@/lib/progress";
import { cn } from "@/lib/utils";

/** Which pipeline step produces each report section. */
export const SECTION_STEP: Record<ReportSection["name"], PipelineStep> = {
  market: "market",
  competitors: "competitors",
  customers: "customers",
  feasibility: "feasibility",
  business_model: "business_model",
};

export interface SectionPanelProps {
  section: ReportSection | null;
  /** Section name, used when the report has no row for it at all. */
  sectionName: ReportSection["name"];
  sources: Source[];
  canRerun: boolean;
  rerunPending: boolean;
  onRerun: (step: PipelineStep) => void;
}

/**
 * One report section: structured payload cards with a markdown fallback, its
 * claims, and a Re-run button while a settled run exists.
 */
export function SectionPanel({
  section,
  sectionName,
  sources,
  canRerun,
  rerunPending,
  onRerun,
}: SectionPanelProps) {
  const step = SECTION_STEP[sectionName];
  const title = section?.title ?? step;
  const notCompleted = section === null || section.status === "not_completed";
  const payload = section?.json_payload ?? {};
  const hasStructured = hasStructuredContent(payload);
  const markdown = section?.markdown.trim() ?? "";
  const claims = section?.claims ?? [];

  return (
    <Card className={cn(notCompleted && "border-dashed")}>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle asChild>
          <h2>{title}</h2>
        </CardTitle>
        {canRerun ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRerun(step)}
            disabled={rerunPending}
          >
            <RotateCw aria-hidden="true" />
            Re-run {title}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {notCompleted ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-6 text-center">
            <p className="text-sm font-medium text-foreground">Not completed</p>
            <p className="mt-1 text-sm text-muted-foreground">
              This section did not finish. Re-run it to fill it in.
            </p>
          </div>
        ) : (
          <>
            {hasStructured ? <StructuredPayload payload={payload} /> : null}
            {!hasStructured && markdown !== "" ? <SafeMarkdown markdown={markdown} /> : null}
            {hasStructured && markdown !== "" ? (
              <SafeMarkdown markdown={markdown} className="border-t border-border pt-4" />
            ) : null}
            {!hasStructured && markdown === "" ? (
              <p className="text-sm text-muted-foreground">
                No content was produced for this section.
              </p>
            ) : null}
          </>
        )}
        {!notCompleted && claims.length > 0 ? (
          <div className="border-t border-border pt-4">
            <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Claims
            </h3>
            <ClaimList claims={claims} sources={sources} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
