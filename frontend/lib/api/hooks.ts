"use client";

import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "./client";
import { keys } from "./keys";
import type {
  CreateIdeaRequest,
  CreateVersionRequest,
  IdeaDetail,
  ListIdeasParams,
  RespondRunRequest,
  Run,
  UpdateIdeaRequest,
} from "./types";

export function useIdeas(params: ListIdeasParams, options?: { enabled?: boolean }) {
  return useInfiniteQuery({
    queryKey: keys.ideas(params),
    queryFn: ({ pageParam }) => api.listIdeas({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
}

export function useIdea(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.idea(id),
    queryFn: () => api.getIdea(id),
    enabled: options?.enabled ?? Boolean(id),
  });
}

export function useSimilarIdeas(id: string, limit = 5) {
  return useQuery({
    queryKey: keys.similar(id),
    queryFn: () => api.getSimilar(id, limit),
    enabled: Boolean(id),
  });
}

export function useTags() {
  return useQuery({
    queryKey: keys.tags(),
    queryFn: () => api.listTags(),
    staleTime: 5 * 60_000,
  });
}

export function useReport(id: string, version?: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.report(id, version),
    queryFn: () => api.getReport(id, version),
    enabled: options?.enabled ?? Boolean(id),
  });
}

export function useCompare(ids: string[]) {
  return useQuery({
    queryKey: keys.compare(ids),
    queryFn: () => api.compare(ids),
    enabled: ids.length >= 2 && ids.length <= 3,
  });
}

export function useCreateIdea() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateIdeaRequest) => api.createIdea(body),
    onSuccess: (idea) => {
      queryClient.setQueryData(keys.idea(idea.id), idea);
      void queryClient.invalidateQueries({ queryKey: ["ideas", "list"] });
    },
  });
}

export function useUpdateIdea(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateIdeaRequest) => api.updateIdea(id, body),
    onSuccess: (idea) => {
      queryClient.setQueryData(keys.idea(id), idea);
      void queryClient.invalidateQueries({ queryKey: ["ideas", "list"] });
    },
  });
}

export function useAddVersion(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateVersionRequest) => api.createVersion(id, body),
    onSuccess: (idea) => {
      queryClient.setQueryData(keys.idea(id), idea);
      void queryClient.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useRerunStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, step }: { runId: string; step: string }) => api.rerunStep(runId, step),
    onSuccess: (run: Run) => {
      queryClient.setQueryData<IdeaDetail | undefined>(keys.idea(run.idea_id), (current) =>
        current ? { ...current, latest_run: run, status: "analyzing" } : current,
      );
      void queryClient.invalidateQueries({ queryKey: keys.idea(run.idea_id) });
    },
  });
}

export function useRespondToRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, body }: { runId: string; body: RespondRunRequest }) =>
      api.respondToRun(runId, body),
    onSuccess: (run) => {
      queryClient.setQueryData<IdeaDetail | undefined>(keys.idea(run.idea_id), (current) =>
        current ? { ...current, latest_run: run, status: "analyzing" } : current,
      );
      void queryClient.invalidateQueries({ queryKey: keys.idea(run.idea_id) });
    },
  });
}
