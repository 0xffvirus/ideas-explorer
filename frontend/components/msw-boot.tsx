"use client";

import { useEffect } from "react";

import { signalMockReady } from "@/lib/api/mock-ready";

/**
 * Started once per page load, even if React invokes effects twice
 * (StrictMode in development): MSW rejects a second `worker.start()`.
 */
let bootPromise: Promise<void> | null = null;

function bootMockWorker(): Promise<void> {
  bootPromise ??= import("@/mocks/browser").then(async ({ worker }) => {
    await worker.start({ onUnhandledFrame: "bypass" });
  });
  return bootPromise;
}

/**
 * Headless component (loaded with `ssr: false`) that starts the MSW browser
 * worker and releases the API client's ready gate in all cases so the UI can
 * never hang on a failed worker start.
 */
export default function MswBoot() {
  useEffect(() => {
    let cancelled = false;
    void bootMockWorker()
      .catch((error: unknown) => {
        console.error("[MSW] Failed to start the mock worker", error);
      })
      .then(() => {
        if (!cancelled) signalMockReady();
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
