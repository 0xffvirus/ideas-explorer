"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useClarify } from "@/lib/api/queries";
import type { ClarifyingQuestion } from "@/lib/api/types";

export interface ClarifierFormProps {
  runId: string;
  questions: ClarifyingQuestion[];
  /** Called after a successful answer or skip submission. */
  onSubmitted?: () => void;
}

/**
 * Inline clarifier shown while the run is `awaiting_input`: one textarea per
 * question, plus a Skip button that lets the pipeline continue without answers.
 */
export function ClarifierForm({ runId, questions, onSubmitted }: ClarifierFormProps) {
  const clarify = useClarify(runId);
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ""));

  // Re-seed the local answers if the run asks a different set of questions.
  const [knownQuestions, setKnownQuestions] = useState(questions);
  if (questions !== knownQuestions) {
    setKnownQuestions(questions);
    setAnswers(questions.map(() => ""));
  }

  const allEmpty = answers.every((answer) => answer.trim() === "");

  function submitAnswers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (allEmpty) return;
    clarify.mutate(
      { answers: answers.map((answer) => answer.trim()), skip: false },
      { onSuccess: () => onSubmitted?.() },
    );
  }

  function skip() {
    clarify.mutate({ skip: true }, { onSuccess: () => onSubmitted?.() });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle asChild>
          <h2>Help the analysis continue</h2>
        </CardTitle>
        <CardDescription>
          The agents paused before spending research budget. Answer what you can, or skip.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submitAnswers} className="flex flex-col gap-4">
          {questions.map((question, index) => {
            const inputId = `clarify-${index}`;
            return (
              <div key={`${question.question}-${index}`} className="flex flex-col gap-1.5">
                <label htmlFor={inputId} className="text-sm font-medium text-foreground">
                  {question.question}
                </label>
                {question.why ? (
                  <p className="text-xs text-muted-foreground">{question.why}</p>
                ) : null}
                <Textarea
                  id={inputId}
                  value={answers[index] ?? ""}
                  onChange={(event) => {
                    const next = [...answers];
                    next[index] = event.target.value;
                    setAnswers(next);
                  }}
                  rows={3}
                />
              </div>
            );
          })}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={allEmpty || clarify.isPending}>
              {clarify.isPending ? "Sending…" : "Submit answers"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={skip}
              disabled={clarify.isPending}
            >
              Skip
            </Button>
          </div>
          {clarify.isError ? (
            <p role="alert" className="text-sm text-destructive">
              Could not send your answers. Try again.
            </p>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
