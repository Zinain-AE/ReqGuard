"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import TagInput from "@/components/TagInput";
import { ErrorBanner, Label, errorText, inputClass, primaryButton, secondaryButton } from "@/components/ui";
import {
  ROLES,
  addMember,
  deleteMember,
  getProject,
  listTeam,
  updateMember,
  type Project,
  type TeamMember,
  type TeamMemberInput,
} from "@/lib/api";

const EMPTY: TeamMemberInput = { name: "", email: "", skills: [], role: "developer" };

const ROLE_STYLE: Record<TeamMember["role"], string> = {
  lead: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
  developer: "bg-indigo-400/10 text-indigo-300 ring-indigo-400/30",
  qa: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
};

export default function TeamPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState<TeamMemberInput>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([getProject(id), listTeam(id)])
      .then(([p, team]) => {
        setProject(p);
        setMembers(team);
      })
      .catch((err) => setLoadError(errorText(err)));
  }, [id]);

  function resetForm() {
    setForm(EMPTY);
    setEditingId(null);
    setFormError("");
  }

  function startEdit(m: TeamMember) {
    setForm({ name: m.name, email: m.email, skills: m.skills, role: m.role });
    setEditingId(m.id);
    setFormError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim()) {
      setFormError("Name and email are required.");
      return;
    }
    setSaving(true);
    setFormError("");
    const data = { ...form, name: form.name.trim(), email: form.email.trim() };
    try {
      if (editingId === null) {
        const member = await addMember(id, data);
        setMembers((list) => [...list, member]);
      } else {
        const member = await updateMember(id, editingId, data);
        setMembers((list) => list.map((m) => (m.id === member.id ? member : m)));
      }
      resetForm();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(m: TeamMember) {
    if (!confirm(`Remove ${m.name} from the team?`)) return;
    try {
      await deleteMember(id, m.id);
      setMembers((list) => list.filter((x) => x.id !== m.id));
      if (editingId === m.id) resetForm();
    } catch (err) {
      setFormError(errorText(err));
    }
  }

  if (loadError) {
    return (
      <div className="max-w-3xl space-y-4">
        <ErrorBanner message={loadError} />
        <Link href="/projects" className="text-sm text-indigo-300 hover:text-indigo-200">
          ← Back to projects
        </Link>
      </div>
    );
  }
  if (!project) return <p className="text-sm text-zinc-500">Loading team...</p>;

  return (
    <div className="max-w-5xl">
      <Link href={`/projects/${id}`} className="text-sm text-zinc-400 hover:text-zinc-100">
        ← {project.name}
      </Link>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">Team</h1>
      <p className="mt-1.5 text-sm text-zinc-400">
        People working on this project. Skills are used later to suggest who should get each task.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-2xl border border-white/10 bg-zinc-900/60 p-6">
        <h2 className="text-lg font-medium">{editingId === null ? "Add member" : "Edit member"}</h2>
        <div className="grid gap-4 sm:grid-cols-[1fr_1fr_10rem]">
          <div>
            <Label htmlFor="member-name">Name</Label>
            <input
              id="member-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              maxLength={100}
              className={inputClass}
            />
          </div>
          <div>
            <Label htmlFor="member-email">Email</Label>
            <input
              id="member-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className={inputClass}
            />
          </div>
          <div>
            <Label htmlFor="member-role">Role</Label>
            <select
              id="member-role"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as TeamMember["role"] })}
              className={inputClass}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r === "qa" ? "QA" : r[0].toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <Label htmlFor="member-skills">Skills</Label>
          <TagInput
            id="member-skills"
            value={form.skills}
            onChange={(skills) => setForm({ ...form, skills })}
            placeholder="Type a skill and press Enter (e.g. React, Python, SQL)"
          />
        </div>
        <ErrorBanner message={formError} />
        <div className="flex gap-3">
          <button type="submit" disabled={saving} className={primaryButton}>
            {saving ? "Saving..." : editingId === null ? "Add member" : "Save changes"}
          </button>
          {editingId !== null && (
            <button type="button" onClick={resetForm} className={secondaryButton}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <div className="mt-8 overflow-x-auto rounded-2xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/80 text-xs uppercase tracking-wider text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Skills</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {members.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                  No team members yet.
                </td>
              </tr>
            )}
            {members.map((m) => (
              <tr key={m.id} className={editingId === m.id ? "bg-indigo-500/5" : ""}>
                <td className="px-4 py-3 font-medium text-zinc-100">{m.name}</td>
                <td className="px-4 py-3 text-zinc-400">{m.email}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${ROLE_STYLE[m.role]}`}>
                    {m.role === "qa" ? "QA" : m.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {m.skills.length === 0 && <span className="text-zinc-600">—</span>}
                    {m.skills.map((s) => (
                      <span key={s} className="rounded-md bg-white/5 px-1.5 py-0.5 text-xs text-zinc-300">
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button onClick={() => startEdit(m)} className="text-xs text-indigo-300 hover:text-indigo-200">
                    Edit
                  </button>
                  <button onClick={() => handleDelete(m)} className="ml-3 text-xs text-rose-300 hover:text-rose-200">
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
