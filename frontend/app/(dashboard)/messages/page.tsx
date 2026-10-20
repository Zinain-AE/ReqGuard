"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import NoProjectSelected from "@/components/NoProjectSelected";
import SourceBadge, { sourceLabel } from "@/components/SourceBadge";
import { ErrorBanner, errorText, inputClass, secondaryButton } from "@/components/ui";
import { MESSAGE_SOURCES, listMessages, type MessageFilters, type MessagePage } from "@/lib/api";
import { useSelectedProject } from "@/lib/selectedProject";

const PAGE_SIZE = 50;
const SEARCH_DELAY_MS = 350;
// Filters kept in the URL, so a filtered view can be reloaded or shared
const FILTER_KEYS = ["source", "author", "q", "date_from", "date_to"] as const;

export default function MessagesPage() {
  return (
    <div className="max-w-6xl">
      <h1 className="text-2xl font-semibold tracking-tight">Messages</h1>
      <p className="mt-1.5 text-sm text-zinc-400">All imported client messages of the selected project.</p>
      {/* useSearchParams needs a Suspense boundary */}
      <Suspense fallback={<p className="mt-8 text-sm text-zinc-500">Loading...</p>}>
        <MessagesForSelectedProject />
      </Suspense>
    </div>
  );
}

function MessagesForSelectedProject() {
  const projectId = useSelectedProject();
  return projectId ? <MessagesView key={projectId} projectId={projectId} /> : <NoProjectSelected />;
}

function MessagesView({ projectId }: { projectId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filters: MessageFilters = {
    ...Object.fromEntries(FILTER_KEYS.map((k) => [k, searchParams.get(k) ?? ""])),
    page: Math.max(1, Number(searchParams.get("page")) || 1),
    page_size: PAGE_SIZE,
  };
  const queryKey = `${projectId}?${searchParams.toString()}`;

  // Text boxes update the URL after a short pause in typing
  const [authorText, setAuthorText] = useState(filters.author ?? "");
  const [searchText, setSearchText] = useState(filters.q ?? "");

  const [result, setResult] = useState<{ key: string; data?: MessagePage; error?: string } | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  function updateUrl(changes: Record<string, string | number>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === "" || value === 1) params.delete(key);
      else params.set(key, String(value));
    }
    if (!("page" in changes)) params.delete("page"); // a new filter starts at page 1
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      const author = authorText.trim();
      const q = searchText.trim();
      if (author !== (searchParams.get("author") ?? "") || q !== (searchParams.get("q") ?? "")) {
        updateUrl({ author, q });
      }
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to typing
  }, [authorText, searchText]);

  useEffect(() => {
    let cancelled = false;
    listMessages(projectId, filters)
      .then((data) => !cancelled && setResult({ key: queryKey, data }))
      .catch((err) => !cancelled && setResult({ key: queryKey, error: errorText(err) }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- queryKey covers projectId and all filters
  }, [queryKey]);

  const loading = result?.key !== queryKey;
  const data = result?.data;
  const hasFilters = FILTER_KEYS.some((k) => searchParams.get(k));

  function clearFilters() {
    setAuthorText("");
    setSearchText("");
    router.replace(pathname, { scroll: false });
  }

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <>
      <div className="mt-6 grid gap-3 rounded-2xl border border-white/10 bg-zinc-900/60 p-4 sm:grid-cols-2 lg:grid-cols-[10rem_1fr_1fr_9.5rem_9.5rem_auto]">
        <FilterField label="Source" htmlFor="f-source">
          <select
            id="f-source"
            value={filters.source}
            onChange={(e) => updateUrl({ source: e.target.value })}
            className={inputClass}
          >
            <option value="">All sources</option>
            {MESSAGE_SOURCES.map((s) => (
              <option key={s} value={s}>
                {sourceLabel(s)}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Author" htmlFor="f-author">
          <input
            id="f-author"
            value={authorText}
            onChange={(e) => setAuthorText(e.target.value)}
            placeholder="Any author"
            maxLength={200}
            className={inputClass}
          />
        </FilterField>
        <FilterField label="Search text" htmlFor="f-q">
          <input
            id="f-q"
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="e.g. delivery"
            maxLength={200}
            className={inputClass}
          />
        </FilterField>
        <FilterField label="From" htmlFor="f-from">
          <input
            id="f-from"
            type="date"
            value={filters.date_from}
            onChange={(e) => updateUrl({ date_from: e.target.value })}
            className={`${inputClass} [color-scheme:dark]`}
          />
        </FilterField>
        <FilterField label="To" htmlFor="f-to">
          <input
            id="f-to"
            type="date"
            value={filters.date_to}
            onChange={(e) => updateUrl({ date_to: e.target.value })}
            className={`${inputClass} [color-scheme:dark]`}
          />
        </FilterField>
        <div className="flex items-end">
          <button onClick={clearFilters} disabled={!hasFilters} className={`${secondaryButton} w-full disabled:opacity-40`}>
            Clear
          </button>
        </div>
      </div>

      {result?.error && (
        <div className="mt-4">
          <ErrorBanner message={result.error} />
        </div>
      )}

      <div
        className={`mt-6 overflow-x-auto rounded-2xl border border-white/10 transition-opacity ${loading && data ? "opacity-60" : ""}`}
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/80 text-xs uppercase tracking-wider text-zinc-500">
            <tr>
              <th className="w-44 px-4 py-3 font-medium">Time</th>
              <th className="w-40 px-4 py-3 font-medium">Source</th>
              <th className="w-40 px-4 py-3 font-medium">Author</th>
              <th className="px-4 py-3 font-medium">Text</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {!data && loading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-zinc-500">
                  Loading messages...
                </td>
              </tr>
            )}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-zinc-500">
                  {hasFilters ? (
                    "No messages match these filters."
                  ) : (
                    <>
                      No messages yet.{" "}
                      <Link href="/sources" className="text-indigo-300 hover:text-indigo-200">
                        Upload chat exports or files
                      </Link>{" "}
                      on the Sources page.
                    </>
                  )}
                </td>
              </tr>
            )}
            {data?.items.map((m) => {
              const open = expanded.has(m.id);
              return (
                <tr key={m.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-3 text-zinc-400 tabular-nums">
                    {new Date(m.sent_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                  </td>
                  <td className="px-4 py-3">
                    <SourceBadge source={m.source} />
                    {m.channel && (
                      <p className="mt-1 max-w-[9rem] truncate text-xs text-zinc-500" title={m.channel}>
                        {m.channel}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-zinc-200">{m.author || <span className="text-zinc-600">—</span>}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggle(m.id)}
                      title={open ? "Click to collapse" : "Click to show all"}
                      className={`w-full cursor-pointer whitespace-pre-line text-left text-zinc-100 ${open ? "" : "line-clamp-3"}`}
                    >
                      {m.text}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data && data.total > 0 && (
        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onPage={(page) => updateUrl({ page })}
        />
      )}
    </>
  );
}

function FilterField({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-zinc-400">
        {label}
      </label>
      {children}
    </div>
  );
}

function Pagination(props: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const { page, pageSize, total, onPage } = props;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  const lastPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="mt-4 flex items-center justify-between text-sm text-zinc-400">
      <p className="tabular-nums">
        {first <= total ? `${first}–${last}` : "0"} of {total}
      </p>
      <div className="flex items-center gap-2">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1} className={`${secondaryButton} disabled:opacity-40`}>
          ← Previous
        </button>
        <span className="px-2 tabular-nums">
          Page {page} of {lastPage}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= lastPage}
          className={`${secondaryButton} disabled:opacity-40`}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
