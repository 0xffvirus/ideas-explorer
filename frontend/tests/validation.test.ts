import { describe, expect, it } from "vitest";

import { ideaIntakeSchema, isRawInputSubmittable, MAX_RAW_INPUT_CHARS } from "@/lib/validation";

describe("ideaIntakeSchema", () => {
  it("rejects an empty idea", () => {
    const result = ideaIntakeSchema.safeParse({ raw_input: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("Describe your idea first.");
    }
  });

  it("rejects a whitespace-only idea", () => {
    expect(ideaIntakeSchema.safeParse({ raw_input: "   \n\t " }).success).toBe(false);
  });

  it("rejects ideas over the character cap", () => {
    const result = ideaIntakeSchema.safeParse({ raw_input: "x".repeat(MAX_RAW_INPUT_CHARS + 1) });
    expect(result.success).toBe(false);
  });

  it("accepts an idea at exactly the cap and trims it", () => {
    const result = ideaIntakeSchema.safeParse({
      raw_input: `  ${"x".repeat(MAX_RAW_INPUT_CHARS)}  `,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.raw_input).toHaveLength(MAX_RAW_INPUT_CHARS);
    }
  });

  it("treats context as optional", () => {
    const result = ideaIntakeSchema.safeParse({ raw_input: "A tool for cats" });
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.context).toBeUndefined();
  });

  it("normalizes blank context fields to undefined", () => {
    const result = ideaIntakeSchema.safeParse({
      raw_input: "A tool for cats",
      context: { target_region: "  EU ", audience_hint: "", budget_hint: "   " },
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.context).toEqual({
        target_region: "EU",
        audience_hint: undefined,
        budget_hint: undefined,
      });
    }
  });

  it("rejects over-long context fields", () => {
    const result = ideaIntakeSchema.safeParse({
      raw_input: "A tool for cats",
      context: { target_region: "x".repeat(121) },
    });
    expect(result.success).toBe(false);
  });
});

describe("isRawInputSubmittable", () => {
  it("mirrors the disabled-button rules", () => {
    expect(isRawInputSubmittable("")).toBe(false);
    expect(isRawInputSubmittable("   ")).toBe(false);
    expect(isRawInputSubmittable("x".repeat(MAX_RAW_INPUT_CHARS + 1))).toBe(false);
    expect(isRawInputSubmittable("A rough idea")).toBe(true);
    expect(isRawInputSubmittable("x".repeat(MAX_RAW_INPUT_CHARS))).toBe(true);
  });
});
