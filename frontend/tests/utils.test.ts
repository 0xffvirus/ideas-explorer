import { describe, expect, it } from "vitest";

import { cn, formatDate, formatDuration } from "@/lib/utils";

describe("cn", () => {
  it("joins class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("drops falsy values", () => {
    expect(cn("a", false, undefined, null, "", "b")).toBe("a b");
  });

  it("lets tailwind-merge resolve conflicting utilities", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-sm", "text-lg")).toBe("text-lg");
  });

  it("supports conditional class maps", () => {
    expect(cn({ a: true, b: false })).toBe("a");
  });
});

describe("formatDuration", () => {
  it("formats sub-second, seconds and minutes", () => {
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(250)).toBe("250ms");
    expect(formatDuration(1500)).toBe("1.5s");
    expect(formatDuration(45_000)).toBe("45s");
    expect(formatDuration(65_000)).toBe("1m 5s");
  });
});

describe("formatDate", () => {
  it("formats ISO dates and tolerates invalid input", () => {
    expect(formatDate("2026-10-14T12:00:00.000Z")).toBe("Oct 14, 2026");
    expect(formatDate("not-a-date")).toBe("");
  });
});
