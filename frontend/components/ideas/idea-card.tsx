"use client";

import Link from "next/link";
import type { Route } from "next";
import { cn } from "cn";
import { Checkbox } from "@/components/ui/checkbox";
import type { IdeaSummary } from "@/lib/api/types";
import { relativeTime, truncate } from "@/lib/format";
import { OverallScore, StatusBadge, VerdictBadge } from "./badges";

type IdeaCardProps = {
  idea: IdeaSummary;
  selected?: boolean;
  onToggleSelected?: (id: string) => void;
  /** Heading level for the card title; set 3 when nested under a section heading. */
  headingLevel?: 2 | 3;
  className?: string;
};

export function IdeaCard({
  idea,
  selected,
  onToggleSelected,
  headingLevel = 2,
  className,
}: IdeaCardProps) {
  const href = `/ideas/${idea.id}` as Route;
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <article
      className={cn(
        "group relative flex flex-col gap-3 rounded-card border border-line bg-surface p-6 transition-shadow",
        "focus-within:shadow-soft hover:shadow-soft",
        selected && "border-ink ring-1 ring-ink",
        className,
      )}
      data-idea-id={idea.id}
    >
      <div className="flex items-start justify-between gap-3">
        <Heading className="t-card min-w-0">
          <Link
            href={href}
            className="rounded-field outline-offset-4 group-hover:underline group-hover:decoration-2 after:absolute after:inset-0 after:content-['']"
          >
            {truncate(idea.title, 90)}
          </Link>
        </Heading>
        {onToggleSelected && (
          <span className="relative z-10 flex min-h-11 items-center">
            <Checkbox
              checked={Boolean(selected)}
              onCheckedChange={() => onToggleSelected(idea.id)}
              aria-label={`Select ${idea.title} for comparison`}
              data-testid="idea-select"
            />
          </span>
        )}
      </div>

      {idea.one_liner && <p className="t-body -mt-1 line-clamp-2">{idea.one_liner}</p>}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
        <StatusBadge status={idea.status} />
        <VerdictBadge verdict={idea.verdict} />
        {idea.overall_score != null && <OverallScore score={idea.overall_score} />}
        {idea.pinned && <span className="badge">Pinned</span>}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="t-meta">{relativeTime(idea.updated_at)}</span>
        {idea.tags.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Tags">
            {idea.tags.map((tag) => (
              <li key={tag} className="t-meta">
                #{tag}
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
