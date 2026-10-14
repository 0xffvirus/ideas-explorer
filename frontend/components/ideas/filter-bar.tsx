"use client";

import { ChevronDown, LayoutGrid, Rows3, X } from "lucide-react";
import { cn } from "cn";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CATEGORY_OPTIONS,
  SORT_OPTIONS,
  STATUS_OPTIONS,
  VERDICT_OPTIONS,
  scoreBandLabel,
} from "@/lib/labels";
import type { LibraryFilters } from "@/lib/library-params";

type FilterBarProps = {
  filters: LibraryFilters;
  onChange: (patch: Partial<LibraryFilters>) => void;
  onClearAll: () => void;
  tags: { name: string; count: number }[];
};

function ChipButton({
  label,
  active,
  ...props
}: React.ComponentProps<"button"> & { label: string; active?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        "inline-flex min-h-9 items-center gap-1.5 rounded-pill border px-3.5 text-sm font-medium transition-colors",
        active
          ? "border-ink bg-ink text-on-action"
          : "border-line bg-surface text-ink-secondary hover:bg-surface-subtle hover:text-ink",
      )}
    >
      {label}
      <ChevronDown size={14} aria-hidden="true" />
    </button>
  );
}

export function FilterBar({ filters, onChange, onClearAll, tags }: FilterBarProps) {
  const activePills: {
    key: keyof LibraryFilters;
    label: string;
    clear: Partial<LibraryFilters>;
  }[] = [];
  if (filters.status) {
    activePills.push({
      key: "status",
      label: STATUS_OPTIONS.find((o) => o.value === filters.status)?.label ?? filters.status,
      clear: { status: null },
    });
  }
  if (filters.verdict) {
    activePills.push({
      key: "verdict",
      label: VERDICT_OPTIONS.find((o) => o.value === filters.verdict)?.label ?? filters.verdict,
      clear: { verdict: null },
    });
  }
  if (filters.category) {
    activePills.push({
      key: "category",
      label: CATEGORY_OPTIONS.find((o) => o.value === filters.category)?.label ?? filters.category,
      clear: { category: null },
    });
  }
  if (filters.tag) {
    activePills.push({ key: "tag", label: `#${filters.tag}`, clear: { tag: null } });
  }
  if (filters.minScore != null || filters.maxScore != null) {
    activePills.push({
      key: "minScore",
      label: scoreBandLabel(filters.minScore ?? undefined, filters.maxScore ?? undefined),
      clear: { minScore: null, maxScore: null },
    });
  }
  if (filters.archived) {
    activePills.push({ key: "archived", label: "Archived", clear: { archived: false } });
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="filter-bar">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="Status" active={Boolean(filters.status)} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-44">
          <DropdownMenuLabel>Status</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={filters.status ?? "any"}
            onValueChange={(value) => onChange({ status: value === "any" ? null : value })}
          >
            <DropdownMenuRadioItem value="any">Any status</DropdownMenuRadioItem>
            {STATUS_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="Verdict" active={Boolean(filters.verdict)} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-44">
          <DropdownMenuLabel>Verdict</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={filters.verdict ?? "any"}
            onValueChange={(value) => onChange({ verdict: value === "any" ? null : value })}
          >
            <DropdownMenuRadioItem value="any">Any verdict</DropdownMenuRadioItem>
            {VERDICT_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="Category" active={Boolean(filters.category)} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-48">
          <DropdownMenuLabel>Category</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={filters.category ?? "any"}
            onValueChange={(value) => onChange({ category: value === "any" ? null : value })}
          >
            <DropdownMenuRadioItem value="any">Any category</DropdownMenuRadioItem>
            {CATEGORY_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="Tag" active={Boolean(filters.tag)} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="max-h-72 min-w-48 overflow-auto">
          <DropdownMenuLabel>Tag</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={filters.tag ?? "any"}
            onValueChange={(value) => onChange({ tag: value === "any" ? null : value })}
          >
            <DropdownMenuRadioItem value="any">Any tag</DropdownMenuRadioItem>
            {tags.map((tag) => (
              <DropdownMenuRadioItem key={tag.name} value={tag.name}>
                #{tag.name}
                <span className="ms-auto text-xs text-ink-muted">{tag.count}</span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="Score" active={filters.minScore != null || filters.maxScore != null} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56 p-4">
          <div className="grid gap-3">
            <p className="field__label">Overall score (0–100)</p>
            <div className="flex items-center gap-2">
              <label className="field__help" htmlFor="score-min">
                Min
              </label>
              <input
                id="score-min"
                type="number"
                min={0}
                max={100}
                value={filters.minScore ?? ""}
                onChange={(event) =>
                  onChange({
                    minScore: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
                className="field__control h-10 min-h-10 w-full"
              />
              <label className="field__help" htmlFor="score-max">
                Max
              </label>
              <input
                id="score-max"
                type="number"
                min={0}
                max={100}
                value={filters.maxScore ?? ""}
                onChange={(event) =>
                  onChange({
                    maxScore: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
                className="field__control h-10 min-h-10 w-full"
              />
            </div>
            <button
              type="button"
              className="link w-fit text-sm"
              onClick={() => onChange({ minScore: null, maxScore: null })}
            >
              Reset score
            </button>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label={SORT_OPTIONS.find((o) => o.value === filters.sort)?.label ?? "Sort"} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-48">
          <DropdownMenuLabel>Sort by</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={filters.sort}
            onValueChange={(value) => onChange({ sort: value as LibraryFilters["sort"] })}
          >
            {SORT_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ChipButton label="More" active={filters.archived} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-48">
          <DropdownMenuCheckboxItem
            checked={filters.archived}
            onCheckedChange={(checked) => onChange({ archived: Boolean(checked) })}
          >
            Show archived
          </DropdownMenuCheckboxItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {activePills.length > 0 && (
        <>
          <ul className="flex flex-wrap items-center gap-2 ps-2" aria-label="Active filters">
            {activePills.map((pill) => (
              <li key={pill.key}>
                <button
                  type="button"
                  onClick={() => onChange(pill.clear)}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-pill border border-ink bg-ink px-3 text-sm font-medium text-on-action"
                >
                  {pill.label}
                  <X size={14} aria-hidden="true" />
                  <span className="visually-hidden">Remove filter: {pill.label}</span>
                </button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={onClearAll} className="link min-h-8 text-sm">
            Clear all
          </button>
        </>
      )}

      <div className="ms-auto inline-flex items-center gap-2">
        <div
          role="group"
          aria-label="Layout"
          className="inline-flex rounded-pill border border-line bg-surface p-1"
        >
          <button
            type="button"
            aria-pressed={filters.view === "list"}
            onClick={() => onChange({ view: "list" })}
            className={cn(
              "inline-flex min-h-8 items-center gap-1.5 rounded-pill px-3 text-sm font-medium",
              filters.view === "list"
                ? "bg-ink text-on-action"
                : "text-ink-secondary hover:bg-surface-subtle",
            )}
          >
            <Rows3 size={14} aria-hidden="true" /> List
          </button>
          <button
            type="button"
            aria-pressed={filters.view === "board"}
            onClick={() => onChange({ view: "board" })}
            className={cn(
              "inline-flex min-h-8 items-center gap-1.5 rounded-pill px-3 text-sm font-medium",
              filters.view === "board"
                ? "bg-ink text-on-action"
                : "text-ink-secondary hover:bg-surface-subtle",
            )}
          >
            <LayoutGrid size={14} aria-hidden="true" /> Board
          </button>
        </div>
      </div>
    </div>
  );
}
