"use client";

import { memo } from "react";
import Link from "next/link";
import type { Route } from "next";
import { cn } from "cn";
import { Checkbox } from "@/components/ui/checkbox";
import type { IdeaStatus, IdeaSummary } from "@/lib/api/types";
import { relativeTime, truncate } from "@/lib/format";
import { OverallScore, VerdictBadge } from "./badges";
import { STATUS_OPTIONS } from "@/lib/labels";

const BOARD_COLUMNS: IdeaStatus[] = ["draft", "queued", "analyzing", "done", "failed"];

type IdeaBoardProps = {
  items: IdeaSummary[];
  selected: string[];
  onToggleSelected: (id: string) => void;
};

export const IdeaBoard = memo(function IdeaBoard({
  items,
  selected,
  onToggleSelected,
}: IdeaBoardProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-5" data-testid="idea-board">
      {BOARD_COLUMNS.map((status) => {
        const column = items.filter((idea) => idea.status === status);
        const label = STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
        return (
          <section
            key={status}
            aria-label={`${label} — ${column.length} ideas`}
            className="rounded-card border border-line bg-surface-subtle/60 p-3"
          >
            <h2 className="t-meta mb-3 flex items-center justify-between px-1 font-bold">
              <span>{label}</span>
              <span className="tabular-nums">{column.length}</span>
            </h2>
            <ul className="grid gap-2">
              {column.map((idea) => (
                <li key={idea.id} data-idea-id={idea.id}>
                  <div
                    className={cn(
                      "group relative rounded-field border border-line bg-surface p-3",
                      selected.includes(idea.id) && "border-ink ring-1 ring-ink",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <Checkbox
                        checked={selected.includes(idea.id)}
                        onCheckedChange={() => onToggleSelected(idea.id)}
                        aria-label={`Select ${idea.title} for comparison`}
                        data-testid="idea-select"
                        className="mt-1"
                      />
                      <h3 className="text-sm leading-snug font-medium">
                        <Link
                          href={`/ideas/${idea.id}` as Route}
                          className="rounded-field group-hover:underline after:absolute after:inset-0 after:content-['']"
                          data-idea-link
                        >
                          {truncate(idea.title, 70)}
                        </Link>
                      </h3>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 ps-7">
                      <VerdictBadge verdict={idea.verdict} />
                      {idea.overall_score != null && <OverallScore score={idea.overall_score} />}
                      <span className="t-meta ms-auto">{relativeTime(idea.updated_at)}</span>
                    </div>
                  </div>
                </li>
              ))}
              {column.length === 0 && <li className="t-meta px-1 py-2">Nothing here</li>}
            </ul>
          </section>
        );
      })}
    </div>
  );
});
