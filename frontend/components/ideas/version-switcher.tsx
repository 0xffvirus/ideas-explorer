"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { IdeaVersion } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function VersionSwitcher({
  versions,
  activeNumber,
  onChange,
}: {
  versions: IdeaVersion[];
  activeNumber: number | undefined;
  onChange: (version: number | undefined) => void;
}) {
  if (versions.length <= 1) return null;
  const latest = Math.max(...versions.map((version) => version.number));
  const value = String(activeNumber ?? latest);

  return (
    <div className="flex items-center gap-2">
      <Select
        value={value}
        onValueChange={(next) => onChange(Number(next) === latest ? undefined : Number(next))}
      >
        <SelectTrigger size="sm" aria-label="Report version" data-testid="version-switcher">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {[...versions]
            .sort((a, b) => b.number - a.number)
            .map((version) => (
              <SelectItem key={version.id} value={String(version.number)}>
                v{version.number}
                {version.number === latest ? " (latest)" : ""} ·{" "}
                {formatDateTime(version.created_at)}
              </SelectItem>
            ))}
        </SelectContent>
      </Select>
      {activeNumber != null && activeNumber !== latest && (
        <button type="button" className="link t-meta" onClick={() => onChange(undefined)}>
          Back to latest
        </button>
      )}
    </div>
  );
}
