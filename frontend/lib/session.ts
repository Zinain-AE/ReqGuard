// Server-side session helpers. Only imported by route handlers in app/api/ and by proxy.ts.
//
// The JWT from FastAPI is stored in an httpOnly cookie on the Next.js origin, so browser
// JavaScript can never read it. Route handlers read the cookie and call FastAPI with
// "Authorization: Bearer <token>".

import { NextResponse } from "next/server";

export const TOKEN_COOKIE = "rg_token";

// Address of the FastAPI backend (not secret; the browser no longer calls it directly)
export const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

type TokenResponse = { access_token: string; token_type: string; expires_in: number };

export function backendUnreachable() {
  return NextResponse.json({ detail: "The ReqGuard backend is not reachable." }, { status: 502 });
}

// Logs in at FastAPI and returns a response that sets the token cookie.
// `remember` = false gives a session cookie (deleted when the browser closes).
export async function loginAndSetCookie(email: string, password: string, remember: boolean) {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    return backendUnreachable();
  }

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    return NextResponse.json(body ?? { detail: "Login failed." }, { status: res.status });
  }

  const token = body as TokenResponse;
  const response = NextResponse.json({ ok: true });
  response.cookies.set(TOKEN_COOKIE, token.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    ...(remember ? { maxAge: token.expires_in } : {}),
  });
  return response;
}
