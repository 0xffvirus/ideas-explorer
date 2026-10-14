"use client";

import { cn } from "cn";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { IdeaStatus, Verdict } from "@/lib/api/types";

export const CONFIDENCE_FLOOR = 0.6;

export function ScoreBadge({
  score,
  confidence,
  className,
}: {
  score: number | null | undefined;
  confidence: number | null | undefined;
  className?: string;
}) {
  if (score == null) {
    return <span className={cn("badge", className)}>Not scored</span>;
  }
  const hasConfidence = confidence != null;
  const uncertain = hasConfidence && confidence < CONFIDENCE_FLOOR;
  const tooltip = hasConfidence
    ? `Jev confidence ${(confidence * 100).toFixed(0)}%${uncertain ? " — flagged for review" : ""}`
    : "No confidence reported";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn("badge tabular-nums", uncertain && "border-dashed", className)}
          data-uncertain={uncertain || undefined}
        >
          {score}/5
          {uncertain ? " ?" : ""}
          {hasConfidence && (
            <span className="sr-only">
              , Jev confidence {(confidence * 100).toFixed(0)} percent
              {uncertain ? ", flagged for review" : ""}
            </span>
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
}

export function OverallScore({
  score,
  className,
}: {
  score: number | null | undefined;
  className?: string;
}) {
  if (score == null) {
    return (
      <span className={cn("badge tabular-nums", className)} data-testid="overall-score">
        —
      </span>
    );
  }
  return (
    <span
      className={cn("badge font-bold text-ink tabular-nums", className)}
      data-testid="overall-score"
    >
      {Math.round(score * 10) / 10}
      <span className="sr-only"> out of 100</span>
      <span aria-hidden="true">/100</span>
    </span>
  );
}

const STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Draft",
  queued: "Queued",
  analyzing: "Analyzing",
  done: "Analyzed",
  failed: "Failed",
};

export function StatusBadge({ status, className }: { status: IdeaStatus; className?: string }) {
  return (
    <span className={cn("badge", className)} data-status={status}>
      {(status === "queued" || status === "analyzing") && (
        <span
          className="me-2 inline-block size-2 animate-pulse rounded-full bg-ink-muted"
          aria-hidden="true"
        />
      )}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const VERDICT_LABELS: Record<Verdict, string> = {
  pursue: "Pursue",
  refine: "Refine",
  park: "Park",
};

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: Verdict | null | undefined;
  className?: string;
}) {
  if (!verdict) return null;
  return (
    <span className={cn("badge font-bold text-ink", className)} data-verdict={verdict}>
      {VERDICT_LABELS[verdict]}
    </span>
  );
}
