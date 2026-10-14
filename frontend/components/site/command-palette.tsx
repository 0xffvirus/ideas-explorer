"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { useIdeas } from "@/lib/api/hooks";
import type { IdeaSummary } from "@/lib/api/types";

const RECENT_SEARCHES_KEY = "idea-forge.recent-searches.v1";
const MAX_RECENT_SEARCHES = 5;

function readRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function rememberSearch(query: string): void {
  const trimmed = query.trim();
  if (!trimmed) return;
  const next = [trimmed, ...readRecentSearches().filter((item) => item !== trimmed)].slice(
    0,
    MAX_RECENT_SEARCHES,
  );
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next));
  } catch {
    // storage may be unavailable; recent searches are best-effort
  }
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [selectedFromUrl, setSelectedFromUrl] = useState<string[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 200);
    return () => clearTimeout(timer);
  }, [query]);

  // Reset dialog-local state when it opens (guarded render-phase update).
  const [wasOpen, setWasOpen] = useState(false);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setQuery("");
      setDebounced("");
      setSelectedFromUrl(
        (new URLSearchParams(window.location.search).get("sel") ?? "").split(",").filter(Boolean),
      );
      setRecentSearches(readRecentSearches());
    }
  }

  const searching = debounced.trim().length > 0;
  const searchQuery = useIdeas({ q: debounced, limit: 8 }, { enabled: open && searching });
  const recentQuery = useIdeas({ sort: "recent", limit: 5 }, { enabled: open && !searching });

  const results: IdeaSummary[] = useMemo(() => {
    const pages = searchQuery.data?.pages ?? [];
    return pages.flatMap((page) => page.items).slice(0, 8);
  }, [searchQuery.data]);

  const recents: IdeaSummary[] = useMemo(() => {
    const pages = recentQuery.data?.pages ?? [];
    return pages.flatMap((page) => page.items).slice(0, 5);
  }, [recentQuery.data]);

  function go(href: string) {
    onOpenChange(false);
    router.push(href as Route);
  }

  function openIdea(idea: IdeaSummary) {
    if (searching) rememberSearch(debounced);
    go(`/ideas/${idea.id}`);
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      description="Jump to an idea, search by meaning, or run an action"
      className="sm:max-w-xl"
      data-testid="command-palette"
    >
      <Command className="**:data-[slot=command-input-wrapper]:p-0">
        <CommandInput
          value={query}
          onValueChange={setQuery}
          placeholder="Jump to an idea or type a command…"
          aria-label="Command palette search"
        />
        <CommandList>
          <CommandEmpty>
            {searchQuery.isPending && searching ? "Searching…" : "Nothing found."}
          </CommandEmpty>

          {searching && results.length > 0 && (
            <CommandGroup heading="Ideas">
              {results.map((idea) => (
                <CommandItem
                  key={idea.id}
                  value={`${idea.title} ${idea.id}`}
                  onSelect={() => openIdea(idea)}
                >
                  <span className="truncate">{idea.title}</span>
                  <CommandShortcut>
                    {idea.verdict ?? idea.status}
                    {idea.overall_score != null ? ` · ${Math.round(idea.overall_score)}` : ""}
                  </CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {searching && (
            <CommandGroup heading="Search">
              <CommandItem
                value={`search library ${query}`}
                onSelect={() => {
                  rememberSearch(debounced);
                  setRecentSearches(readRecentSearches());
                  go(`/ideas?q=${encodeURIComponent(debounced.trim())}`);
                }}
              >
                Search the library for “{debounced.trim()}”
              </CommandItem>
            </CommandGroup>
          )}

          {!searching && recents.length > 0 && (
            <CommandGroup heading="Recent ideas">
              {recents.map((idea) => (
                <CommandItem key={idea.id} value={idea.title} onSelect={() => openIdea(idea)}>
                  <span className="truncate">{idea.title}</span>
                  <CommandShortcut>{idea.status}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          <div className="-mx-1 my-1 h-px bg-border" aria-hidden="true" />

          <CommandGroup heading="Actions">
            <CommandItem value="new idea" onSelect={() => go("/")}>
              New idea
              <CommandShortcut>n</CommandShortcut>
            </CommandItem>
            <CommandItem value="open library" onSelect={() => go("/ideas")}>
              Open library
              <CommandShortcut>/</CommandShortcut>
            </CommandItem>
            {selectedFromUrl.length >= 2 && (
              <CommandItem
                value="compare selected"
                onSelect={() => go(`/compare?ids=${selectedFromUrl.join(",")}`)}
              >
                Compare selected ({selectedFromUrl.length})
              </CommandItem>
            )}
          </CommandGroup>

          {!searching && recentSearches.length > 0 && (
            <CommandGroup heading="Recent searches">
              {recentSearches.map((item) => (
                <CommandItem
                  key={item}
                  value={`recent ${item}`}
                  onSelect={() => go(`/ideas?q=${encodeURIComponent(item)}`)}
                >
                  <span className="truncate">{item}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
