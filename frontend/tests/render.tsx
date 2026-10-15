import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface ProvidersProps {
  children: ReactNode;
  client: QueryClient;
}

function Providers({ children, client }: ProvidersProps) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={0}>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}

export interface RenderWithProvidersResult extends ReturnType<typeof render> {
  client: QueryClient;
}

/** Render with a fresh QueryClient and TooltipProvider wired in. */
export function renderWithProviders(
  ui: ReactElement,
  options: { client?: QueryClient } & Omit<RenderOptions, "wrapper"> = {},
): RenderWithProvidersResult {
  const { client = createTestQueryClient(), ...renderOptions } = options;
  return {
    ...render(ui, {
      wrapper: ({ children }) => <Providers client={client}>{children}</Providers>,
      ...renderOptions,
    }),
    client,
  };
}
