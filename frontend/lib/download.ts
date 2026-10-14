import { api } from "@/lib/api/client";

export function slugify(value: string): string {
  return (
    value
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[^\w\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-")
      .slice(0, 60) || "idea"
  );
}

export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function downloadReport(
  ideaId: string,
  title: string,
  format: "md" | "pdf",
  version?: number,
): Promise<void> {
  const filename = `${slugify(title)}-report.${format}`;
  if (format === "md") {
    const markdown = await api.getReportMarkdown(ideaId, version);
    triggerDownload(new Blob([markdown], { type: "text/markdown;charset=utf-8" }), filename);
    return;
  }
  const blob = await api.getReportPdf(ideaId, version);
  triggerDownload(blob, filename);
}
