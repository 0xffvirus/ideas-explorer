import { describe, expect, it } from "vitest";

import { isEditableTarget, nextSelectedIndex } from "@/lib/keyboard";

describe("nextSelectedIndex", () => {
  it("selects the first item when moving forward from nothing", () => {
    expect(nextSelectedIndex(-1, 1, 3)).toBe(0);
  });

  it("selects the last item when moving backward from nothing", () => {
    expect(nextSelectedIndex(-1, -1, 3)).toBe(2);
  });

  it("moves through the list", () => {
    expect(nextSelectedIndex(0, 1, 3)).toBe(1);
    expect(nextSelectedIndex(1, 1, 3)).toBe(2);
    expect(nextSelectedIndex(2, -1, 3)).toBe(1);
  });

  it("wraps around in both directions", () => {
    expect(nextSelectedIndex(2, 1, 3)).toBe(0);
    expect(nextSelectedIndex(0, -1, 3)).toBe(2);
  });

  it("returns -1 for an empty list", () => {
    expect(nextSelectedIndex(-1, 1, 0)).toBe(-1);
    expect(nextSelectedIndex(4, -1, 0)).toBe(-1);
  });

  it("clamps an out-of-range index", () => {
    expect(nextSelectedIndex(9, 1, 3)).toBe(0);
    expect(nextSelectedIndex(9, -1, 3)).toBe(2);
  });
});

describe("isEditableTarget", () => {
  it("recognizes text-entry surfaces", () => {
    expect(isEditableTarget(document.createElement("input"))).toBe(true);
    expect(isEditableTarget(document.createElement("textarea"))).toBe(true);
    expect(isEditableTarget(document.createElement("select"))).toBe(true);
    expect(isEditableTarget(document.createElement("div"))).toBe(false);
    expect(isEditableTarget(null)).toBe(false);
  });
});
