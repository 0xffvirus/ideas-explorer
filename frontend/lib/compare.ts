import { z } from "zod";

export const MIN_COMPARE_IDS = 2;
export const MAX_COMPARE_IDS = 3;

export type CompareIdsResult = { ok: true; ids: string[] } | { ok: false; message: string };

const uuidListSchema = z.array(z.uuid());

/**
 * Validate the `ids` search param for `/compare`: 2–3 unique UUIDs.
 * Returns a user-facing message instead of ids when the selection is invalid,
 * so the page can render a friendly empty state without calling the API.
 */
export function parseCompareIds(raw: string | null | undefined): CompareIdsResult {
  const parts = (raw ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");

  if (parts.length === 0) {
    return { ok: false, message: "Pick 2–3 ideas from the library to compare them side by side." };
  }

  const parsed = uuidListSchema.safeParse(parts);
  if (!parsed.success) {
    return {
      ok: false,
      message: "One of the selected ideas has an invalid id. Pick the ideas again from the library.",
    };
  }

  const ids = parsed.data;
  if (new Set(ids).size !== ids.length) {
    return { ok: false, message: "The same idea is selected more than once — remove the duplicate." };
  }
  if (ids.length < MIN_COMPARE_IDS) {
    return { ok: false, message: "Pick at least 2 ideas to compare." };
  }
  if (ids.length > MAX_COMPARE_IDS) {
    return { ok: false, message: "Compare up to 3 ideas at a time." };
  }

  return { ok: true, ids };
}
