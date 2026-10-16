// Small helper for calling the FastAPI backend.
// The backend address comes from NEXT_PUBLIC_API_URL in frontend/.env.local.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Calls `${API_URL}${path}` and returns the parsed JSON body.
// Throws ApiError when the response status is not 2xx.
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail ?? `Request failed with status ${res.status}`;
    throw new ApiError(res.status, typeof message === "string" ? message : JSON.stringify(message));
  }

  return res.json() as Promise<T>;
}

export type Health = { status: string; database: string; db_engine: string };

export function getHealth() {
  return apiFetch<Health>("/health");
}
