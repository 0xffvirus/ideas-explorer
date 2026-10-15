import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { IdeaStatus } from "@/lib/api/types";

const STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Draft",
  queued: "Queued",
  analyzing: "Analyzing",
  done: "Done",
  failed: "Failed",
};

const STATUS_VARIANTS: Record<IdeaStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  queued: "warning",
  analyzing: "info",
  done: "success",
  failed: "destructive",
};

export interface StatusBadgeProps {
  status: IdeaStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge variant={STATUS_VARIANTS[status]} className={className}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}
