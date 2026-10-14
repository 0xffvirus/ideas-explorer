"use client";

import Link from "next/link";
import { IdeaForm } from "./idea-form";
import { RecentIdeas } from "./recent-ideas";

export function IntakeScreen({ initialDraft }: { initialDraft?: string }) {
  return (
    <div className="container--reading container pt-[calc(var(--header-offset)+var(--space-8))] pb-16">
      <header className="section-heading">
        <h1 className="t-section">Turn a rough idea into a decision</h1>
        <p className="t-lead measure">
          Describe it in one sentence. Idea Forge polishes the brief, researches the market,
          competitors, customers, and feasibility, then scores it with calibrated confidence — every
          claim carries its sources.
        </p>
      </header>

      <IdeaForm initialDraft={initialDraft} />

      <section aria-labelledby="recent-heading" className="mt-16">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h2 id="recent-heading" className="t-subsection">
            Recent ideas
          </h2>
          <Link href="/ideas" className="link t-meta">
            View library
          </Link>
        </div>
        <RecentIdeas />
      </section>
    </div>
  );
}
