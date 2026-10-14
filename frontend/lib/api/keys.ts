import type { ListIdeasParams } from "./types";

export const keys = {
  ideas: (params: ListIdeasParams) => ["ideas", "list", params] as const,
  idea: (id: string) => ["ideas", "detail", id] as const,
  similar: (id: string) => ["ideas", "similar", id] as const,
  tags: () => ["tags"] as const,
  report: (id: string, version?: number) => ["ideas", "report", id, version ?? "latest"] as const,
  compare: (ids: string[]) => ["compare", [...ids].sort().join(",")] as const,
};
