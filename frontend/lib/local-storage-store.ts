"use client";

import { useSyncExternalStore } from "react";

export interface ExternalStore<T> {
  getSnapshot: () => T;
  getServerSnapshot: () => T;
  subscribe: (listener: () => void) => () => void;
  set: (value: T) => void;
}

interface CreateStoreOptions<T> {
  key: string;
  fallback: T;
  /** Validate/coerce a value read back from localStorage. */
  parse: (value: unknown) => T;
}

/**
 * A tiny external store persisted to localStorage. `useSyncExternalStore`
 * consumers render the server snapshot during SSR/hydration and switch to the
 * persisted value right after, so no hydration mismatch is possible.
 */
export function createLocalStorageStore<T>({
  key,
  fallback,
  parse,
}: CreateStoreOptions<T>): ExternalStore<T> {
  let current: T = fallback;

  if (typeof window !== "undefined") {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) current = parse(JSON.parse(raw));
    } catch {
      current = fallback;
    }
  }

  const listeners = new Set<() => void>();

  function persist(value: T) {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage can be unavailable (private mode, quota); state still works in memory.
    }
  }

  return {
    getSnapshot: () => current,
    getServerSnapshot: () => fallback,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    set: (value) => {
      current = value;
      persist(value);
      for (const listener of listeners) listener();
    },
  };
}

/** Subscribe a component to an external store (hydration-safe). */
export function useExternalStore<T>(store: ExternalStore<T>): T {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
}
