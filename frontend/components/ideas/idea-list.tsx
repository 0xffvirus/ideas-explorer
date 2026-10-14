"use client";

import { memo } from "react";
import Link from "next/link";
import type { Route } from "next";
import { Checkbox } from "@/components/ui/checkbox";
import type { IdeaSummary } from "@/lib/api/types";
import { relativeTime, truncate } from "@/lib/format";
import { OverallScore, StatusBadge, VerdictBadge } from "./badges";

type IdeaListProps = {
  items: IdeaSummary[];
  selected: string[];
  onToggleSelected: (id: string) => void;
};

export const IdeaList = memo(function IdeaList({
  items,
  selected,
  onToggleSelected,
}: IdeaListProps) {
  return (
    <ul className="rows" data-testid="idea-list">
      {items.map((idea) => (
        <li key={idea.id} className="group flex items-start gap-4" data-idea-id={idea.id}>
          <span className="flex min-h-11 items-center pt-1">
            <Checkbox
              checked={selected.includes(idea.id)}
              onCheckedChange={() => onToggleSelected(idea.id)}
              aria-label={`Select ${idea.title} for comparison`}
              data-testid="idea-select"
            />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="t-card">
              <Link
                href={`/ideas/${idea.id}` as Route}
                className="rounded-field group-hover:underline group-hover:decoration-2"
                data-idea-link
              >
                {truncate(idea.title, 100)}
              </Link>
            </h2>
            {idea.one_liner && <p className="t-body line-clamp-1">{idea.one_liner}</p>}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={idea.status} />
              <VerdictBadge verdict={idea.verdict} />
              {idea.overall_score != null && <OverallScore score={idea.overall_score} />}
              {idea.category && <span className="badge">{idea.category.replace("_", " ")}</span>}
              {idea.tags.map((tag) => (
                <span key={tag} className="t-meta">
                  #{tag}
                </span>
              ))}
              <span className="t-meta ms-auto">{relativeTime(idea.updated_at)}</span>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
});
