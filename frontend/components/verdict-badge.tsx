import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { IdeaVerdict } from "@/lib/api/types";

const VERDICT_LABELS: Record<IdeaVerdict, string> = {
  pursue: "Pursue",
  refine: "Refine",
  park: "Park",
};

const VERDICT_VARIANTS: Record<IdeaVerdict, BadgeProps["variant"]> = {
  pursue: "success",
  refine: "warning",
  park: "secondary",
};

export interface VerdictBadgeProps {
  verdict: IdeaVerdict | null | undefined;
  className?: string;
}

export function VerdictBadge({ verdict, className }: VerdictBadgeProps) {
  if (!verdict) return null;
  return (
    <Badge variant={VERDICT_VARIANTS[verdict]} className={className}>
      {VERDICT_LABELS[verdict]}
    </Badge>
  );
}
