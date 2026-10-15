export type MoveDirection = 1 | -1;

/**
 * Pure index arithmetic for j/k list navigation. Starts at 0 when moving
 * forward from "nothing selected" and at the last item moving backward; wraps
 * around at both ends. Returns -1 for an empty list.
 */
export function nextSelectedIndex(
  current: number,
  direction: MoveDirection,
  length: number,
): number {
  if (length <= 0) return -1;
  if (current < 0 || current >= length) return direction === 1 ? 0 : length - 1;
  return (current + direction + length) % length;
}

/** True when a keyboard event target is a text-entry surface (typing should win). */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined" || !(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  switch (target.tagName.toLowerCase()) {
    case "input":
    case "textarea":
    case "select":
      return true;
    default:
      return false;
  }
}
