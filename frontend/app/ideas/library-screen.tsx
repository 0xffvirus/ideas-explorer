"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FilterBar } from "@/components/ideas/filter-bar";
import { IdeaBoard } from "@/components/ideas/idea-board";
import { IdeaList } from "@/components/ideas/idea-list";
import { SearchBar } from "@/components/ideas/search-bar";
import { SelectionBar } from "@/components/ideas/selection-bar";
import { useIdeas, useTags } from "@/lib/api/hooks";
import {
  DEFAULT_FILTERS,
  filtersToParams,
  hasActiveFilters,
  parseFilters,
  toApiParams,
  type LibraryFilters,
} from "@/lib/library-params";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

export function LibraryScreen() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters = useMemo(
    () => parseFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  const [qInput, setQInput] = useState(filters.q);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Keep the input in sync with the URL (back/forward, cleared links).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setQInput(filters.q);
  }, [filters.q]);

  const update = useCallback(
    (patch: Partial<LibraryFilters>, options?: { replace?: boolean }) => {
      const next = { ...filters, ...patch };
      const params = filtersToParams(next, new URLSearchParams(searchParams.toString()));
      const href = `${pathname}?${params.toString()}` as Route;
      // Filter changes create history entries so back/forward restore them;
      // debounced typing and selection updates replace instead.
      if (options?.replace) router.replace(href, { scroll: false });
      else router.push(href, { scroll: false });
    },
    [filters, pathname, router, searchParams],
  );

  // Debounced search: 200 ms, then push into the URL.
  useEffect(() => {
    if (qInput === filters.q) return;
    const timer = setTimeout(() => update({ q: qInput }, { replace: true }), 200);
    return () => clearTimeout(timer);
  }, [qInput, filters.q, update]);

  const apiParams = useMemo(() => toApiParams(filters), [filters]);
  const query = useIdeas(apiParams);
  const tagsQuery = useTags();

  const items = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  const matchMode = query.data?.pages[0]?.mode ?? null;
  const totalLoaded = items.length;

  const toggleSelected = useCallback(
    (id: string) => {
      const selected = filters.selected.includes(id)
        ? filters.selected.filter((value) => value !== id)
        : [...filters.selected, id].slice(0, 3);
      update({ selected }, { replace: true });
    },
    [filters.selected, update],
  );

  // j/k roving focus through results, / focuses search.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "/" && !isTypingTarget(event.target)) {
        event.preventDefault();
        searchInputRef.current?.focus();
        return;
      }
      if (event.key !== "j" && event.key !== "k") return;
      if (isTypingTarget(event.target)) return;
      const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("[data-idea-link]"));
      if (links.length === 0) return;
      event.preventDefault();
      const current = links.findIndex((link) => link === document.activeElement);
      const delta = event.key === "j" ? 1 : -1;
      const next =
        current === -1
          ? delta === 1
            ? 0
            : links.length - 1
          : Math.min(Math.max(current + delta, 0), links.length - 1);
      links[next]?.focus();
      links[next]?.scrollIntoView({ block: "nearest" });
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const emptyDraftHref = filters.q ? (`/?draft=${encodeURIComponent(filters.q)}` as Route) : null;

  return (
    <div className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24">
      <header className="section-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="t-section">Library</h1>
          <p className="t-meta" data-testid="result-count" aria-live="polite">
            {query.isPending ? "Loading…" : `${totalLoaded} idea${totalLoaded === 1 ? "" : "s"}`}
            {query.hasNextPage ? "+" : ""}
          </p>
        </div>
        <SearchBar
          value={qInput}
          onValueChange={setQInput}
          mode={filters.mode}
          onModeChange={(mode) => update({ mode })}
          activeMatch={matchMode}
          inputRef={searchInputRef}
        />
        <FilterBar
          filters={filters}
          onChange={update}
          onClearAll={() => update({ ...DEFAULT_FILTERS, q: filters.q, mode: filters.mode })}
          tags={tagsQuery.data?.items ?? []}
        />
      </header>

      <div aria-busy={query.isFetching} data-testid="library-results">
        {query.isPending && (
          <div className="grid gap-3" aria-label="Loading ideas">
            {[0, 1, 2, 3, 4].map((index) => (
              <div key={index} className="h-20 animate-pulse rounded-card bg-surface-subtle" />
            ))}
          </div>
        )}

        {query.isError && (
          <p className="t-body" role="alert">
            Could not load ideas.{" "}
            <button
              type="button"
              className="link cursor-pointer"
              onClick={() => void query.refetch()}
            >
              Retry
            </button>
          </p>
        )}

        {!query.isPending && !query.isError && items.length === 0 && (
          <div className="rounded-card border border-line bg-surface p-10 text-center">
            <h2 className="t-card">
              {filters.q
                ? "No ideas match this search"
                : hasActiveFilters(filters)
                  ? "No ideas match these filters"
                  : "No ideas here yet"}
            </h2>
            <p className="t-body mt-2">
              {filters.q
                ? "Try a broader phrase, a different mode, or turn it into a new idea."
                : hasActiveFilters(filters)
                  ? "Loosen or clear the filters to see more."
                  : "Start with a one-paragraph description on the home page."}
            </p>
            <div className="mt-6 flex justify-center gap-3">
              {emptyDraftHref && (
                <Button asChild className="rounded-pill font-bold">
                  <Link href={emptyDraftHref}>Create an idea from “{filters.q}”</Link>
                </Button>
              )}
              {hasActiveFilters(filters) && (
                <Button
                  variant="outline"
                  onClick={() => update({ ...DEFAULT_FILTERS })}
                  className="rounded-pill font-bold"
                >
                  Clear filters
                </Button>
              )}
            </div>
          </div>
        )}

        {items.length > 0 &&
          (filters.view === "board" ? (
            <IdeaBoard
              items={items}
              selected={filters.selected}
              onToggleSelected={toggleSelected}
            />
          ) : (
            <IdeaList items={items} selected={filters.selected} onToggleSelected={toggleSelected} />
          ))}

        {query.hasNextPage && items.length > 0 && (
          <div className="mt-8 flex justify-center">
            <Button
              variant="outline"
              onClick={() => void query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
              className="min-h-12 rounded-pill px-6 font-bold"
              data-testid="load-more"
            >
              {query.isFetchingNextPage ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" /> Loading…
                </>
              ) : (
                "Load more"
              )}
            </Button>
          </div>
        )}
      </div>

      <SelectionBar
        items={items}
        selected={filters.selected}
        onClear={() => update({ selected: [] })}
        onCompare={() => router.push(`/compare?ids=${filters.selected.join(",")}` as Route)}
      />
    </div>
  );
}
