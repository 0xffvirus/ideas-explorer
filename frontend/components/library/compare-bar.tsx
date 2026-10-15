"use client";

import Link from "next/link";
import { GitCompare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { clearCompareSelection, MAX_COMPARE_SELECTION } from "@/lib/stores";

export interface CompareBarProps {
  selectedIds: string[];
}

export function CompareBar({ selectedIds }: CompareBarProps) {
  if (selectedIds.length === 0) return null;

  const canCompare = selectedIds.length >= 2 && selectedIds.length <= MAX_COMPARE_SELECTION;

  return (
    <div
      role="region"
      aria-label="Comparison selection"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4"
    >
      <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-border bg-card px-4 py-2 shadow-lg">
        <span className="text-sm text-muted-foreground" aria-live="polite">
          {selectedIds.length} of {MAX_COMPARE_SELECTION} selected
        </span>
        {canCompare ? (
          <Button asChild size="sm">
            <Link href={`/compare?ids=${selectedIds.join(",")}`}>
              <GitCompare aria-hidden="true" />
              Compare selected
            </Link>
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">Pick one more to compare</span>
        )}
        <Button variant="ghost" size="sm" onClick={clearCompareSelection}>
          Clear
        </Button>
      </div>
    </div>
  );
}
