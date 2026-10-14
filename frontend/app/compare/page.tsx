import { Suspense } from "react";
import { CompareScreen } from "./compare-screen";

export const metadata = { title: "Compare" };

// Compare renders from runtime search params (?ids=); instant-navigation
// validation of a prerendered segment does not apply.
export const instant = false;

function CompareSkeleton() {
  return (
    <div
      className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24"
      aria-busy="true"
    >
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="t-section">Compare</h1>
          <p className="t-meta mt-1">&nbsp;</p>
        </div>
        <div className="h-11 w-36 animate-pulse rounded-pill bg-surface-subtle" />
      </div>
      <div className="grid gap-x-6 lg:grid-cols-[200px_1fr_1fr]">
        <div className="hidden lg:block" />
        <div className="h-40 animate-pulse rounded-card bg-surface-subtle" />
        <div className="h-40 animate-pulse rounded-card bg-surface-subtle" />
        <div className="h-96 animate-pulse rounded-card bg-surface-subtle lg:col-span-3" />
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <main id="main">
      <Suspense fallback={<CompareSkeleton />}>
        <CompareScreen />
      </Suspense>
    </main>
  );
}
