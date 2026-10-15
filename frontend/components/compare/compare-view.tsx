"use client";

import Link from "next/link";
import { useMemo } from "react";

import { CompareTable } from "@/components/compare/compare-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompare } from "@/lib/api/queries";
import { parseCompareIds } from "@/lib/compare";

function UnavailableCard({ message }: { message: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-4 p-8">
        <p className="max-w-prose text-sm text-muted-foreground">{message}</p>
        <Button asChild variant="outline">
          <Link href="/ideas">Back to library</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function CompareSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-12 w-full rounded-xl" />
      <Skeleton className="h-12 w-full rounded-xl" />
      <Skeleton className="h-12 w-full rounded-xl" />
      <Skeleton className="h-12 w-full rounded-xl" />
      <Skeleton className="h-12 w-full rounded-xl" />
    </div>
  );
}

export interface CompareViewProps {
  /** Raw `ids` query value, e.g. "uuid,uuid". */
  rawIds: string | null;
}

/** `/compare` screen: validates the selection, then aligns 2–3 idea reports. */
export function CompareView({ rawIds }: CompareViewProps) {
  const parsed = useMemo(() => parseCompareIds(rawIds), [rawIds]);
  const ids = parsed.ok ? parsed.ids : [];
  const { data, isLoading, isError, refetch } = useCompare(ids);

  if (!parsed.ok) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Compare</h1>
        <UnavailableCard message={parsed.message} />
      </div>
    );
  }

  const entries = data?.entries ?? [];
  const ready = data !== undefined && entries.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Compare</h1>
        {ready ? (
          <p className="text-sm text-muted-foreground">{entries.length} ideas side by side</p>
        ) : null}
      </div>

      {isLoading ? <CompareSkeleton /> : null}

      {isError ? (
        <Card>
          <CardContent className="flex flex-col items-start gap-3 p-6">
            <p className="text-sm text-muted-foreground">
              Could not load the comparison. The selection may be invalid, or the API is down.
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                Try again
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/ideas">Back to library</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !isError && entries.length === 0 ? (
        <UnavailableCard message="These ideas could not be found. Pick 2–3 ideas from the library to compare them." />
      ) : null}

      {ready ? <CompareTable report={data} /> : null}
    </div>
  );
}
