"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ClarifyingQuestion } from "@/lib/api/types";

export function ClarifyForm({
  questions,
  onSubmit,
  onSkip,
  isPending,
}: {
  questions: ClarifyingQuestion[];
  onSubmit: (answers: { question_id: string; answer: string }[]) => void;
  onSkip: () => void;
  isPending: boolean;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const allAnswered = questions.every((question) => (answers[question.id] ?? "").trim().length > 0);

  return (
    <section
      aria-labelledby="clarify-heading"
      className="rounded-card border border-line bg-surface p-6"
      data-testid="clarify-form"
    >
      <h2 id="clarify-heading" className="t-card">
        A few quick questions
      </h2>
      <p className="t-body mt-1">
        The brief needs a bit more detail. Answer what you can, or skip and the pipeline will make
        its best guess.
      </p>
      <form
        className="mt-5 grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!allAnswered || isPending) return;
          onSubmit(
            questions.map((question) => ({
              question_id: question.id,
              answer: (answers[question.id] ?? "").trim(),
            })),
          );
        }}
      >
        {questions.map((question, index) => (
          <div key={question.id} className="field">
            <label className="field__label" htmlFor={`clarify-${question.id}`}>
              {index + 1}. {question.question}
            </label>
            {question.help && <p className="field__help">{question.help}</p>}
            <input
              id={`clarify-${question.id}`}
              className="field__control"
              value={answers[question.id] ?? ""}
              onChange={(event) =>
                setAnswers((current) => ({ ...current, [question.id]: event.target.value }))
              }
              disabled={isPending}
            />
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            disabled={!allAnswered || isPending}
            className="rounded-pill font-bold"
            data-testid="clarify-submit"
          >
            {isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" /> Sending…
              </>
            ) : (
              "Continue analysis"
            )}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={onSkip}
            disabled={isPending}
            className="rounded-pill font-bold"
            data-testid="clarify-skip"
          >
            Skip
          </Button>
        </div>
      </form>
    </section>
  );
}
