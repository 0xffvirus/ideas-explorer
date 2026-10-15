/**
 * Small handshake between the MSW boot component and the API client.
 *
 * In mocking mode the app renders immediately (so the server-rendered tree is
 * complete), while `apiFetch` waits until the service worker is active. This
 * avoids both request races and a client-only wrapper around the whole app.
 */
let armed = false;
let resolveReady: () => void = () => {};
let readyPromise: Promise<void> = Promise.resolve();

/** Arm the gate; called once by the client module that mounts the mock. */
export function armMockReady(): void {
  if (armed) return;
  armed = true;
  readyPromise = new Promise<void>((resolve) => {
    resolveReady = resolve;
  });
}

/** Release `whenMockReady` waiters; safe to call more than once. */
export function signalMockReady(): void {
  resolveReady();
}

/** `null` outside mocking mode (or on the server), otherwise a promise to await. */
export function whenMockReady(): Promise<void> | null {
  return armed ? readyPromise : null;
}
