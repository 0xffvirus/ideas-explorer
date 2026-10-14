"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";

const MOCKING = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  const [mockReady, setMockReady] = useState(!MOCKING);

  useEffect(() => {
    if (!MOCKING || mockReady) return;
    let active = true;
    void import("@/lib/mocks/install").then(({ installMockFetch }) => {
      installMockFetch();
      if (active) setMockReady(true);
    });
    return () => {
      active = false;
    };
  }, [mockReady]);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>{mockReady ? children : null}</TooltipProvider>
    </QueryClientProvider>
  );
}
