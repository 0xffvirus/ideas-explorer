import { getResponse } from "msw";
import { API_URL } from "@/lib/api/client";
import { handlers } from "./handlers";

let installed = false;

/**
 * Installs a fetch wrapper that resolves requests through the MSW handlers.
 * Used in dev and e2e instead of a service worker so the mock layer stays in
 * the regular module graph (no worker file, works under Turbopack SSR builds).
 */
export function installMockFetch(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    // Read the URL without constructing a Request (avoids consuming stream bodies).
    const url =
      input instanceof Request ? input.url : typeof input === "string" ? input : input.toString();
    if (!url.startsWith(`${API_URL}/`) && url !== API_URL) {
      return originalFetch(input, init);
    }
    const request = input instanceof Request ? input : new Request(input, init);
    const mocked = await getResponse(handlers, request);
    return mocked ?? originalFetch(input, init);
  };
}
