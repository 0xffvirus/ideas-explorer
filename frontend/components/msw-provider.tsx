"use client";

import dynamic from "next/dynamic";

import type { ReactNode } from "react";

import { armMockReady } from "@/lib/api/mock-ready";

const MOCKING_ENABLED = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";

// Arm the API gate as soon as this client module loads, i.e. before any child
// effect can issue a request.
if (MOCKING_ENABLED && typeof window !== "undefined") {
  armMockReady();
}

// `ssr: false`: `msw/browser` is browser-only (its exports map has
// `"node": null`) and must never enter the server bundle. The boot component
// renders nothing, so the app's own tree stays server-renderable.
const MswBoot = dynamic(() => import("@/components/msw-boot"), { ssr: false });

/**
 * Renders the mock boot component alongside the app. Requests made while the
 * service worker starts are held by the API client's ready gate.
 */
export function MswProvider({ children }: { children: ReactNode }) {
  if (!MOCKING_ENABLED) return <>{children}</>;
  return (
    <>
      <MswBoot />
      {children}
    </>
  );
}
