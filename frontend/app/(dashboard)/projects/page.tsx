"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner, Label, errorText, inputClass, primaryButton, secondaryButton } from "@/components/ui";
import { createProject, listProjects, type Project, type ProjectInput } from "@/lib/api";

const EMPTY: ProjectInput = { name: "", description: "", scope_text: "" };

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProjectInput>(EMPTY);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err) => setError(errorText(err)));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setFormError("Project name is required.");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      const project = await createProject({ ...form, name: form.name.trim() });
      setProjects((list) => [project, ...(list ?? [])]);
      setForm(EMPTY);
      setShowForm(false);
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1.5 text-sm text-zinc-400">Your projects and their team members.</p>
        </div>
        {!showForm && (
          <button onClick={() => setShowForm(true)} className={primaryButton}>
            New project
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-6 space-y-4 rounded-2xl border border-white/10 bg-zinc-900/60 p-6">
          <h2 className="text-lg font-medium">New project</h2>
          <div>
            <Label htmlFor="name">Name</Label>
            <input
              id="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Acme customer portal"
              maxLength={200}
              className={inputClass}
              autoFocus
            />
          </div>
          <div>
            <Label htmlFor="description">Description</Label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              placeholder="Short summary of the project"
              className={inputClass}
            />
          </div>
          <div>
            <Label htmlFor="scope">Scope</Label>
            <textarea
              id="scope"
              value={form.scope_text}
              onChange={(e) => setForm({ ...form, scope_text: e.target.value })}
              rows={4}
              placeholder="What the client agreed to build. Used later to flag possible out-of-scope requests."
              className={inputClass}
            />
          </div>
          <ErrorBanner message={formError} />
          <div className="flex gap-3">
            <button type="submit" disabled={saving} className={primaryButton}>
              {saving ? "Creating..." : "Create project"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setFormError("");
              }}
              className={secondaryButton}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="mt-8">
        <ErrorBanner message={error} />
        {projects === null && !error && <p className="text-sm text-zinc-500">Loading projects...</p>}
        {projects?.length === 0 && (
          <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-zinc-500">
            No projects yet. Create your first one.
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          {projects?.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 transition hover:border-indigo-400/40 hover:bg-zinc-900"
            >
              <h3 className="font-medium text-zinc-100">{p.name}</h3>
              <p className="mt-1 line-clamp-2 text-sm text-zinc-400">{p.description || "No description"}</p>
              <p className="mt-3 text-xs text-zinc-500">Created {new Date(p.created_at).toLocaleDateString()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
