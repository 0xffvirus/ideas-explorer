"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { useSimilarIdeas } from "@/lib/api/queries";

export interface SimilarIdeasProps {
  ideaId: string;
}

/** Sidebar of neighbouring ideas; renders nothing while empty or loading. */
export function SimilarIdeas({ ideaId }: SimilarIdeasProps) {
  const { data } = useSimilarIdeas(ideaId);
  const ideas = data ?? [];
  if (ideas.length === 0) return null;

  return (
    <section aria-labelledby="similar-ideas-heading" className="flex flex-col gap-3">
      <h2 id="similar-ideas-heading" className="text-sm font-semibold tracking-tight">
        Similar ideas
      </h2>
      <ul className="flex flex-col gap-2">
        {ideas.map((idea) => (
          <li key={idea.id}>
            <Link
              href={`/ideas/${idea.id}`}
              className="group flex items-start justify-between gap-2 rounded-lg border border-border bg-card p-3 text-sm transition-colors hover:border-ring focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
            >
              <span className="leading-snug font-medium text-foreground">{idea.title}</span>
              <ArrowUpRight
                className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
