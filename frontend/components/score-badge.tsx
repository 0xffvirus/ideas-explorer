"use client";

import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const CONFIDENCE_THRESHOLD = 0.6;

/** Score scales used by the API: dimension scores are 1-5, overall scores 0-100. */
export type ScoreScale = 5 | 100;

export interface ScoreBadgeProps {
  /** Score value; `null`/`undefined` renders an em dash. */
  score: number | null | undefined;
  /** Which scale `score` is on. Defaults to the Jev dimension scale (5). */
  scale?: ScoreScale;
  /** Jev confidence in [0, 1]. Below 0.6 the badge is flagged with "?". */
  confidence?: number | null;
  className?: string;
}

export function ScoreBadge({ score, scale = 5, confidence, className }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-sm text-muted-foreground",
          className,
        )}
        aria-label="Not scored"
      >
        —
      </span>
    );
  }

  const hasConfidence = confidence !== null && confidence !== undefined;
  const uncertain = hasConfidence && confidence < CONFIDENCE_THRESHOLD;
  const formattedScore = Number.isInteger(score) ? String(score) : score.toFixed(1);
  const confidenceLabel = hasConfidence ? `Confidence ${Math.round(confidence * 100)}%` : null;

  const badge = (
    <span
      tabIndex={hasConfidence ? 0 : undefined}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm tabular-nums",
        uncertain
          ? "border-dashed border-border bg-transparent"
          : "border-transparent bg-muted text-foreground",
        hasConfidence &&
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none",
        className,
      )}
      aria-label={
        confidenceLabel
          ? `Score ${formattedScore} out of ${scale}. ${confidenceLabel}`
          : `Score ${formattedScore} out of ${scale}`
      }
    >
      {formattedScore}/{scale}
      {uncertain ? <span aria-hidden="true">?</span> : null}
    </span>
  );

  if (!hasConfidence) {
    return badge;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent>{confidenceLabel}</TooltipContent>
    </Tooltip>
  );
}
