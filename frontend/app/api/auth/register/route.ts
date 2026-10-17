import { NextResponse, type NextRequest } from "next/server";
import { BACKEND_URL, backendUnreachable, loginAndSetCookie } from "@/lib/session";

// POST /api/auth/register  { name, email, password }
// Creates the account at FastAPI, then logs in so the user lands on the app signed in.
export async function POST(request: NextRequest) {
  const { name, email, password } = await request.json().catch(() => ({}));

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
      cache: "no-store",
    });
  } catch {
    return backendUnreachable();
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    return NextResponse.json(body ?? { detail: "Registration failed." }, { status: res.status });
  }

  return loginAndSetCookie(String(email), String(password), false);
}
