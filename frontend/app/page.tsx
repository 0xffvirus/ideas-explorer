import { Suspense } from "react";
import { IntakeScreen } from "@/components/intake/intake-screen";

type SearchParams = PageProps<"/">["searchParams"];

// Intake reads an optional ?draft= at request time; instant-navigation
// validation of a prerendered segment does not apply.
export const instant = false;

async function IntakeLoader({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const draft = typeof params.draft === "string" ? params.draft.slice(0, 5000) : undefined;
  return <IntakeScreen initialDraft={draft} />;
}

export default function HomePage(props: PageProps<"/">) {
  return (
    <main id="main">
      <Suspense
        fallback={
          <div
            className="container--reading container pt-[calc(var(--header-offset)+var(--space-8))] pb-16"
            aria-busy="true"
          >
            <div className="h-12 w-2/3 animate-pulse rounded-field bg-surface-subtle" />
            <div className="mt-4 h-5 w-3/4 animate-pulse rounded-field bg-surface-subtle" />
            <div className="mt-8 h-40 animate-pulse rounded-field bg-surface-subtle" />
            <div className="mt-4 h-11 w-36 animate-pulse rounded-pill bg-surface-subtle" />
          </div>
        }
      >
        <IntakeLoader searchParams={props.searchParams} />
      </Suspense>
    </main>
  );
}
