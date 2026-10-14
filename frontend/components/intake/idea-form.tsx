"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCreateIdea } from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";

const DRAFT_KEY = "idea-forge.intake-draft.v1";
const MAX_LENGTH = 5000;

type Draft = {
  rawInput: string;
  region: string;
  audience: string;
  budget: string;
};

const EMPTY_DRAFT: Draft = { rawInput: "", region: "", audience: "", budget: "" };

function readDraft(): Draft {
  try {
    const saved = localStorage.getItem(DRAFT_KEY);
    if (!saved) return EMPTY_DRAFT;
    const parsed = JSON.parse(saved) as Partial<Draft>;
    return { ...EMPTY_DRAFT, ...parsed };
  } catch {
    return EMPTY_DRAFT;
  }
}

export function IdeaForm({ initialDraft }: { initialDraft?: string }) {
  const router = useRouter();
  const createIdea = useCreateIdea();
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [restored, setRestored] = useState(false);
  const [touched, setTouched] = useState(false);
  const rawId = useId();
  const contextId = useId();

  useEffect(() => {
    // Restoring the draft after mount avoids a hydration mismatch (the server
    // cannot read localStorage). This is the documented React pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft((current) => {
      if (current.rawInput.trim()) return current;
      const stored = readDraft();
      if (!stored.rawInput.trim() && initialDraft) {
        return { ...EMPTY_DRAFT, rawInput: initialDraft };
      }
      return stored;
    });
    setRestored(true);
  }, [initialDraft]);

  useEffect(() => {
    if (!restored) return;
    // Written synchronously so a reload (or navigation) never loses the draft.
    if (!draft.rawInput.trim()) {
      localStorage.removeItem(DRAFT_KEY);
      return;
    }
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [draft, restored]);

  const trimmed = draft.rawInput.trim();
  const tooLong = draft.rawInput.length > MAX_LENGTH;
  const empty = trimmed.length === 0;
  const disabled = empty || tooLong || createIdea.isPending;
  const nearLimit = draft.rawInput.length > MAX_LENGTH - 500;

  const context = useMemo(() => {
    const entries: Record<string, string> = {};
    if (draft.region.trim()) entries.target_region = draft.region.trim();
    if (draft.audience.trim()) entries.audience_hint = draft.audience.trim();
    if (draft.budget.trim()) entries.budget_hint = draft.budget.trim();
    return Object.keys(entries).length > 0 ? entries : undefined;
  }, [draft.region, draft.audience, draft.budget]);

  function submit() {
    if (disabled) return;
    createIdea.mutate(
      { raw_input: trimmed, context, analyze: true },
      {
        onSuccess: (idea) => {
          localStorage.removeItem(DRAFT_KEY);
          setDraft(EMPTY_DRAFT);
          router.push(`/ideas/${idea.id}` as Route);
        },
      },
    );
  }

  return (
    <form
      className="stack"
      style={{ "--stack-gap": "var(--space-5)" } as React.CSSProperties}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="field">
        <label htmlFor={rawId} className="field__label">
          Describe your idea, however rough
        </label>
        <textarea
          id={rawId}
          value={draft.rawInput}
          onChange={(event) =>
            setDraft((current) => ({ ...current, rawInput: event.target.value }))
          }
          onBlur={() => setTouched(true)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="e.g. An app that helps independent dog walkers manage bookings and reminders…"
          className="field__control min-h-40 text-base"
          aria-describedby={`${rawId}-help${tooLong || (touched && empty) ? ` ${rawId}-error` : ""}`}
          aria-invalid={tooLong || (touched && empty) || undefined}
          maxLength={MAX_LENGTH + 1}
          autoFocus
          data-testid="idea-input"
        />
        <div className="flex items-start justify-between gap-4">
          <p id={`${rawId}-help`} className="field__help">
            One sentence or a paragraph is enough. ⌘/Ctrl + Enter submits.
          </p>
          {nearLimit && (
            <p className="field__help tabular-nums" data-testid="char-count">
              {draft.rawInput.length.toLocaleString()}/{MAX_LENGTH.toLocaleString()}
            </p>
          )}
        </div>
        {(tooLong || (touched && empty)) && (
          <p id={`${rawId}-error`} className="field__error" role="alert">
            {tooLong
              ? `Trim the idea to ${MAX_LENGTH.toLocaleString()} characters or fewer.`
              : "Write at least a sentence before analyzing."}
          </p>
        )}
      </div>

      <details className="accordion">
        <summary>Add context (optional)</summary>
        <div id={contextId} className="accordion__panel grid gap-4 sm:grid-cols-3">
          <div className="field">
            <label className="field__label" htmlFor={`${contextId}-region`}>
              Region or market
            </label>
            <input
              id={`${contextId}-region`}
              className="field__control"
              value={draft.region}
              onChange={(event) =>
                setDraft((current) => ({ ...current, region: event.target.value }))
              }
              placeholder="e.g. United States, MENA"
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor={`${contextId}-audience`}>
              Audience hint
            </label>
            <input
              id={`${contextId}-audience`}
              className="field__control"
              value={draft.audience}
              onChange={(event) =>
                setDraft((current) => ({ ...current, audience: event.target.value }))
              }
              placeholder="e.g. solo operators"
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor={`${contextId}-budget`}>
              Budget hint
            </label>
            <input
              id={`${contextId}-budget`}
              className="field__control"
              value={draft.budget}
              onChange={(event) =>
                setDraft((current) => ({ ...current, budget: event.target.value }))
              }
              placeholder="e.g. under $10k to MVP"
            />
          </div>
        </div>
      </details>

      <div className="flex flex-wrap items-center gap-4">
        <Button
          type="submit"
          disabled={disabled}
          className="min-h-13 rounded-pill px-6 text-base font-bold"
          data-testid="analyze-button"
        >
          {createIdea.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden="true" /> Queuing…
            </>
          ) : (
            <>
              <Sparkles aria-hidden="true" /> Analyze
            </>
          )}
        </Button>
        <p className="t-meta" aria-live="polite">
          {createIdea.isPending && "Sending to the pipeline…"}
          {createIdea.isError &&
            (isApiError(createIdea.error)
              ? createIdea.error.message
              : "Something went wrong. Try again.")}
        </p>
      </div>
    </form>
  );
}
