import type { IdeasQuery } from "@/lib/api/types";
import type { IdeaStatus, IdeaVerdict, SearchMode, SortField } from "@/lib/api/types";

export type LibraryView = "list" | "board";

/**
 * The Library's complete filter state. It round-trips through the URL query
 * string so bookmarks, back and forward restore exactly what the user saw.
 */
export interface LibraryFilters {
  q: string;
  mode: SearchMode;
  status: IdeaStatus | null;
  verdict: IdeaVerdict | null;
  category: string | null;
  tag: string | null;
  scoreMin: number | null;
  scoreMax: number | null;
  sort: SortField;
  view: LibraryView;
}

export const LIBRARY_PAGE_SIZE = 30;
export const SEARCH_DEBOUNCE_MS = 200;

/** Overall scores are on a 0–100 scale (dimension scores are 1–5). */
export const SCORE_FILTER_MIN = 0;
export const SCORE_FILTER_MAX = 100;

export const DEFAULT_LIBRARY_FILTERS: LibraryFilters = {
  q: "",
  mode: "hybrid",
  status: null,
  verdict: null,
  category: null,
  tag: null,
  scoreMin: null,
  scoreMax: null,
  sort: "recent",
  view: "list",
};

export const STATUS_OPTIONS: ReadonlyArray<{ value: IdeaStatus; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "queued", label: "Queued" },
  { value: "analyzing", label: "Analyzing" },
  { value: "done", label: "Done" },
  { value: "failed", label: "Failed" },
];

export const VERDICT_OPTIONS: ReadonlyArray<{ value: IdeaVerdict; label: string }> = [
  { value: "pursue", label: "Pursue" },
  { value: "refine", label: "Refine" },
  { value: "park", label: "Park" },
];

export const MODE_OPTIONS: ReadonlyArray<{ value: SearchMode; label: string }> = [
  { value: "hybrid", label: "Hybrid" },
  { value: "keyword", label: "Keyword" },
  { value: "semantic", label: "Semantic" },
];

export const SORT_OPTIONS: ReadonlyArray<{ value: SortField; label: string }> = [
  { value: "recent", label: "Recent" },
  { value: "score", label: "Score" },
  { value: "title", label: "Title" },
];

/** Minimal reader interface satisfied by both `URLSearchParams` and Next's readonly variant. */
export interface SearchParamsReader {
  get(name: string): string | null;
}

function isOneOf<T extends string>(value: string | null, allowed: readonly T[]): value is T {
  return value !== null && (allowed as readonly string[]).includes(value);
}

function trimmedOrNull(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed === "" ? null : trimmed;
}

function parseScore(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.min(Math.max(parsed, SCORE_FILTER_MIN), SCORE_FILTER_MAX);
}

const STATUS_VALUES = STATUS_OPTIONS.map((option) => option.value);
const VERDICT_VALUES = VERDICT_OPTIONS.map((option) => option.value);
const MODE_VALUES = MODE_OPTIONS.map((option) => option.value);
const SORT_VALUES = SORT_OPTIONS.map((option) => option.value);

/** Parse URL search params into filters, ignoring invalid values. */
export function parseLibraryFilters(params: SearchParamsReader): LibraryFilters {
  const mode = params.get("mode");
  const status = params.get("status");
  const verdict = params.get("verdict");
  const sort = params.get("sort");
  const view = params.get("view");
  return {
    q: params.get("q")?.trim() ?? "",
    mode: isOneOf(mode, MODE_VALUES) ? mode : DEFAULT_LIBRARY_FILTERS.mode,
    status: isOneOf(status, STATUS_VALUES) ? status : null,
    verdict: isOneOf(verdict, VERDICT_VALUES) ? verdict : null,
    category: trimmedOrNull(params.get("category")),
    tag: trimmedOrNull(params.get("tag")),
    scoreMin: parseScore(params.get("score_min")),
    scoreMax: parseScore(params.get("score_max")),
    sort: isOneOf(sort, SORT_VALUES) ? sort : DEFAULT_LIBRARY_FILTERS.sort,
    view: view === "board" ? "board" : "list",
  };
}

/** Serialize filters, omitting defaults so URLs stay short. */
export function libraryFiltersToSearchParams(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q.trim() !== "") params.set("q", filters.q.trim());
  if (filters.mode !== DEFAULT_LIBRARY_FILTERS.mode) params.set("mode", filters.mode);
  if (filters.status) params.set("status", filters.status);
  if (filters.verdict) params.set("verdict", filters.verdict);
  if (filters.category) params.set("category", filters.category);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.scoreMin !== null) params.set("score_min", String(filters.scoreMin));
  if (filters.scoreMax !== null) params.set("score_max", String(filters.scoreMax));
  if (filters.sort !== DEFAULT_LIBRARY_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.view !== DEFAULT_LIBRARY_FILTERS.view) params.set("view", filters.view);
  return params;
}

/** Map Library filters onto the API's `GET /ideas` query parameters. */
export function toIdeaQuery(
  filters: LibraryFilters,
  options: { cursor?: string | null; limit?: number } = {},
): IdeasQuery {
  const query: IdeasQuery = { sort: filters.sort, limit: options.limit ?? LIBRARY_PAGE_SIZE };
  if (filters.q.trim() !== "") {
    query.q = filters.q.trim();
    query.mode = filters.mode;
  }
  if (filters.status) query.status = filters.status;
  if (filters.verdict) query.verdict = filters.verdict;
  if (filters.category) query.category = filters.category;
  if (filters.tag) query.tag = filters.tag;
  if (filters.scoreMin !== null) query.score_min = filters.scoreMin;
  if (filters.scoreMax !== null) query.score_max = filters.scoreMax;
  if (options.cursor) query.cursor = options.cursor;
  return query;
}

/** Count of filters beyond the search query itself (used for a "clear" affordance). */
export function activeFilterCount(filters: LibraryFilters): number {
  let count = 0;
  if (filters.status) count += 1;
  if (filters.verdict) count += 1;
  if (filters.category) count += 1;
  if (filters.tag) count += 1;
  if (filters.scoreMin !== null || filters.scoreMax !== null) count += 1;
  return count;
}
