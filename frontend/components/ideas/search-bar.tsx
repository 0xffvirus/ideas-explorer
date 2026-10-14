"use client";

import { useRef } from "react";
import { Search } from "lucide-react";
import { MATCH_HINTS, MODE_OPTIONS } from "@/lib/labels";
import type { SearchMode } from "@/lib/api/types";
import { cn } from "cn";

type SearchBarProps = {
  value: string;
  onValueChange: (value: string) => void;
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  activeMatch: SearchMode | null;
  inputRef?: React.Ref<HTMLInputElement>;
};

export function SearchBar({
  value,
  onValueChange,
  mode,
  onModeChange,
  activeMatch,
  inputRef,
}: SearchBarProps) {
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function onModeKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = (index + delta + MODE_OPTIONS.length) % MODE_OPTIONS.length;
    onModeChange(MODE_OPTIONS[next].value);
    optionRefs.current[next]?.focus();
  }

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-0 flex-1 basis-72">
          <Search
            size={18}
            aria-hidden="true"
            className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-ink-muted"
          />
          <input
            ref={inputRef}
            id="library-search"
            type="search"
            value={value}
            onChange={(event) => onValueChange(event.target.value)}
            placeholder="Search ideas by keyword or meaning…"
            className="field__control ps-11"
            aria-label="Search ideas"
            autoComplete="off"
            data-testid="library-search"
          />
        </div>
        <div
          role="radiogroup"
          aria-label="Search mode"
          className="inline-flex rounded-pill border border-line bg-surface p-1"
        >
          {MODE_OPTIONS.map((option, index) => (
            <button
              key={option.value}
              ref={(element) => {
                optionRefs.current[index] = element;
              }}
              type="button"
              role="radio"
              aria-checked={mode === option.value}
              tabIndex={mode === option.value ? 0 : -1}
              title={option.hint}
              onClick={() => onModeChange(option.value)}
              onKeyDown={(event) => onModeKeyDown(event, index)}
              className={cn(
                "min-h-9 rounded-pill px-4 text-sm font-medium transition-colors",
                mode === option.value
                  ? "bg-ink text-on-action"
                  : "text-ink-secondary hover:bg-surface-subtle",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {value.trim() !== "" && activeMatch && (
        <p className="t-meta ps-1" data-testid="match-hint">
          {MATCH_HINTS[activeMatch]}
        </p>
      )}
    </div>
  );
}
