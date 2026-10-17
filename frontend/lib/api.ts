// Small helper for calling the FastAPI backend from the browser.
// Requests go to the same-origin route /api/backend/<path>, which adds the login token
// (kept in an httpOnly cookie) and forwards to FastAPI. See app/api/backend/[...path]/route.ts.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ loc, msg, ... }]
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return `Request failed with status ${status}`;
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, errorMessage(body, res.status));
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Calls FastAPI `${path}` and returns the parsed JSON body.
// Throws ApiError when the response status is not 2xx; on 401 it also sends the user to /login.
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    return await request<T>(`/api/backend${path}`, init);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401 && typeof window !== "undefined") {
      const next = window.location.pathname + window.location.search;
      // Full page load (not router.push): this helper is not a component, and it drops all client state
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?next=${encodeURIComponent(next)}`;
    }
    throw err;
  }
}

const json = (body: unknown) => JSON.stringify(body);

// ---------- Health ----------

export type Health = { status: string; database: string; db_engine: string };

export function getHealth() {
  return apiFetch<Health>("/health");
}

// ---------- Auth ----------

export type User = { id: number; name: string; email: string; created_at: string };

export function login(email: string, password: string, remember: boolean) {
  return request<{ ok: true }>("/api/auth/login", { method: "POST", body: json({ email, password, remember }) });
}

export function register(name: string, email: string, password: string) {
  return request<{ ok: true }>("/api/auth/register", { method: "POST", body: json({ name, email, password }) });
}

export function logout() {
  return request<{ ok: true }>("/api/auth/logout", { method: "POST" });
}

export function getMe() {
  return apiFetch<User>("/auth/me");
}

// ---------- Projects ----------

export type Project = {
  id: number;
  name: string;
  description: string;
  scope_text: string;
  owner_id: number;
  created_at: string;
  updated_at: string;
};

export type ProjectInput = Pick<Project, "name" | "description" | "scope_text">;

export function listProjects() {
  return apiFetch<Project[]>("/projects");
}

export function createProject(data: ProjectInput) {
  return apiFetch<Project>("/projects", { method: "POST", body: json(data) });
}

export function getProject(id: number | string) {
  return apiFetch<Project>(`/projects/${id}`);
}

export function updateProject(id: number | string, data: Partial<ProjectInput>) {
  return apiFetch<Project>(`/projects/${id}`, { method: "PATCH", body: json(data) });
}

export function deleteProject(id: number | string) {
  return apiFetch<void>(`/projects/${id}`, { method: "DELETE" });
}

// ---------- Team ----------

export const ROLES = ["lead", "developer", "qa"] as const;
export type Role = (typeof ROLES)[number];

export type TeamMember = {
  id: number;
  project_id: number;
  name: string;
  email: string;
  skills: string[];
  role: Role;
  created_at: string;
};

export type TeamMemberInput = Pick<TeamMember, "name" | "email" | "skills" | "role">;

export function listTeam(projectId: number | string) {
  return apiFetch<TeamMember[]>(`/projects/${projectId}/team`);
}

export function addMember(projectId: number | string, data: TeamMemberInput) {
  return apiFetch<TeamMember>(`/projects/${projectId}/team`, { method: "POST", body: json(data) });
}

export function updateMember(projectId: number | string, memberId: number, data: Partial<TeamMemberInput>) {
  return apiFetch<TeamMember>(`/projects/${projectId}/team/${memberId}`, { method: "PATCH", body: json(data) });
}

export function deleteMember(projectId: number | string, memberId: number) {
  return apiFetch<void>(`/projects/${projectId}/team/${memberId}`, { method: "DELETE" });
}
