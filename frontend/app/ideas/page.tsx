import { Suspense } from "react";
import { LibraryScreen } from "./library-screen";

export const metadata = { title: "Library" };

// The library renders from runtime search params (URL-synced filters), so it
// cannot validate instant navigation of a prerendered segment.
export const instant = false;

function LibrarySkeleton() {
  return (
    <div
      className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24"
      aria-busy="true"
    >
      <div className="h-12 w-48 animate-pulse rounded-field bg-surface-subtle" />
      <div className="mt-6 h-13 animate-pulse rounded-field bg-surface-subtle" />
      <div className="mt-6 grid gap-3">
        {[0, 1, 2, 3, 4].map((index) => (
          <div key={index} className="h-20 animate-pulse rounded-card bg-surface-subtle" />
        ))}
      </div>
    </div>
  );
}

export default function IdeasPage() {
  return (
    <main id="main">
      <Suspense fallback={<LibrarySkeleton />}>
        <LibraryScreen />
      </Suspense>
    </main>
  );
}
