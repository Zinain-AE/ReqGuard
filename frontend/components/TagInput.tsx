"use client";

import { useState } from "react";

type Props = {
  id?: string;
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
};

// Text box that turns typed words into tags.
// Enter or comma adds a tag, Backspace on an empty box removes the last one,
// pasting "a, b, c" adds three tags. Duplicates (any letter case) are ignored.
export default function TagInput({ id, value, onChange, placeholder }: Props) {
  const [text, setText] = useState("");

  function addTags(raw: string) {
    const next = [...value];
    for (const part of raw.split(",")) {
      const tag = part.trim().replace(/\s+/g, " ");
      if (tag && !next.some((t) => t.toLowerCase() === tag.toLowerCase())) next.push(tag);
    }
    if (next.length !== value.length) onChange(next);
    setText("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTags(text);
    } else if (e.key === "Backspace" && !text && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text");
    if (pasted.includes(",")) {
      e.preventDefault();
      addTags(text + pasted);
    }
  }

  return (
    <div className="flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950/60 px-2 py-1.5 transition focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-500/20">
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-md bg-indigo-500/15 py-0.5 pr-1 pl-2 text-xs text-indigo-200"
        >
          {tag}
          <button
            type="button"
            onClick={() => onChange(value.filter((t) => t !== tag))}
            aria-label={`Remove ${tag}`}
            className="rounded px-1 text-indigo-300 hover:bg-indigo-500/20 hover:text-white"
          >
            ×
          </button>
        </span>
      ))}
      <input
        id={id}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => text.trim() && addTags(text)}
        placeholder={value.length ? "" : placeholder}
        className="min-w-24 flex-1 bg-transparent px-1 py-0.5 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none"
      />
    </div>
  );
}
