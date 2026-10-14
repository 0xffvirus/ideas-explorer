"use client";

import { useEffect, useRef, useState } from "react";
import { Pencil } from "lucide-react";
import { cn } from "cn";

export function TitleEditor({
  title,
  onSave,
  className,
}: {
  title: string;
  onSave: (title: string) => void;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function commit() {
    const next = value.trim();
    setEditing(false);
    if (next && next !== title) onSave(next);
    else setValue(title);
  }

  if (!editing) {
    return (
      <span className={cn("group inline-flex items-start gap-2", className)}>
        <h1 className="t-section max-w-4xl">{title}</h1>
        <button
          type="button"
          onClick={() => {
            setValue(title);
            setEditing(true);
          }}
          className="icon-btn mt-2 size-9 min-h-9 min-w-9 shrink-0 opacity-60 group-hover:opacity-100"
          aria-label="Edit title"
          data-testid="edit-title"
        >
          <Pencil size={14} aria-hidden="true" />
        </button>
      </span>
    );
  }

  return (
    <input
      ref={inputRef}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") commit();
        if (event.key === "Escape") {
          setValue(title);
          setEditing(false);
        }
      }}
      maxLength={80}
      aria-label="Idea title"
      className={cn(
        "t-section w-full max-w-4xl rounded-field border border-line-control bg-surface px-3 py-1",
        className,
      )}
      data-testid="title-input"
    />
  );
}
