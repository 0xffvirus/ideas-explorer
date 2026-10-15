"use client";

import { Fragment, useMemo } from "react";

import { parseMarkdown, type InlineToken, type MarkdownBlock } from "@/lib/markdown";
import { cn } from "@/lib/utils";

const HEADING_CLASS: Record<number, string> = {
  3: "text-base font-semibold tracking-tight",
  4: "text-sm font-semibold tracking-tight",
  5: "text-sm font-medium",
  6: "text-sm font-medium text-muted-foreground",
};

function Inline({ tokens }: { tokens: InlineToken[] }) {
  return (
    <>
      {tokens.map((token, index) => {
        switch (token.type) {
          case "bold":
            return <strong key={index}>{token.value}</strong>;
          case "italic":
            return <em key={index}>{token.value}</em>;
          case "code":
            return (
              <code
                key={index}
                className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground"
              >
                {token.value}
              </code>
            );
          case "link":
            return (
              <a
                key={index}
                href={token.href}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-sm font-medium text-foreground underline underline-offset-4 hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
              >
                {token.value}
              </a>
            );
          default:
            return <Fragment key={index}>{token.value}</Fragment>;
        }
      })}
    </>
  );
}

function Block({ block }: { block: MarkdownBlock }) {
  switch (block.type) {
    case "heading": {
      const level = Math.min(Math.max(block.level + 2, 3), 6);
      const Tag = `h${level}` as "h3" | "h4" | "h5" | "h6";
      return (
        <Tag className={HEADING_CLASS[level] ?? HEADING_CLASS[3]}>
          <Inline tokens={block.tokens} />
        </Tag>
      );
    }
    case "list": {
      const Tag = block.ordered ? "ol" : "ul";
      return (
        <Tag
          className={cn(
            "flex flex-col gap-1 pl-5 marker:text-muted-foreground",
            block.ordered ? "list-decimal" : "list-disc",
          )}
        >
          {block.items.map((item, index) => (
            <li key={index}>
              <Inline tokens={item} />
            </li>
          ))}
        </Tag>
      );
    }
    case "code":
      return (
        <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
          <code>{block.value}</code>
        </pre>
      );
    default:
      return (
        <p>
          <Inline tokens={block.tokens} />
        </p>
      );
  }
}

export interface SafeMarkdownProps {
  markdown: string;
  className?: string;
}

/**
 * Renders report markdown as React elements. No `dangerouslySetInnerHTML` and
 * no raw HTML execution: unsupported markup renders as plain text.
 */
export function SafeMarkdown({ markdown, className }: SafeMarkdownProps) {
  const blocks = useMemo(() => parseMarkdown(markdown), [markdown]);
  if (blocks.length === 0) return null;
  return (
    <div className={cn("flex flex-col gap-3 text-sm leading-relaxed text-foreground", className)}>
      {blocks.map((block, index) => (
        <Block key={index} block={block} />
      ))}
    </div>
  );
}
