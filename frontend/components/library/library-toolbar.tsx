"use client";

import { Check, ChevronDown, Columns3, List, Search, X } from "lucide-react";
import type { Ref } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import type { TagCount } from "@/lib/api/types";
import {
  activeFilterCount,
  MODE_OPTIONS,
  SCORE_FILTER_MAX,
  SCORE_FILTER_MIN,
  SORT_OPTIONS,
  STATUS_OPTIONS,
  VERDICT_OPTIONS,
  type LibraryFilters,
  type LibraryView as LibraryViewName,
} from "@/lib/library-filters";
import { cn } from "@/lib/utils";

const MODE_HINTS: Record<LibraryFilters["mode"], string> = {
  hybrid: "Matching by meaning and keywords",
  keyword: "Keyword match",
  semantic: "Semantic match",
};

const chipClass = (selected: boolean) =>
  cn(
    "inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    selected
      ? "border-primary bg-primary text-primary-foreground"
      : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
  );

function Chip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={label}
      onClick={onClick}
      className={chipClass(selected)}
    >
      {label.replace(/^[^:]+:\s*/, "")}
    </button>
  );
}

export interface LibraryToolbarProps {
  filters: LibraryFilters;
  queryInput: string;
  onQueryInputChange: (value: string) => void;
  searchInputRef: Ref<HTMLInputElement>;
  onChange: (patch: Partial<LibraryFilters>) => void;
  categories: string[];
  tags: TagCount[];
}

export function LibraryToolbar({
  filters,
  queryInput,
  onQueryInputChange,
  searchInputRef,
  onChange,
  categories,
  tags,
}: LibraryToolbarProps) {
  const sortLabel = SORT_OPTIONS.find((option) => option.value === filters.sort)?.label ?? "Recent";
  const filterCount = activeFilterCount(filters);

  return (
    <div className="mt-6 flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-md">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <label htmlFor="library-search" className="sr-only">
            Search ideas
          </label>
          <Input
            id="library-search"
            ref={searchInputRef}
            type="search"
            value={queryInput}
            onChange={(event) => onQueryInputChange(event.target.value)}
            placeholder="Search ideas…"
            className="pl-9"
          />
        </div>

        <div
          role="group"
          aria-label="Search mode"
          className="inline-flex shrink-0 rounded-lg border border-border bg-card p-0.5"
        >
          {MODE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filters.mode === option.value}
              aria-label={`Search mode: ${option.label}`}
              onClick={() => onChange({ mode: option.value })}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none",
                filters.mode === option.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 sm:ml-auto">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" aria-label={`Sort by: ${sortLabel}`}>
                Sort: {sortLabel}
                <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {SORT_OPTIONS.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  onSelect={() => onChange({ sort: option.value })}
                >
                  <Check
                    className={cn(
                      "size-4",
                      option.value === filters.sort ? "opacity-100" : "opacity-0",
                    )}
                    aria-hidden="true"
                  />
                  {option.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <div
            role="group"
            aria-label="View"
            className="inline-flex rounded-lg border border-border bg-card p-0.5"
          >
            {(
              [
                { value: "list", label: "List view", Icon: List },
                { value: "board", label: "Board view", Icon: Columns3 },
              ] as const
            ).map(({ value, label, Icon }) => (
              <button
                key={value}
                type="button"
                aria-pressed={filters.view === value}
                aria-label={label}
                onClick={() => onChange({ view: value as LibraryViewName })}
                className={cn(
                  "inline-flex items-center rounded-md px-2 py-1 transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none",
                  filters.view === value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div role="group" aria-label="Status" className="flex flex-wrap items-center gap-1.5">
          {STATUS_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              label={`Status: ${option.label}`}
              selected={filters.status === option.value}
              onClick={() =>
                onChange({ status: filters.status === option.value ? null : option.value })
              }
            />
          ))}
        </div>
        <div role="group" aria-label="Verdict" className="flex flex-wrap items-center gap-1.5">
          {VERDICT_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              label={`Verdict: ${option.label}`}
              selected={filters.verdict === option.value}
              onClick={() =>
                onChange({ verdict: filters.verdict === option.value ? null : option.value })
              }
            />
          ))}
        </div>

        {categories.length > 0 ? (
          <div role="group" aria-label="Category" className="flex flex-wrap items-center gap-1.5">
            {categories.map((category) => (
              <Chip
                key={category}
                label={`Category: ${category}`}
                selected={filters.category === category}
                onClick={() =>
                  onChange({ category: filters.category === category ? null : category })
                }
              />
            ))}
          </div>
        ) : null}

        {tags.length > 0 ? (
          <div role="group" aria-label="Tag" className="flex flex-wrap items-center gap-1.5">
            {tags.map((tag) => (
              <Chip
                key={tag.name}
                label={`Tag: ${tag.name}`}
                selected={filters.tag === tag.name}
                onClick={() => onChange({ tag: filters.tag === tag.name ? null : tag.name })}
              />
            ))}
          </div>
        ) : null}

        <div role="group" aria-label="Score range" className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Score ({SCORE_FILTER_MIN}–{SCORE_FILTER_MAX})
          </span>
          <label htmlFor="score-min" className="sr-only">
            Minimum score, {SCORE_FILTER_MIN} to {SCORE_FILTER_MAX}
          </label>
          <Input
            id="score-min"
            type="number"
            min={SCORE_FILTER_MIN}
            max={SCORE_FILTER_MAX}
            step={1}
            value={filters.scoreMin ?? ""}
            onChange={(event) =>
              onChange({
                scoreMin: event.target.value === "" ? null : Number(event.target.value),
              })
            }
            className="h-8 w-20 text-xs"
            aria-label="Minimum score"
          />
          <span className="text-xs text-muted-foreground">to</span>
          <label htmlFor="score-max" className="sr-only">
            Maximum score, {SCORE_FILTER_MIN} to {SCORE_FILTER_MAX}
          </label>
          <Input
            id="score-max"
            type="number"
            min={SCORE_FILTER_MIN}
            max={SCORE_FILTER_MAX}
            step={1}
            value={filters.scoreMax ?? ""}
            onChange={(event) =>
              onChange({
                scoreMax: event.target.value === "" ? null : Number(event.target.value),
              })
            }
            className="h-8 w-20 text-xs"
            aria-label="Maximum score"
          />
        </div>

        {filterCount > 0 ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({
                status: null,
                verdict: null,
                category: null,
                tag: null,
                scoreMin: null,
                scoreMax: null,
              })
            }
          >
            <X aria-hidden="true" />
            Clear filters
          </Button>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        {filters.q.trim() !== "" ? MODE_HINTS[filters.mode] : "Search by keyword or meaning"}
      </p>
    </div>
  );
}
