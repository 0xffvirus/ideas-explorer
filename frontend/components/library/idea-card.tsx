"use client";

import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import { StatusBadge } from "@/components/status-badge";
import { VerdictBadge } from "@/components/verdict-badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { IdeaSummary } from "@/lib/api/types";
import { cn, formatDate } from "@/lib/utils";

export interface IdeaCardProps {
  idea: IdeaSummary;
  /** Highlighted as the current j/k keyboard selection. */
  keyboardSelected: boolean;
  compareSelected: boolean;
  /** True when 3 ideas are selected and this one is not: selection is full. */
  compareDisabled: boolean;
  onToggleCompare: (id: string) => void;
  linkRef: (node: HTMLAnchorElement | null) => void;
}

export function IdeaCard({
  idea,
  keyboardSelected,
  compareSelected,
  compareDisabled,
  onToggleCompare,
  linkRef,
}: IdeaCardProps) {
  const tags = idea.tags ?? [];

  return (
    <article
      data-selected={keyboardSelected || undefined}
      className={cn(
        "group h-full rounded-xl border border-border bg-card p-4 transition-colors",
        compareSelected && "border-primary/60 bg-accent/40",
        keyboardSelected && "ring-2 ring-ring ring-offset-2 ring-offset-background",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="pt-0.5">
          <Checkbox
            checked={compareSelected}
            disabled={compareDisabled}
            onCheckedChange={() => onToggleCompare(idea.id)}
            aria-label={`Select ${idea.title} for comparison`}
            title={compareDisabled ? "Select up to 3 ideas to compare" : undefined}
          />
        </div>
        <div className="min-w-0 flex-1">
          <Link
            ref={linkRef}
            href={`/ideas/${idea.id}`}
            className="rounded-md leading-snug font-medium text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
          >
            {idea.title}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={idea.status} />
            <VerdictBadge verdict={idea.verdict} />
            <ScoreBadge score={idea.overall_score} scale={100} />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {idea.category ? (
              <span className="text-xs text-muted-foreground">{idea.category}</span>
            ) : null}
            {tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
              >
                {tag}
              </span>
            ))}
            <span className="ml-auto text-xs text-muted-foreground">
              {formatDate(idea.created_at)}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
