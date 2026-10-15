/**
 * Shared MSW handlers live in `mocks/handlers.ts` so the browser worker (e2e)
 * and the Node server (Vitest) exercise exactly the same mock API.
 */
export { handlers, resetMockStore } from "@/mocks/handlers";
