"use client";

import {
  Archive,
  ArchiveRestore,
  ChevronDown,
  Download,
  Pencil,
  Pin,
  PinOff,
  Plus,
  X,
} from "lucide-react";
import { useId, useRef, useState, type FormEvent } from "react";

import { ScoreBadge } from "@/components/score-badge";
import { StatusBadge } from "@/components/status-badge";
import { VerdictBadge } from "@/components/verdict-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { apiUrl } from "@/lib/api/client";
import { useUpdateIdea } from "@/lib/api/queries";
import type { IdeaDetail, IdeaVersionRead } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

function TitleEditor({ idea }: { idea: IdeaDetail }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const update = useUpdateIdea(idea.id);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(idea.title);

  function startEditing() {
    setValue(idea.title);
    update.reset();
    setEditing(true);
  }

  const trimmed = value.trim();
  const canSave = trimmed !== "" && trimmed !== idea.title && !update.isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmed === idea.title) {
      setEditing(false);
      return;
    }
    if (!canSave) return;
    update.mutate({ title: trimmed }, { onSuccess: () => setEditing(false) });
  }

  if (!editing) {
    return (
      <div className="flex items-start gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          {idea.title}
        </h1>
        <Button
          variant="ghost"
          size="icon"
          className="mt-0.5 size-8 shrink-0 text-muted-foreground"
          aria-label="Edit title"
          onClick={startEditing}
        >
          <Pencil aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-xl flex-wrap items-center gap-2">
      <label htmlFor={inputId} className="sr-only">
        Idea title
      </label>
      <Input
        id={inputId}
        ref={(node) => {
          inputRef.current = node;
          if (node && document.activeElement !== node) node.focus();
        }}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            setEditing(false);
          }
        }}
        aria-invalid={update.isError || undefined}
        className="h-10 w-full text-base sm:max-w-md"
      />
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={!canSave}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
      {update.isError ? (
        <p role="alert" className="w-full text-sm text-destructive">
          Could not save the title. Try again.
        </p>
      ) : null}
    </form>
  );
}

function TagEditor({ idea }: { idea: IdeaDetail }) {
  const update = useUpdateIdea(idea.id);
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  const tags = idea.tags ?? [];

  function addTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const tag = value.trim();
    if (tag === "" || tags.includes(tag)) {
      setValue("");
      setAdding(false);
      return;
    }
    update.mutate({ tags: [...tags, tag] }, { onSuccess: () => setAdding(false) });
    setValue("");
  }

  function removeTag(tag: string) {
    update.mutate({ tags: tags.filter((item) => item !== tag) });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-foreground"
        >
          {tag}
          <button
            type="button"
            aria-label={`Remove tag ${tag}`}
            className="rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
            onClick={() => removeTag(tag)}
            disabled={update.isPending}
          >
            <X className="size-3" aria-hidden="true" />
          </button>
        </span>
      ))}
      {adding ? (
        <form onSubmit={addTag} className="flex items-center gap-1">
          <label htmlFor="new-tag" className="sr-only">
            New tag
          </label>
          <Input
            id="new-tag"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="New tag"
            className="h-7 w-28 px-2 text-xs"
            autoFocus
          />
          <Button type="submit" size="sm" variant="ghost" className="h-7 px-2 text-xs">
            Add
          </Button>
        </form>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-muted-foreground"
          onClick={() => setAdding(true)}
          disabled={update.isPending}
        >
          <Plus aria-hidden="true" />
          Add tag
        </Button>
      )}
    </div>
  );
}

function VersionSwitcher({
  versions,
  selected,
  onSelect,
}: {
  versions: IdeaVersionRead[];
  selected: IdeaVersionRead;
  onSelect: (versionNumber: number) => void;
}) {
  if (versions.length <= 1) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label="Switch version">
          v{selected.number} · {formatDate(selected.created_at)}
          <ChevronDown aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Report version</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {versions.map((version) => (
          <DropdownMenuItem key={version.id} onSelect={() => onSelect(version.number)}>
            v{version.number} · {formatDate(version.created_at)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ExportMenu({ ideaId }: { ideaId: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label="Export report">
          <Download aria-hidden="true" />
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <a
            href={apiUrl(`/ideas/${ideaId}/report.md`)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Download Markdown
          </a>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <a
            href={apiUrl(`/ideas/${ideaId}/report.pdf`)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Download PDF
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export interface IdeaHeaderProps {
  idea: IdeaDetail;
  /** Version whose report is on screen; defaults to the latest. */
  selectedVersion: IdeaVersionRead;
  onSelectVersion: (versionNumber: number) => void;
}

/** Idea header: inline title, badges, tags, pin/archive, versions and export. */
export function IdeaHeader({ idea, selectedVersion, onSelectVersion }: IdeaHeaderProps) {
  const update = useUpdateIdea(idea.id);
  const versions = idea.versions ?? [idea.latest_version];
  const archived = idea.archived_at !== null;

  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-full sm:basis-auto">
          <TitleEditor idea={idea} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <StatusBadge status={idea.status} />
            <VerdictBadge verdict={idea.verdict} />
            <ScoreBadge score={idea.overall_score} scale={100} />
            {archived ? <Badge variant="outline">Archived</Badge> : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <VersionSwitcher
            versions={versions}
            selected={selectedVersion}
            onSelect={onSelectVersion}
          />
          <Button
            variant="outline"
            size="sm"
            aria-pressed={idea.pinned}
            aria-label={idea.pinned ? "Unpin idea" : "Pin idea"}
            onClick={() => update.mutate({ pinned: !idea.pinned })}
            disabled={update.isPending}
          >
            {idea.pinned ? <PinOff aria-hidden="true" /> : <Pin aria-hidden="true" />}
            {idea.pinned ? "Pinned" : "Pin"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            aria-label={archived ? "Restore idea" : "Archive idea"}
            onClick={() => update.mutate({ archived: !archived })}
            disabled={update.isPending}
          >
            {archived ? <ArchiveRestore aria-hidden="true" /> : <Archive aria-hidden="true" />}
            {archived ? "Restore" : "Archive"}
          </Button>
          <ExportMenu ideaId={idea.id} />
        </div>
      </div>
      <TagEditor idea={idea} />
    </header>
  );
}
