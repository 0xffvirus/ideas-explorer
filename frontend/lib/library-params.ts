import type { ListIdeasParams, SearchMode, Sort } from "@/lib/api/types";

export type LibraryFilters = {
  q: string;
  mode: SearchMode;
  status: string | null;
  verdict: string | null;
  category: string | null;
  tag: string | null;
  minScore: number | null;
  maxScore: number | null;
  sort: Sort;
  view: "list" | "board";
  archived: boolean;
  selected: string[];
};

export const DEFAULT_FILTERS: LibraryFilters = {
  q: "",
  mode: "hybrid",
  status: null,
  verdict: null,
  category: null,
  tag: null,
  minScore: null,
  maxScore: null,
  sort: "recent",
  view: "list",
  archived: false,
  selected: [],
};

const MODES: SearchMode[] = ["hybrid", "keyword", "semantic"];
const SORTS: Sort[] = ["recent", "score", "title"];

function numberOrNull(value: string | null): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseFilters(params: URLSearchParams): LibraryFilters {
  const mode = params.get("mode");
  const sort = params.get("sort");
  return {
    q: params.get("q") ?? "",
    mode: MODES.includes(mode as SearchMode) ? (mode as SearchMode) : "hybrid",
    status: params.get("status"),
    verdict: params.get("verdict"),
    category: params.get("category"),
    tag: params.get("tag"),
    minScore: numberOrNull(params.get("min_score")),
    maxScore: numberOrNull(params.get("max_score")),
    sort: SORTS.includes(sort as Sort) ? (sort as Sort) : "recent",
    view: params.get("view") === "board" ? "board" : "list",
    archived: params.get("archived") === "true",
    selected: (params.get("sel") ?? "").split(",").filter(Boolean).slice(0, 3),
  };
}

export function filtersToParams(
  filters: LibraryFilters,
  current?: URLSearchParams,
): URLSearchParams {
  const params = new URLSearchParams(current);
  for (const key of [
    "q",
    "mode",
    "status",
    "verdict",
    "category",
    "tag",
    "min_score",
    "max_score",
    "sort",
    "view",
    "archived",
    "sel",
  ]) {
    params.delete(key);
  }
  if (filters.q) params.set("q", filters.q);
  if (filters.mode !== "hybrid") params.set("mode", filters.mode);
  if (filters.status) params.set("status", filters.status);
  if (filters.verdict) params.set("verdict", filters.verdict);
  if (filters.category) params.set("category", filters.category);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.minScore != null) params.set("min_score", String(filters.minScore));
  if (filters.maxScore != null) params.set("max_score", String(filters.maxScore));
  if (filters.sort !== "recent") params.set("sort", filters.sort);
  if (filters.view !== "list") params.set("view", filters.view);
  if (filters.archived) params.set("archived", "true");
  if (filters.selected.length > 0) params.set("sel", filters.selected.join(","));
  return params;
}

export function toApiParams(filters: LibraryFilters, limit = 30): ListIdeasParams {
  return {
    q: filters.q || undefined,
    mode: filters.q ? filters.mode : undefined,
    status: (filters.status as ListIdeasParams["status"]) ?? undefined,
    verdict: (filters.verdict as ListIdeasParams["verdict"]) ?? undefined,
    category: filters.category ?? undefined,
    tag: filters.tag ?? undefined,
    min_score: filters.minScore ?? undefined,
    max_score: filters.maxScore ?? undefined,
    sort: filters.sort,
    archived: filters.archived,
    limit,
  };
}

export function hasActiveFilters(filters: LibraryFilters): boolean {
  return Boolean(
    filters.q ||
    filters.status ||
    filters.verdict ||
    filters.category ||
    filters.tag ||
    filters.minScore != null ||
    filters.maxScore != null ||
    filters.archived,
  );
}
