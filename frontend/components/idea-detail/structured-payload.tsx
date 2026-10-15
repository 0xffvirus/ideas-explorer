import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Human label for a snake_case payload key. */
export function humanizeKey(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .trim();
}

function isPrimitive(value: unknown): value is string | number | boolean {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
}

/** True when a payload value produces visible content. */
export function hasContent(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.some(hasContent);
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).some(hasContent);
  }
  return true;
}

/** True when the section payload has at least one renderable field. */
export function hasStructuredContent(payload: Record<string, unknown>): boolean {
  return Object.values(payload).some(hasContent);
}

function ValueView({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (!hasContent(value)) return null;

  if (isPrimitive(value)) {
    return <p className="text-sm leading-relaxed whitespace-pre-wrap">{String(value)}</p>;
  }

  if (Array.isArray(value)) {
    if (value.every(isPrimitive)) {
      return (
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-relaxed marker:text-muted-foreground">
          {value.map((item, index) => (
            <li key={index}>{String(item)}</li>
          ))}
        </ul>
      );
    }
    return (
      <div className="flex flex-col gap-3">
        {value.map((item, index) => (
          <div key={index} className="rounded-lg border border-border bg-muted/30 p-3">
            <ValueView value={item} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }

  if (depth >= 3) return null;

  return (
    <dl className="flex flex-col gap-2.5">
      {Object.entries(value as Record<string, unknown>)
        .filter(([, item]) => hasContent(item))
        .map(([key, item]) => (
          <div key={key} className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {humanizeKey(key)}
            </dt>
            <dd>
              <ValueView value={item} depth={depth + 1} />
            </dd>
          </div>
        ))}
    </dl>
  );
}

export interface StructuredPayloadProps {
  payload: Record<string, unknown>;
}

/**
 * Renders a section's `json_payload` as labeled cards. Nested objects become
 * definition lists and arrays of objects become stacked blocks.
 */
export function StructuredPayload({ payload }: StructuredPayloadProps) {
  const entries = Object.entries(payload).filter(([, value]) => hasContent(value));
  if (entries.length === 0) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <Card key={key} className="h-full">
          <CardHeader className="p-4 pb-2">
            <CardTitle asChild>
              <h3 className="text-sm">{humanizeKey(key)}</h3>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <ValueView value={value} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
