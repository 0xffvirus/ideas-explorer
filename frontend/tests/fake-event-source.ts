/**
 * Minimal `EventSource` stand-in for jsdom. The SSE layer creates a new
 * instance per run; tests drive the stream by emitting named events.
 *
 * It also models the parts of the real API the reconnect logic depends on:
 * `readyState` (`CONNECTING`/`OPEN`/`CLOSED`) and `lastEventId` (preserved by
 * the browser across a native reconnect of the same source).
 */
type Listener = (event: Event) => void;

export class FakeEventSource {
  static instances: FakeEventSource[] = [];

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  /** Set false to model connections that fail before opening. */
  static autoOpen = true;

  static reset(): void {
    FakeEventSource.instances = [];
    FakeEventSource.autoOpen = true;
  }

  static latest(): FakeEventSource | undefined {
    return FakeEventSource.instances.at(-1);
  }

  readonly url: string;
  readonly CONNECTING = FakeEventSource.CONNECTING;
  readonly OPEN = FakeEventSource.OPEN;
  readonly CLOSED = FakeEventSource.CLOSED;
  /** True once `close()` was called deliberately. */
  closed = false;
  /** Mirrors `EventSource.readyState`; starts CONNECTING until the open tick. */
  readyState: number = FakeEventSource.CONNECTING;
  /** Mirrors `EventSource.lastEventId`; updated by `emit` when an id is given. */
  lastEventId = "";
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;

  private listeners = new Map<string, Set<Listener>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
    if (FakeEventSource.autoOpen) {
      queueMicrotask(() => {
        if (!this.closed) this.simulateOpen();
      });
    }
  }

  addEventListener(type: string, listener: Listener): void {
    const set = this.listeners.get(type) ?? new Set<Listener>();
    set.add(listener);
    this.listeners.set(type, set);
  }

  removeEventListener(type: string, listener: Listener): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  /** Mark the source open (browser reconnect completed). */
  simulateOpen(): void {
    if (this.closed) return;
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.(new Event("open"));
  }

  /**
   * Fire an `error` event in the given readyState. Defaults to CLOSED (the
   * browser gave up), which is the hook's manual-reconnect path; pass
   * CONNECTING to model a transient drop the browser retries natively.
   */
  simulateError(readyState: number = FakeEventSource.CLOSED): void {
    this.readyState = readyState;
    this.onerror?.(new Event("error"));
  }

  /** Emit a named event; `id` sets `lastEventId` like an SSE `id:` field. */
  emit(type: string, data: unknown, id?: string | number): void {
    if (id !== undefined) this.lastEventId = String(id);
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
    if (type === "message") this.onmessage?.(event as MessageEvent<string>);
  }
}

/** Swap `globalThis.EventSource` for the fake; returns a restore function. */
export function installFakeEventSource(): () => void {
  const original = globalThis.EventSource;
  FakeEventSource.reset();
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
  return () => {
    globalThis.EventSource = original;
  };
}

/** Wait until the component under test has opened a stream. */
export function waitForEventSource(): Promise<FakeEventSource> {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const check = () => {
      const source = FakeEventSource.latest();
      if (source) {
        resolve(source);
        return;
      }
      if (Date.now() - started > 5000) {
        reject(new Error("No EventSource was created"));
        return;
      }
      setTimeout(check, 10);
    };
    check();
  });
}

/** Wait until the component under test has opened a stream for `runId`. */
export function waitForEventSourceFor(runId: string): Promise<FakeEventSource> {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const check = () => {
      const source = FakeEventSource.instances.find((item) => item.url.includes(`/runs/${runId}/`));
      if (source) {
        resolve(source);
        return;
      }
      if (Date.now() - started > 5000) {
        reject(new Error(`No EventSource was created for run ${runId}`));
        return;
      }
      setTimeout(check, 10);
    };
    check();
  });
}
