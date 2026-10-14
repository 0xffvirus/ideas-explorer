import { describe, expect, it } from "vitest";
import {
  DEFAULT_FILTERS,
  filtersToParams,
  hasActiveFilters,
  parseFilters,
  toApiParams,
} from "./library-params";

describe("parseFilters", () => {
  it("returns defaults for empty params", () => {
    expect(parseFilters(new URLSearchParams())).toEqual(DEFAULT_FILTERS);
  });

  it("parses a full filter set", () => {
    const params = new URLSearchParams(
      "q=pets&mode=semantic&status=done&verdict=pursue&category=marketplace&tag=ai&min_score=40&max_score=90&sort=score&view=board&archived=true&sel=a,b,c,d",
    );
    const filters = parseFilters(params);
    expect(filters).toMatchObject({
      q: "pets",
      mode: "semantic",
      status: "done",
      verdict: "pursue",
      category: "marketplace",
      tag: "ai",
      minScore: 40,
      maxScore: 90,
      sort: "score",
      view: "board",
      archived: true,
    });
    expect(filters.selected).toHaveLength(3);
  });

  it("falls back for invalid enum values and numbers", () => {
    const filters = parseFilters(new URLSearchParams("mode=bogus&sort=weird&min_score=abc"));
    expect(filters.mode).toBe("hybrid");
    expect(filters.sort).toBe("recent");
    expect(filters.minScore).toBeNull();
  });
});

describe("filtersToParams", () => {
  it("omits defaults and keeps meaningful values", () => {
    const params = filtersToParams({
      ...DEFAULT_FILTERS,
      q: "pets",
      status: "done",
      view: "board",
      minScore: 30,
      selected: ["a", "b"],
    });
    expect(params.get("q")).toBe("pets");
    expect(params.get("status")).toBe("done");
    expect(params.get("view")).toBe("board");
    expect(params.get("min_score")).toBe("30");
    expect(params.get("sel")).toBe("a,b");
    expect(params.get("mode")).toBeNull();
    expect(params.get("sort")).toBeNull();
    expect(params.get("archived")).toBeNull();
  });

  it("preserves unrelated params such as tab", () => {
    const params = filtersToParams(
      { ...DEFAULT_FILTERS, q: "x" },
      new URLSearchParams("tab=market"),
    );
    expect(params.get("tab")).toBe("market");
    expect(params.get("q")).toBe("x");
  });

  it("round-trips through parse", () => {
    const source = {
      ...DEFAULT_FILTERS,
      q: "invoice",
      mode: "keyword" as const,
      verdict: "refine" as const,
      maxScore: 60,
      sort: "title" as const,
      archived: true,
    };
    expect(parseFilters(filtersToParams(source))).toEqual(source);
  });
});

describe("toApiParams", () => {
  it("drops the mode when there is no query", () => {
    const api = toApiParams({ ...DEFAULT_FILTERS, mode: "semantic" });
    expect(api.mode).toBeUndefined();
    expect(api.limit).toBe(30);
  });

  it("maps camelCase filters to snake_case query params", () => {
    const api = toApiParams({ ...DEFAULT_FILTERS, q: "pets", minScore: 20, maxScore: 80 });
    expect(api).toMatchObject({ q: "pets", min_score: 20, max_score: 80, mode: "hybrid" });
  });
});

describe("hasActiveFilters", () => {
  it("is false only for the default set", () => {
    expect(hasActiveFilters(DEFAULT_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...DEFAULT_FILTERS, q: "x" })).toBe(true);
    expect(hasActiveFilters({ ...DEFAULT_FILTERS, archived: true })).toBe(true);
    expect(hasActiveFilters({ ...DEFAULT_FILTERS, view: "board" })).toBe(false);
  });
});
