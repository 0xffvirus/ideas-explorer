"use client";

import { cn } from "cn";
import type { DimensionScore } from "@/lib/api/types";
import { ScoreBadge } from "./badges";

export function Scorecard({ dimensions }: { dimensions: DimensionScore[] }) {
  const scored = dimensions.filter((dimension) => !dimension.not_scored);
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="scorecard">
      {dimensions.map((dimension) => (
        <div
          key={dimension.id}
          className={cn(
            "rounded-card border p-4",
            dimension.not_scored
              ? "border-dashed border-line-control bg-canvas"
              : "border-line bg-surface",
          )}
          data-dimension={dimension.id}
          data-needs-review={dimension.needs_review || undefined}
        >
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-ink">{dimension.label}</h3>
            {dimension.not_scored ? (
              <span className="badge border-dashed">not scored</span>
            ) : (
              <ScoreBadge score={dimension.score} confidence={dimension.confidence} />
            )}
          </div>
          {!dimension.not_scored && dimension.confidence != null && (
            <div className="mt-3" aria-hidden="true">
              <div className="h-1.5 overflow-hidden rounded-pill bg-surface-subtle">
                <div
                  className={cn(
                    "h-full rounded-pill",
                    dimension.needs_review ? "bg-ink-muted" : "bg-ink",
                  )}
                  style={{ width: `${Math.round(dimension.confidence * 100)}%` }}
                />
              </div>
              <p className="t-meta mt-1">Confidence {(dimension.confidence * 100).toFixed(0)}%</p>
            </div>
          )}
          {dimension.rationale && <p className="t-body mt-3 text-sm">{dimension.rationale}</p>}
        </div>
      ))}
      {scored.length < dimensions.length && (
        <p className="t-meta sm:col-span-2">
          Dimensions marked “not scored” are excluded from the overall score — the denominator
          shrinks, the 0–100 scale does not.
        </p>
      )}
    </div>
  );
}
