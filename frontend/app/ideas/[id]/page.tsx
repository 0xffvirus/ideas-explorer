import { Suspense } from "react";

import { IdeaDetailView } from "@/components/idea-detail-view";
import { Skeleton } from "@/components/ui/skeleton";

export default function IdeaPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<IdeaDetailSkeleton />}>
      <IdeaDetailRoute params={params} />
    </Suspense>
  );
}

async function IdeaDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <IdeaDetailView ideaId={id} />;
}

function IdeaDetailSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-9 w-2/3" />
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}
