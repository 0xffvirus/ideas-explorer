import type { Metadata } from "next";
import { Suspense } from "react";

import { LibraryView } from "@/components/library/library-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Library",
};

export default function IdeasPage() {
  return (
    <Suspense fallback={<LibrarySkeleton />}>
      <LibraryView />
    </Suspense>
  );
}

function LibrarySkeleton() {
  return (
    <div aria-hidden="true">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="mt-6 h-10 w-full max-w-md" />
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-28 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
