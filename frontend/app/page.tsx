import { Suspense } from "react";

import { HomeIntake } from "@/components/home-intake";
import { RecentIdeas } from "@/components/recent-ideas";
import { Skeleton } from "@/components/ui/skeleton";

export default function HomePage() {
  return (
    <div className="flex flex-col">
      <Suspense fallback={<IntakeSkeleton />}>
        <HomeIntake />
      </Suspense>
      <Suspense fallback={null}>
        <RecentIdeas />
      </Suspense>
    </div>
  );
}

function IntakeSkeleton() {
  return (
    <div className="mx-auto w-full max-w-3xl" aria-hidden="true">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="mt-4 h-5 w-1/2" />
      <Skeleton className="mt-8 h-48 w-full rounded-lg" />
      <Skeleton className="mt-3 h-11 w-32" />
    </div>
  );
}
