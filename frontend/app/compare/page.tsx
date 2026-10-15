import type { Metadata } from "next";
import { Suspense } from "react";

import { CompareView } from "@/components/compare/compare-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Compare",
};

export default function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string | string[] }>;
}) {
  return (
    <Suspense fallback={<CompareSkeleton />}>
      <CompareRoute searchParams={searchParams} />
    </Suspense>
  );
}

async function CompareRoute({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string | string[] }>;
}) {
  const params = await searchParams;
  const rawIds =
    typeof params.ids === "string" ? params.ids : (params.ids?.join(",") ?? null);
  return <CompareView rawIds={rawIds} />;
}

function CompareSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <Skeleton className="h-9 w-40" />
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}
