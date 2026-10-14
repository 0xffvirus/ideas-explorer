import { Suspense } from "react";
import { IdeaScreen } from "./idea-screen";
import { IdeaPageSkeleton } from "@/components/ideas/idea-page-skeleton";

type Params = PageProps<"/ideas/[id]">["params"];

// Interactive route that resolves its id at request time; instant-navigation
// validation of a prerendered segment does not apply.
export const instant = false;

async function IdeaLoader({ params }: { params: Params }) {
  const { id } = await params;
  return <IdeaScreen ideaId={id} />;
}

export default function IdeaPage(props: PageProps<"/ideas/[id]">) {
  return (
    <main id="main">
      <Suspense fallback={<IdeaPageSkeleton />}>
        <IdeaLoader params={props.params} />
      </Suspense>
    </main>
  );
}
