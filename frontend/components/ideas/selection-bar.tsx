"use client";

import { Button } from "@/components/ui/button";
import type { IdeaSummary } from "@/lib/api/types";

type SelectionBarProps = {
  items: IdeaSummary[];
  selected: string[];
  onClear: () => void;
  onCompare: () => void;
};

export function SelectionBar({ items, selected, onClear, onCompare }: SelectionBarProps) {
  if (selected.length === 0) return null;
  const titles = selected
    .map((id) => items.find((idea) => idea.id === id)?.title)
    .filter(Boolean)
    .join(", ");

  return (
    <div
      role="region"
      aria-label="Compare selection"
      className="z-status fixed inset-x-0 bottom-4 flex justify-center px-4"
      data-testid="selection-bar"
    >
      <div className="flex flex-wrap items-center gap-3 rounded-pill border border-line bg-surface px-5 py-2 shadow-lift">
        <p className="t-meta" aria-live="polite">
          {selected.length} selected
          {titles && <span className="visually-hidden">: {titles}</span>}
        </p>
        <Button
          type="button"
          size="sm"
          onClick={onCompare}
          disabled={selected.length < 2}
          title={selected.length < 2 ? "Select at least two ideas" : "Compare selected ideas"}
          className="rounded-pill font-bold"
        >
          Compare
        </Button>
        <button type="button" onClick={onClear} className="link text-sm">
          Clear
        </button>
      </div>
    </div>
  );
}
