"use client";

import { Command } from "cmdk";
import { Clock, GitCompare, Library, Lightbulb, Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { useExternalStore } from "@/lib/local-storage-store";
import { useIdeas } from "@/lib/api/queries";
import {
  MAX_COMPARE_SELECTION,
  recentSearchesStore,
  recordRecentSearch,
  compareSelectionStore,
} from "@/lib/stores";
import { cn } from "@/lib/utils";

export const OPEN_COMMAND_PALETTE_EVENT = "idea-forge:open-command-palette";

/** Open the global command palette from anywhere (e.g. the header hint). */
export function openCommandPalette(): void {
  window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT));
}

const ITEM_CLASS =
  "flex cursor-default select-none items-center gap-2 rounded-md px-2 py-2 text-sm text-foreground data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground";
const GROUP_CLASS =
  "px-2 py-1.5 text-xs font-medium text-muted-foreground [&_[cmdk-group-heading]]:mb-1";

export function CommandPaletteTrigger() {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={openCommandPalette}
      className="text-muted-foreground"
      aria-label="Open command palette"
    >
      <Search aria-hidden="true" />
      <span className="hidden sm:inline">Search</span>
      <kbd className="hidden items-center gap-0.5 rounded border border-border px-1.5 py-0.5 font-sans text-[10px] text-muted-foreground sm:inline-flex">
        <span>⌘</span>
        <span>K</span>
      </kbd>
    </Button>
  );
}

export interface CommandPaletteProps {
  /** Test seam: render the palette already open. */
  defaultOpen?: boolean;
}

export function CommandPalette({ defaultOpen = false }: CommandPaletteProps) {
  const router = useRouter();
  const [open, setOpen] = useState(defaultOpen);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query.trim(), 150);

  const recentSearches = useExternalStore(recentSearchesStore);
  const selection = useExternalStore(compareSelectionStore);
  const canCompare = selection.length >= 2 && selection.length <= MAX_COMPARE_SELECTION;

  const { data, isFetching } = useIdeas(
    { q: debouncedQuery, mode: "hybrid", limit: 8 },
    { enabled: open && debouncedQuery.length > 0 },
  );
  const ideas = data?.pages.flatMap((page) => page.items ?? []) ?? [];

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    };
    const onOpen = () => setOpen(true);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpen);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpen);
    };
  }, []);

  function close() {
    setOpen(false);
    setQuery("");
  }

  function navigate(href: string) {
    close();
    router.push(href);
  }

  function selectIdea(id: string) {
    if (debouncedQuery) recordRecentSearch(debouncedQuery);
    navigate(`/ideas/${id}`);
  }

  const showIdeas = debouncedQuery.length > 0;
  const noResults = showIdeas && !isFetching && ideas.length === 0;

  return (
    <Command.Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setQuery("");
      }}
      label="Command palette"
      shouldFilter={false}
      loop
      overlayClassName="fixed inset-0 z-50 bg-black/50"
      contentClassName="fixed left-1/2 top-[12%] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-card shadow-2xl focus:outline-none"
      className="flex flex-col"
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          onKeyDown={(event) => {
            if (event.key === "Enter" && query.trim() !== "") recordRecentSearch(query);
          }}
          placeholder="Search ideas or run a command…"
          className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
      </div>
      <Command.List className="max-h-[60vh] overflow-y-auto p-2">
        {noResults ? (
          <Command.Empty className="px-2 py-8 text-center text-sm text-muted-foreground">
            No ideas found.
          </Command.Empty>
        ) : null}
        {!showIdeas ? (
          <>
            {recentSearches.length > 0 ? (
              <Command.Group heading="Recent searches" className={GROUP_CLASS}>
                {recentSearches.map((term) => (
                  <Command.Item
                    key={term}
                    value={`recent-${term}`}
                    onSelect={() => setQuery(term)}
                    className={ITEM_CLASS}
                  >
                    <Clock aria-hidden="true" />
                    {term}
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
            <Command.Group heading="Actions" className={GROUP_CLASS}>
              <Command.Item value="new-idea" onSelect={() => navigate("/")} className={ITEM_CLASS}>
                <Plus aria-hidden="true" />
                New idea
              </Command.Item>
              <Command.Item
                value="go-to-library"
                onSelect={() => navigate("/ideas")}
                className={ITEM_CLASS}
              >
                <Library aria-hidden="true" />
                Go to library
              </Command.Item>
              {canCompare ? (
                <Command.Item
                  value="compare-selected"
                  onSelect={() => navigate(`/compare?ids=${selection.join(",")}`)}
                  className={ITEM_CLASS}
                >
                  <GitCompare aria-hidden="true" />
                  Compare selected ({selection.length})
                </Command.Item>
              ) : null}
            </Command.Group>
          </>
        ) : (
          <Command.Group heading="Ideas" className={GROUP_CLASS}>
            {isFetching && ideas.length === 0 ? (
              <Command.Loading className="px-2 py-6 text-center text-sm text-muted-foreground">
                Searching…
              </Command.Loading>
            ) : null}
            {ideas.map((idea) => (
              <Command.Item
                key={idea.id}
                value={`idea-${idea.id}`}
                onSelect={() => selectIdea(idea.id)}
                className={cn(ITEM_CLASS, "justify-between")}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Lightbulb className="shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="truncate">{idea.title}</span>
                </span>
                <StatusBadge status={idea.status} />
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
      <div className="flex items-center gap-3 border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
        <span>
          <kbd className="font-sans">↑↓</kbd> navigate
        </span>
        <span>
          <kbd className="font-sans">↵</kbd> open
        </span>
        <span>
          <kbd className="font-sans">esc</kbd> close
        </span>
      </div>
    </Command.Dialog>
  );
}
