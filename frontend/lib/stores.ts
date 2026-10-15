"use client";

import { createLocalStorageStore } from "@/lib/local-storage-store";

export interface IntakeDraft {
  raw_input: string;
  context: {
    target_region: string;
    audience_hint: string;
    budget_hint: string;
  };
}

export const EMPTY_INTAKE_DRAFT: IntakeDraft = {
  raw_input: "",
  context: { target_region: "", audience_hint: "", budget_hint: "" },
};

function parseDraft(value: unknown): IntakeDraft {
  if (typeof value !== "object" || value === null) return EMPTY_INTAKE_DRAFT;
  const record = value as Record<string, unknown>;
  const context =
    typeof record.context === "object" && record.context !== null
      ? (record.context as Record<string, unknown>)
      : {};
  const read = (source: Record<string, unknown>, key: string) =>
    typeof source[key] === "string" ? (source[key] as string) : "";
  return {
    raw_input: read(record, "raw_input"),
    context: {
      target_region: read(context, "target_region"),
      audience_hint: read(context, "audience_hint"),
      budget_hint: read(context, "budget_hint"),
    },
  };
}

/** Intake draft survives reloads; cleared after a successful submit. */
export const intakeDraftStore = createLocalStorageStore<IntakeDraft>({
  key: "idea-forge:intake-draft",
  fallback: EMPTY_INTAKE_DRAFT,
  parse: parseDraft,
});

export const MAX_RECENT_SEARCHES = 5;

function parseStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

/** Recent command-palette searches, newest first, max 5. */
export const recentSearchesStore = createLocalStorageStore<string[]>({
  key: "idea-forge:recent-searches",
  fallback: [],
  parse: (value) => parseStringList(value).slice(0, MAX_RECENT_SEARCHES),
});

export function recordRecentSearch(query: string): void {
  const trimmed = query.trim();
  if (trimmed === "") return;
  const current = recentSearchesStore.getSnapshot();
  const next = [trimmed, ...current.filter((item) => item !== trimmed)].slice(
    0,
    MAX_RECENT_SEARCHES,
  );
  recentSearchesStore.set(next);
}

export const MAX_COMPARE_SELECTION = 3;

/** Ideas selected for comparison (2-3), shared between Library and palette. */
export const compareSelectionStore = createLocalStorageStore<string[]>({
  key: "idea-forge:compare-selection",
  fallback: [],
  parse: (value) => parseStringList(value).slice(0, MAX_COMPARE_SELECTION),
});

export function toggleCompareSelection(id: string): void {
  const current = compareSelectionStore.getSnapshot();
  if (current.includes(id)) {
    compareSelectionStore.set(current.filter((item) => item !== id));
    return;
  }
  if (current.length >= MAX_COMPARE_SELECTION) return;
  compareSelectionStore.set([...current, id]);
}

export function clearCompareSelection(): void {
  compareSelectionStore.set([]);
}
