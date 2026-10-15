import type { ReactNode } from "react";

import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import { VerdictBadge } from "@/components/verdict-badge";
import { Button } from "@/components/ui/button";
import type { CompareEntry, CompareReport, IdeaVerdict, ScorecardEntry } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function toVerdict(value: string | null | undefined): IdeaVerdict | null {
  return value === "pursue" || value === "refine" || value === "park" ? value : null;
}

function humanizeDimension(dimension: string): string {
  return dimension
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function scorecardOf(entry: CompareEntry): Map<string, ScorecardEntry> {
  return new Map((entry.report?.scorecard ?? []).map((item) => [item.dimension, item]));
}

function dimensionLabel(dimension: string, entries: CompareEntry[]): string {
  for (const entry of entries) {
    const item = scorecardOf(entry).get(dimension);
    if (item?.label) return item.label;
  }
  return humanizeDimension(dimension);
}

const TABLE_CLASS = "w-full min-w-[640px] border-collapse text-sm";
const HEAD_CELL_CLASS =
  "sticky left-0 z-10 w-36 bg-card p-3 text-left align-top text-xs font-medium tracking-wide text-muted-foreground uppercase";

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <tr className="border-b border-border align-top last:border-0">
      <th scope="row" className={HEAD_CELL_CLASS}>
        {label}
      </th>
      {children}
    </tr>
  );
}

/** Side-by-side comparison: aligned summary rows plus a dimension matrix. */
export function CompareTable({ report }: { report: CompareReport }) {
  const entries = report.entries ?? [];
  const dimensions =
    (report.dimensions ?? []).length > 0
      ? (report.dimensions ?? [])
      : [...new Set(entries.flatMap((entry) => [...scorecardOf(entry).keys()]))];

  return (
    <div className="flex flex-col gap-8">
      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className={TABLE_CLASS}>
          <caption className="sr-only">Ideas compared side by side</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className={HEAD_CELL_CLASS}>
                Attribute
              </th>
              {entries.map((entry) => (
                <th
                  key={entry.idea_id}
                  scope="col"
                  className="min-w-44 p-3 text-left align-top font-medium"
                >
                  <Link
                    href={`/ideas/${entry.idea_id}`}
                    className="rounded-sm leading-snug text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
                  >
                    {entry.title ?? "Untitled idea"}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <SummaryRow label="One-liner">
              {entries.map((entry) => (
                <td key={entry.idea_id} className="p-3 align-top text-muted-foreground">
                  {entry.one_liner?.trim() || "—"}
                </td>
              ))}
            </SummaryRow>
            <SummaryRow label="Verdict">
              {entries.map((entry) => (
                <td key={entry.idea_id} className="p-3 align-top">
                  <span className="flex flex-wrap items-center gap-2">
                    <VerdictBadge verdict={toVerdict(entry.verdict)} />
                    {entry.verdict_confidence !== null &&
                    entry.verdict_confidence !== undefined ? (
                      <span className="text-xs text-muted-foreground">
                        {Math.round(entry.verdict_confidence * 100)}% confidence
                      </span>
                    ) : null}
                    {!entry.verdict ? <span className="text-muted-foreground">—</span> : null}
                  </span>
                </td>
              ))}
            </SummaryRow>
            <SummaryRow label="Overall score">
              {entries.map((entry) => (
                <td key={entry.idea_id} className="p-3 align-top">
                  <ScoreBadge score={entry.overall_score} scale={100} />
                </td>
              ))}
            </SummaryRow>
            <SummaryRow label="Category">
              {entries.map((entry) => (
                <td key={entry.idea_id} className="p-3 align-top text-muted-foreground">
                  {entry.category ?? "—"}
                </td>
              ))}
            </SummaryRow>
            <SummaryRow label="Report">
              {entries.map((entry) => (
                <td key={entry.idea_id} className="p-3 align-top">
                  {entry.report ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/ideas/${entry.idea_id}`}>Open report</Link>
                    </Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {entry.reason ?? "No completed report yet"}
                    </span>
                  )}
                </td>
              ))}
            </SummaryRow>
          </tbody>
        </table>
      </div>

      {dimensions.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className={TABLE_CLASS}>
            <caption className="sr-only">Dimension scores for each idea</caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className={cn(HEAD_CELL_CLASS, "normal-case")}>
                  Dimension
                </th>
                {entries.map((entry) => (
                  <th key={entry.idea_id} scope="col" className="min-w-44 p-3 text-left align-top">
                    {entry.title ?? "Untitled idea"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dimensions.map((dimension) => (
                <tr key={dimension} className="border-b border-border align-top last:border-0">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 w-36 bg-card p-3 text-left text-sm font-medium"
                  >
                    {dimensionLabel(dimension, entries)}
                  </th>
                  {entries.map((entry) => {
                    const item = scorecardOf(entry).get(dimension);
                    return (
                      <td key={entry.idea_id} className="p-3 align-top">
                        {item ? (
                          <span className="flex flex-wrap items-center gap-1.5">
                            <ScoreBadge score={item.score} confidence={item.confidence} />
                            {item.needs_review ? (
                              <span
                                className="text-sm text-muted-foreground"
                                aria-label="Needs review"
                                title="Needs review"
                              >
                                ?
                              </span>
                            ) : null}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
