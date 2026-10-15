import { describe, expect, it } from "vitest";

import {
  activeFilterCount,
  DEFAULT_LIBRARY_FILTERS,
  libraryFiltersToSearchParams,
  parseLibraryFilters,
  toIdeaQuery,
  type LibraryFilters,
} from "@/lib/library-filters";

const full: LibraryFilters = {
  q: "pets for renters",
  mode: "semantic",
  status: "done",
  verdict: "pursue",
  category: "Consumer",
  tag: "pets",
  scoreMin: 30,
  scoreMax: 90,
  sort: "score",
  view: "board",
};

describe("library filter URL round trip", () => {
  it("restores every field through the query string", () => {
    const params = libraryFiltersToSearchParams(full);
    expect(parseLibraryFilters(params)).toEqual(full);
  });

  it("restores defaults from an empty query string", () => {
    expect(parseLibraryFilters(new URLSearchParams())).toEqual(DEFAULT_LIBRARY_FILTERS);
  });

  it("omits defaults from the URL", () => {
    const params = libraryFiltersToSearchParams(DEFAULT_LIBRARY_FILTERS);
    expect(params.toString()).toBe("");
  });

  it("survives a second round trip (idempotent)", () => {
    const once = libraryFiltersToSearchParams(full).toString();
    const twice = libraryFiltersToSearchParams(
      parseLibraryFilters(new URLSearchParams(once)),
    ).toString();
    expect(twice).toBe(once);
  });

  it("ignores invalid enum values and malformed numbers", () => {
    const parsed = parseLibraryFilters(
      new URLSearchParams({
        mode: "banana",
        status: "nope",
        verdict: "maybe",
        sort: "chaos",
        view: "grid",
        score_min: "abc",
        score_max: "45",
      }),
    );
    expect(parsed.mode).toBe("hybrid");
    expect(parsed.status).toBeNull();
    expect(parsed.verdict).toBeNull();
    expect(parsed.sort).toBe("recent");
    expect(parsed.view).toBe("list");
    expect(parsed.scoreMin).toBeNull();
    expect(parsed.scoreMax).toBe(45);
  });

  it("round-trips the full 0-100 score range", () => {
    const params = new URLSearchParams({ score_min: "0", score_max: "100" });
    const parsed = parseLibraryFilters(params);
    expect(parsed.scoreMin).toBe(0);
    expect(parsed.scoreMax).toBe(100);
    expect(
      libraryFiltersToSearchParams({ ...DEFAULT_LIBRARY_FILTERS, ...parsed }).toString(),
    ).toBe("score_min=0&score_max=100");
  });

  it("clamps out-of-range scores to 0-100 instead of dropping them", () => {
    const parsed = parseLibraryFilters(
      new URLSearchParams({ score_min: "-10", score_max: "150" }),
    );
    expect(parsed.scoreMin).toBe(0);
    expect(parsed.scoreMax).toBe(100);
  });

  it("trims query string values", () => {
    const parsed = parseLibraryFilters(new URLSearchParams({ q: "  pets  ", tag: "  cats " }));
    expect(parsed.q).toBe("pets");
    expect(parsed.tag).toBe("cats");
  });
});

describe("toIdeaQuery", () => {
  it("maps filters onto API parameters and includes mode only with a query", () => {
    expect(toIdeaQuery(full)).toEqual({
      q: "pets for renters",
      mode: "semantic",
      status: "done",
      verdict: "pursue",
      category: "Consumer",
      tag: "pets",
      score_min: 30,
      score_max: 90,
      sort: "score",
      limit: 30,
    });

    const withoutQuery = toIdeaQuery(DEFAULT_LIBRARY_FILTERS);
    expect(withoutQuery).toEqual({ sort: "recent", limit: 30 });
    expect("mode" in withoutQuery).toBe(false);
  });

  it("passes cursor and a custom limit through", () => {
    expect(toIdeaQuery(full, { cursor: "offset:30", limit: 10 })).toMatchObject({
      cursor: "offset:30",
      limit: 10,
    });
  });
});

describe("activeFilterCount", () => {
  it("counts filters beyond the search query", () => {
    expect(activeFilterCount(DEFAULT_LIBRARY_FILTERS)).toBe(0);
    expect(activeFilterCount({ ...DEFAULT_LIBRARY_FILTERS, q: "pets" })).toBe(0);
    expect(activeFilterCount(full)).toBe(5);
  });
});
