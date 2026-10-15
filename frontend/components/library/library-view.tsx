"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CompareBar } from "@/components/library/compare-bar";
import { IdeaCard } from "@/components/library/idea-card";
import { LibraryToolbar } from "@/components/library/library-toolbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useIdeas, useTags } from "@/lib/api/queries";
import type { IdeaSummary } from "@/lib/api/types";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { isEditableTarget, nextSelectedIndex } from "@/lib/keyboard";
import { useExternalStore } from "@/lib/local-storage-store";
import {
  libraryFiltersToSearchParams,
  parseLibraryFilters,
  SEARCH_DEBOUNCE_MS,
  STATUS_OPTIONS,
  toIdeaQuery,
  type LibraryFilters,
} from "@/lib/library-filters";
import { compareSelectionStore, toggleCompareSelection, MAX_COMPARE_SELECTION } from "@/lib/stores";

export function LibraryView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const itemLinkRefs = useRef<Array<HTMLAnchorElement | null>>([]);
  const orderedLengthRef = useRef(0);

  const filters = useMemo(() => parseLibraryFilters(searchParams), [searchParams]);
  const filtersKey = useMemo(() => libraryFiltersToSearchParams(filters).toString(), [filters]);

  // Local input state, adopted from the URL when back/forward changes it.
  const [queryInput, setQueryInput] = useState(filters.q);
  const [lastUrlQuery, setLastUrlQuery] = useState(filters.q);
  if (filters.q !== lastUrlQuery) {
    setLastUrlQuery(filters.q);
    setQueryInput(filters.q);
  }
  const debouncedQuery = useDebouncedValue(queryInput, SEARCH_DEBOUNCE_MS);

  // j/k selection resets whenever the query string (and therefore the list) changes.
  const [focusIndex, setFocusIndex] = useState(-1);
  const [lastFiltersKey, setLastFiltersKey] = useState(filtersKey);
  if (filtersKey !== lastFiltersKey) {
    setLastFiltersKey(filtersKey);
    setFocusIndex(-1);
  }

  // Discrete actions (chips, sort, view) push history so back/forward restores
  // them; continuous typing replaces so it cannot flood the history stack.
  const applyFilters = useCallback(
    (patch: Partial<LibraryFilters>, history: "push" | "replace" = "push") => {
      const next = { ...filters, ...patch };
      const params = libraryFiltersToSearchParams(next).toString();
      const url = params ? `/ideas?${params}` : "/ideas";
      if (history === "replace") {
        router.replace(url, { scroll: false });
      } else {
        router.push(url, { scroll: false });
      }
    },
    [filters, router],
  );

  useEffect(() => {
    const next = debouncedQuery.trim();
    if (next !== queryInput.trim()) return;
    if (next === filters.q) return;
    applyFilters({ q: next }, "replace");
  }, [debouncedQuery, queryInput, filters.q, applyFilters]);

  const query = useMemo(() => toIdeaQuery(filters), [filters]);
  const { data, isLoading, isError, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useIdeas(query);

  const items = useMemo(() => data?.pages.flatMap((page) => page.items ?? []) ?? [], [data]);
  const { data: tagCounts } = useTags();
  const selection = useExternalStore(compareSelectionStore);

  const categories = useMemo(() => {
    const found = new Set<string>();
    for (const idea of items) if (idea.category) found.add(idea.category);
    return [...found].sort((a, b) => a.localeCompare(b));
  }, [items]);

  const tagOptions = useMemo(() => {
    const counts = tagCounts ?? [];
    const names = [...counts]
      .sort((a, b) => b.count - a.count)
      .slice(0, 8)
      .map((tag) => tag.name);
    if (filters.tag && !names.includes(filters.tag)) names.push(filters.tag);
    return names.map((name) => ({
      name,
      count: counts.find((tag) => tag.name === name)?.count ?? 0,
    }));
  }, [tagCounts, filters.tag]);

  const groups = useMemo(
    () =>
      STATUS_OPTIONS.map((option) => ({
        status: option.value,
        label: option.label,
        items: items.filter((idea) => idea.status === option.value),
      })),
    [items],
  );

  const orderedItems = useMemo(
    () => (filters.view === "board" ? groups.flatMap((group) => group.items) : items),
    [filters.view, groups, items],
  );

  const indexById = useMemo(() => {
    const map = new Map<string, number>();
    orderedItems.forEach((idea, index) => map.set(idea.id, index));
    return map;
  }, [orderedItems]);

  useEffect(() => {
    orderedLengthRef.current = orderedItems.length;
  }, [orderedItems.length]);

  useEffect(() => {
    if (focusIndex < 0) return;
    itemLinkRefs.current[focusIndex]?.focus();
  }, [focusIndex]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isEditableTarget(event.target)) return;
      if (event.key === "/") {
        event.preventDefault();
        searchInputRef.current?.focus();
        return;
      }
      if (event.key === "n") {
        event.preventDefault();
        router.push("/");
        return;
      }
      if (event.key === "j" || event.key === "k") {
        event.preventDefault();
        setFocusIndex((current) =>
          nextSelectedIndex(current, event.key === "j" ? 1 : -1, orderedLengthRef.current),
        );
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);

  const handleToggleCompare = useCallback((id: string) => toggleCompareSelection(id), []);

  function cardFor(idea: IdeaSummary) {
    const index = indexById.get(idea.id) ?? -1;
    return (
      <li key={idea.id}>
        <IdeaCard
          idea={idea}
          keyboardSelected={index === focusIndex}
          compareSelected={selection.includes(idea.id)}
          compareDisabled={
            selection.length >= MAX_COMPARE_SELECTION && !selection.includes(idea.id)
          }
          onToggleCompare={handleToggleCompare}
          linkRef={(node) => {
            if (index >= 0) itemLinkRefs.current[index] = node;
          }}
        />
      </li>
    );
  }

  return (
    <div className="pb-24">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Library</h1>
        {!isLoading && !isError ? (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {items.length}
            {hasNextPage ? "+" : ""} {items.length === 1 ? "idea" : "ideas"}
          </p>
        ) : null}
      </div>

      <LibraryToolbar
        filters={filters}
        queryInput={queryInput}
        onQueryInputChange={setQueryInput}
        searchInputRef={searchInputRef}
        onChange={applyFilters}
        categories={categories}
        tags={tagOptions}
      />

      {isLoading ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : null}

      {isError ? (
        <Card className="mt-6">
          <CardContent className="flex flex-col items-start gap-3 p-6">
            <p className="text-sm text-muted-foreground">
              Could not load ideas. Is the API running?
            </p>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Try again
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !isError && items.length === 0 ? (
        <Card className="mt-6">
          <CardContent className="flex flex-col items-start gap-4 p-8">
            <p className="text-sm text-muted-foreground">
              No ideas match — create one from this query
            </p>
            <Button asChild>
              <Link href={filters.q ? `/?q=${encodeURIComponent(filters.q)}` : "/"}>New idea</Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !isError && items.length > 0 && filters.view === "list" ? (
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orderedItems.map(cardFor)}
        </ul>
      ) : null}

      {!isLoading && !isError && items.length > 0 && filters.view === "board" ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((group) => (
            <section
              key={group.status}
              aria-label={`${group.label} ideas`}
              className="rounded-xl border border-border bg-muted/40 p-3"
            >
              <h2 className="px-1 pb-2 text-sm font-medium text-muted-foreground">
                {group.label} <span className="tabular-nums">({group.items.length})</span>
              </h2>
              {group.items.length === 0 ? (
                <p className="px-1 pb-2 text-xs text-muted-foreground">None</p>
              ) : (
                <ul className="flex flex-col gap-3">{group.items.map(cardFor)}</ul>
              )}
            </section>
          ))}
        </div>
      ) : null}

      {hasNextPage ? (
        <div className="mt-8 flex justify-center">
          <Button
            variant="outline"
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? (
              <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : null}
            Load more
          </Button>
        </div>
      ) : null}

      <CompareBar selectedIds={selection} />
    </div>
  );
}
