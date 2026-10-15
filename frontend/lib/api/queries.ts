"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, toQueryInput } from "./client";
import { compareKeys, ideaKeys, runKeys, tagKeys } from "./keys";
import type {
  ClarifyRequest,
  CompareReport,
  IdeaCreate,
  IdeaDetail,
  IdeaListResponse,
  IdeasQuery,
  IdeaUpdate,
  IdeaVersionCreate,
  Report,
  RunRead,
  SimilarIdea,
  TagCount,
} from "./types";

export type {
  ClarifyRequest,
  ClarifyingQuestion,
  CompareEntry,
  CompareIdeaReport,
  CompareReport,
  IdeaCreate,
  IdeaDetail,
  IdeaListResponse,
  IdeasQuery,
  IdeaStatus,
  IdeaSummary,
  IdeaUpdate,
  IdeaVerdict,
  IdeaVersionCreate,
  IdeaVersionRead,
  NextStep,
  Report,
  ReportBrief,
  ReportClaim,
  ReportHeader,
  ReportSection,
  RunRead,
  RunStepRead,
  ScorecardEntry,
  SearchMode,
  SimilarIdea,
  SortField,
  Source,
  TagCount,
} from "./types";

async function listIdeas(query: IdeasQuery): Promise<IdeaListResponse> {
  const response = await apiFetch<IdeaListResponse>("/ideas", {
    query: toQueryInput(query),
  });
  return { items: response.items ?? [], next_cursor: response.next_cursor ?? null };
}

export interface UseIdeasOptions {
  enabled?: boolean;
}

/**
 * Cursor-paginated idea list. Flatten `data.pages[].items` for the visible rows
 * and call `fetchNextPage` for "Load more".
 */
export function useIdeas(filters: IdeasQuery, options: UseIdeasOptions = {}) {
  return useInfiniteQuery({
    queryKey: ideaKeys.list(filters),
    queryFn: ({ pageParam }) => listIdeas({ ...filters, cursor: pageParam }),
    initialPageParam: undefined as string | null | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: options.enabled ?? true,
  });
}

export function useIdea(id: string | null | undefined) {
  return useQuery({
    queryKey: ideaKeys.detail(id ?? ""),
    queryFn: () => apiFetch<IdeaDetail>(`/ideas/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateIdea() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IdeaCreate) => apiFetch<IdeaDetail>("/ideas", { method: "POST", body }),
    onSuccess: (idea) => {
      queryClient.setQueryData(ideaKeys.detail(idea.id), idea);
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}

export function useUpdateIdea(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IdeaUpdate) =>
      apiFetch<IdeaDetail>(`/ideas/${id}`, { method: "PATCH", body }),
    onSuccess: (idea) => {
      queryClient.setQueryData(ideaKeys.detail(idea.id), idea);
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}

export function useAddVersion(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IdeaVersionCreate) =>
      apiFetch<IdeaDetail>(`/ideas/${id}/versions`, { method: "POST", body }),
    onSuccess: (idea) => {
      queryClient.setQueryData(ideaKeys.detail(idea.id), idea);
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}

export function useSimilarIdeas(id: string | null | undefined) {
  return useQuery({
    queryKey: ideaKeys.similar(id ?? ""),
    queryFn: () => apiFetch<SimilarIdea[]>(`/ideas/${id}/similar`),
    enabled: Boolean(id),
  });
}

export function useTags() {
  return useQuery({
    queryKey: tagKeys.all,
    queryFn: () => apiFetch<TagCount[]>("/tags"),
    staleTime: 60_000,
  });
}

export function useRuns(ideaId: string | null | undefined) {
  return useQuery({
    queryKey: ideaKeys.runs(ideaId ?? ""),
    queryFn: () => apiFetch<RunRead[]>(`/ideas/${ideaId}/runs`),
    enabled: Boolean(ideaId),
  });
}

const ACTIVE_RUN_STATUSES = new Set(["pending", "running", "awaiting_input"]);

export function useRun(id: string | null | undefined) {
  return useQuery({
    queryKey: runKeys.detail(id ?? ""),
    queryFn: () => apiFetch<RunRead>(`/runs/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_RUN_STATUSES.has(status) ? 2000 : false;
    },
  });
}

export function useRerunStep(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (step: string) =>
      apiFetch<RunRead>(`/runs/${runId}/steps/${step}/rerun`, { method: "POST" }),
    onSuccess: (run) => {
      // The API returns the run already reset to `pending`, so seed the caches
      // from that response: the re-arm (progress panel + SSE subscription) must
      // happen immediately, not after the refetches land.
      queryClient.setQueryData(runKeys.detail(run.id), run);
      queryClient.setQueryData<RunRead[] | undefined>(ideaKeys.runs(run.idea_id), (previous) =>
        previous?.map((item) => (item.id === run.id ? run : item)),
      );
      void queryClient.invalidateQueries({ queryKey: runKeys.detail(run.id) });
      void queryClient.invalidateQueries({ queryKey: ideaKeys.runs(run.idea_id) });
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}

export function useClarify(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ClarifyRequest) =>
      apiFetch<RunRead>(`/runs/${runId}/clarify`, { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}

export function useReport(ideaId: string | null | undefined, version?: number) {
  return useQuery({
    queryKey: ideaKeys.report(ideaId ?? "", version),
    queryFn: () => apiFetch<Report>(`/ideas/${ideaId}/report`, { query: { version } }),
    enabled: Boolean(ideaId),
  });
}

export function useCompare(ids: string[]) {
  return useQuery({
    queryKey: compareKeys.list(ids),
    queryFn: () => apiFetch<CompareReport>("/compare", { query: { ids: ids.join(",") } }),
    enabled: ids.length >= 2,
  });
}
