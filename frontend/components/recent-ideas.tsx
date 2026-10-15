"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { VerdictBadge } from "@/components/verdict-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useIdeas } from "@/lib/api/queries";
import { formatDate } from "@/lib/utils";

export function RecentIdeas() {
  const { data, isLoading, isError } = useIdeas({ limit: 6, sort: "recent" });
  const ideas = data?.pages.flatMap((page) => page.items ?? []) ?? [];

  return (
    <section aria-labelledby="recent-heading" className="mx-auto mt-16 w-full max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <h2 id="recent-heading" className="text-lg font-semibold tracking-tight">
          Recent ideas
        </h2>
        {ideas.length > 0 ? (
          <Link
            href="/ideas"
            className="inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
          >
            View all
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : null}

      {isError ? (
        <p className="mt-4 text-sm text-muted-foreground">
          Could not load recent ideas. Is the API running?
        </p>
      ) : null}

      {!isLoading && !isError && ideas.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No ideas yet — yours will appear here.</p>
      ) : null}

      {ideas.length > 0 ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {ideas.map((idea) => (
            <li key={idea.id}>
              <Link
                href={`/ideas/${idea.id}`}
                className="block rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
              >
                <Card className="h-full transition-colors hover:border-ring">
                  <CardContent className="flex h-full flex-col gap-3 p-4">
                    <p className="line-clamp-2 text-sm leading-snug font-medium text-foreground">
                      {idea.title}
                    </p>
                    <div className="mt-auto flex flex-wrap items-center gap-2">
                      <StatusBadge status={idea.status} />
                      <VerdictBadge verdict={idea.verdict} />
                      <span className="ml-auto text-xs text-muted-foreground">
                        {formatDate(idea.created_at)}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
