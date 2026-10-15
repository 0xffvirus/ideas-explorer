"use client";

import { ChevronDown, Loader2, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { useCreateIdea, type IdeaCreate } from "@/lib/api/queries";
import { useExternalStore } from "@/lib/local-storage-store";
import { EMPTY_INTAKE_DRAFT, intakeDraftStore, type IntakeDraft } from "@/lib/stores";
import { cn } from "@/lib/utils";
import {
  ideaIntakeSchema,
  isRawInputSubmittable,
  MAX_RAW_INPUT_CHARS,
  WARN_RAW_INPUT_CHARS,
} from "@/lib/validation";

function toCreateBody(values: z.infer<typeof ideaIntakeSchema>): IdeaCreate {
  const context = values.context;
  const hasContext =
    context !== undefined &&
    (context.target_region !== undefined ||
      context.audience_hint !== undefined ||
      context.budget_hint !== undefined);
  return {
    raw_input: values.raw_input,
    analyze: true,
    ...(hasContext ? { context } : {}),
  };
}

const CONTEXT_FIELDS: Array<{
  key: keyof IntakeDraft["context"];
  label: string;
  placeholder: string;
}> = [
  { key: "target_region", label: "Region", placeholder: "e.g. EU, US, MENA" },
  { key: "audience_hint", label: "Audience", placeholder: "e.g. indie freelancers" },
  { key: "budget_hint", label: "Budget", placeholder: "e.g. under $5k to MVP" },
];

/**
 * Intake form.
 *
 * The spec asks for an "optimistic Queued state" on submit. A true optimistic
 * navigation would need a client-supplied id for `/ideas/[id]`, which the API
 * does not accept (and inventing one would 404). The accepted interpretation:
 * make the submit feel immediate instead — the button switches to "Creating…",
 * duplicate submits are disabled, and navigation happens the moment the 201
 * returns (the local API is fast, and `useCreateIdea` already seeds the detail
 * cache so the idea page renders without a second round trip).
 */
export function HomeIntake() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefilledQuery = searchParams.get("q")?.trim() ?? "";
  const draft = useExternalStore(intakeDraftStore);
  const [contextOpen, setContextOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createIdea = useCreateIdea();
  const errorId = useId();
  const countId = useId();

  // "Create one from this query" lands on /?q=…; prefill when there is no draft yet.
  useEffect(() => {
    if (prefilledQuery === "") return;
    const current = intakeDraftStore.getSnapshot();
    if (current.raw_input.trim() === "") {
      intakeDraftStore.set({ ...current, raw_input: prefilledQuery });
    }
  }, [prefilledQuery]);

  const rawInput = draft.raw_input;
  const canSubmit = isRawInputSubmittable(rawInput) && !createIdea.isPending;

  function updateDraft(patch: Partial<IntakeDraft>) {
    intakeDraftStore.set({ ...draft, ...patch });
  }

  function updateContext(key: keyof IntakeDraft["context"], value: string) {
    intakeDraftStore.set({ ...draft, context: { ...draft.context, [key]: value } });
  }

  function handleSubmit() {
    const result = ideaIntakeSchema.safeParse({
      raw_input: rawInput,
      context: draft.context,
    });
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Check your input and try again.");
      return;
    }
    setError(null);
    createIdea.mutate(toCreateBody(result.data), {
      onSuccess: (idea) => {
        intakeDraftStore.set(EMPTY_INTAKE_DRAFT);
        router.push(`/ideas/${idea.id}`);
      },
      onError: (mutationError) => {
        setError(
          mutationError instanceof ApiError
            ? mutationError.detail
            : "Could not create the idea. Is the API running?",
        );
      },
    });
  }

  return (
    <section aria-labelledby="intake-heading" className="mx-auto w-full max-w-3xl">
      <h1
        id="intake-heading"
        className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
      >
        Describe your idea, however rough
      </h1>
      <p className="mt-3 max-w-xl text-muted-foreground">
        One sentence or a paragraph. Analysis starts as soon as you press Analyze.
      </p>

      <form
        className="mt-8"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) handleSubmit();
        }}
      >
        <label htmlFor="idea-input" className="sr-only">
          Your idea
        </label>
        <Textarea
          id="idea-input"
          value={rawInput}
          onChange={(event) => updateDraft({ raw_input: event.target.value })}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              if (canSubmit) handleSubmit();
            }
          }}
          placeholder="A tool that helps…"
          aria-invalid={error !== null}
          aria-describedby={cn(countId, error ? errorId : undefined)}
          className="min-h-40 resize-y p-4 text-base sm:min-h-48"
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button type="submit" size="lg" disabled={!canSubmit}>
            {createIdea.isPending ? (
              <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <Sparkles aria-hidden="true" />
            )}
            {createIdea.isPending ? "Creating…" : "Analyze"}
          </Button>
          <span className="text-xs text-muted-foreground">⌘/Ctrl + Enter to submit</span>
          {rawInput.length > WARN_RAW_INPUT_CHARS ? (
            <span
              id={countId}
              className={cn(
                "ml-auto text-xs tabular-nums",
                rawInput.length > MAX_RAW_INPUT_CHARS
                  ? "text-destructive"
                  : "text-muted-foreground",
              )}
            >
              {rawInput.length.toLocaleString("en")} / {MAX_RAW_INPUT_CHARS.toLocaleString("en")}
            </span>
          ) : null}
        </div>

        {error ? (
          <p id={errorId} role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <div className="mt-6">
          <button
            type="button"
            onClick={() => setContextOpen((open) => !open)}
            aria-expanded={contextOpen}
            aria-controls="intake-context"
            className="inline-flex items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
          >
            <ChevronDown
              className={cn(
                "size-4 transition-transform motion-reduce:transition-none",
                contextOpen && "rotate-180",
              )}
              aria-hidden="true"
            />
            Add context (optional)
          </button>
          {contextOpen ? (
            <div id="intake-context" className="mt-4 grid gap-4 sm:grid-cols-3">
              {CONTEXT_FIELDS.map((field) => (
                <div key={field.key} className="flex flex-col gap-1.5">
                  <label
                    htmlFor={`intake-${field.key}`}
                    className="text-xs font-medium text-muted-foreground"
                  >
                    {field.label}
                  </label>
                  <Input
                    id={`intake-${field.key}`}
                    value={draft.context[field.key]}
                    onChange={(event) => updateContext(field.key, event.target.value)}
                    placeholder={field.placeholder}
                  />
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </form>
    </section>
  );
}
