"use client";

import { IdeaCard } from "@/components/ideas/idea-card";
import { useIdeas } from "@/lib/api/hooks";

export function RecentIdeas() {
  const query = useIdeas({ sort: "recent", limit: 6 });
  const items = query.data?.pages.flatMap((page) => page.items).slice(0, 6) ?? [];

  if (query.isPending) {
    return (
      <div
        className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
        aria-busy="true"
        aria-label="Loading recent ideas"
      >
        {[0, 1, 2].map((index) => (
          <div key={index} className="h-44 animate-pulse rounded-card bg-surface-subtle" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <p className="t-body" role="alert">
        Could not load recent ideas.{" "}
        <button type="button" className="link cursor-pointer" onClick={() => void query.refetch()}>
          Retry
        </button>
      </p>
    );
  }

  if (items.length === 0) {
    return (
      <p className="t-body">
        Nothing here yet — your first analysis will appear here as soon as it is queued.
      </p>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((idea) => (
        <IdeaCard key={idea.id} idea={idea} headingLevel={3} />
      ))}
    </div>
  );
}
