export function IdeaPageSkeleton() {
  return (
    <div
      className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24"
      aria-busy="true"
      data-testid="idea-skeleton"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="h-5 w-40 animate-pulse rounded-field bg-surface-subtle" />
        <div className="h-8 w-28 animate-pulse rounded-pill bg-surface-subtle" />
      </div>
      <div className="mb-2 h-12 w-3/4 animate-pulse rounded-field bg-surface-subtle" />
      <div className="mb-4 h-12 w-1/2 animate-pulse rounded-field bg-surface-subtle" />
      <div className="mb-4 h-5 w-2/3 animate-pulse rounded-field bg-surface-subtle" />
      <div className="mb-10 flex gap-2">
        <div className="h-6 w-20 animate-pulse rounded-pill bg-surface-subtle" />
        <div className="h-6 w-24 animate-pulse rounded-pill bg-surface-subtle" />
        <div className="h-6 w-16 animate-pulse rounded-pill bg-surface-subtle" />
      </div>
      <div className="h-[26rem] animate-pulse rounded-card bg-surface-subtle" />
    </div>
  );
}
