/**
 * Tiny, dependency-free Markdown parser for report section text.
 *
 * Only the constructs the reports use are supported — headings, paragraphs,
 * bold/italic span text, inline code, links, and ordered/unordered lists. Raw
 * HTML is never interpreted: unknown markup stays visible text. Links are run
 * through `sanitizeUrl`, which drops `javascript:` and other unsafe schemes.
 */

export type InlineToken =
  | { type: "text"; value: string }
  | { type: "bold"; value: string }
  | { type: "italic"; value: string }
  | { type: "code"; value: string }
  | { type: "link"; value: string; href: string };

export type MarkdownBlock =
  | { type: "heading"; level: number; tokens: InlineToken[] }
  | { type: "paragraph"; tokens: InlineToken[] }
  | { type: "list"; ordered: boolean; items: InlineToken[][] }
  | { type: "code"; value: string };

const INLINE_PATTERN =
  /\[([^\]]*)\]\(([^()\s]*(?:\([^()]*\)[^()\s]*)*)\)|\*\*([^*]+)\*\*|\*([^*\n]+)\*|`([^`]+)`/g;
const HEADING_PATTERN = /^(#{1,6})\s+(.*)$/;
const LIST_PATTERN = /^\s*(?:([-*+])|(\d+)[.)])\s+(.*)$/;

const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

/**
 * Return the URL if it is safe to render as a link, otherwise `null`.
 * Relative URLs resolve against the current origin and are allowed.
 */
export function sanitizeUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  try {
    const url = new URL(trimmed, "https://example.invalid/");
    return SAFE_PROTOCOLS.has(url.protocol) ? trimmed : null;
  } catch {
    return null;
  }
}

/** Split one line of text into plain text plus bold/italic/code/link tokens. */
export function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIndex = 0;
  INLINE_PATTERN.lastIndex = 0;

  for (const match of text.matchAll(INLINE_PATTERN)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      tokens.push({ type: "text", value: text.slice(lastIndex, index) });
    }
    const [full, linkText, href, bold, italic, code] = match;
    if (linkText !== undefined && href !== undefined) {
      const safeHref = sanitizeUrl(href);
      if (safeHref !== null) tokens.push({ type: "link", value: linkText, href: safeHref });
      else tokens.push({ type: "text", value: linkText });
    } else if (bold !== undefined) {
      tokens.push({ type: "bold", value: bold });
    } else if (italic !== undefined) {
      tokens.push({ type: "italic", value: italic });
    } else if (code !== undefined) {
      tokens.push({ type: "code", value: code });
    }
    lastIndex = index + full.length;
  }

  if (lastIndex < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIndex) });
  }
  return tokens;
}

function isBlockBoundary(line: string): boolean {
  return (
    line.trim() === "" ||
    line.trim().startsWith("```") ||
    HEADING_PATTERN.test(line) ||
    LIST_PATTERN.test(line)
  );
}

/** Parse a Markdown document into a flat list of block nodes. */
export function parseMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? "";

    if (line.trim() === "") {
      index += 1;
      continue;
    }

    if (line.trim().startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !(lines[index] ?? "").trim().startsWith("```")) {
        code.push(lines[index] ?? "");
        index += 1;
      }
      index += 1;
      blocks.push({ type: "code", value: code.join("\n") });
      continue;
    }

    const heading = HEADING_PATTERN.exec(line);
    if (heading) {
      blocks.push({
        type: "heading",
        level: (heading[1] ?? "").length,
        tokens: parseInline(heading[2] ?? ""),
      });
      index += 1;
      continue;
    }

    const listStart = LIST_PATTERN.exec(line);
    if (listStart) {
      const ordered = listStart[2] !== undefined;
      const items: InlineToken[][] = [];
      while (index < lines.length) {
        const item = LIST_PATTERN.exec(lines[index] ?? "");
        if (!item || (item[2] !== undefined) !== ordered) break;
        items.push(parseInline(item[3] ?? ""));
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && !isBlockBoundary(lines[index] ?? "")) {
      paragraph.push((lines[index] ?? "").trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", tokens: parseInline(paragraph.join(" ")) });
  }

  return blocks;
}
