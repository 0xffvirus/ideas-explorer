import type { IdeasQuery } from "./types";

/**
 * Central TanStack Query keys. Every key is derived from `ideaKeys.all`,
 * `runKeys.all`, etc. so prefix invalidation reaches every variant.
 */
export const ideaKeys = {
  all: ["ideas"] as const,
  lists: () => ["ideas", "list"] as const,
  list: (filters: IdeasQuery) => ["ideas", "list", filters] as const,
  details: () => ["ideas", "detail"] as const,
  detail: (id: string) => ["ideas", "detail", id] as const,
  similar: (id: string) => ["ideas", "similar", id] as const,
  runs: (ideaId: string) => ["ideas", "runs", ideaId] as const,
  report: (id: string, version?: number) => ["ideas", "report", id, version ?? null] as const,
};

export const runKeys = {
  all: ["runs"] as const,
  detail: (id: string) => ["runs", "detail", id] as const,
};

export const tagKeys = {
  all: ["tags"] as const,
};

export const compareKeys = {
  all: ["compare"] as const,
  list: (ids: string[]) => ["compare", [...ids].sort()] as const,
};
