// Forwards /api/backend/<path> to FastAPI <path>, adding the bearer token from the httpOnly cookie.
// The browser only ever talks to this same-origin route, so the token never reaches client JavaScript.

import { NextResponse, type NextRequest } from "next/server";
import { BACKEND_URL, TOKEN_COOKIE, backendUnreachable } from "@/lib/session";

type Context = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params;
  const url = `${BACKEND_URL}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);

  let res: Response;
  try {
    res = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });
  } catch {
    return backendUnreachable();
  }

  const body = res.status === 204 ? null : await res.arrayBuffer();
  const response = new NextResponse(body, { status: res.status });
  const resType = res.headers.get("content-type");
  if (resType) response.headers.set("content-type", resType);

  // Token expired or invalid: drop the cookie so proxy.ts sends the user to /login
  if (res.status === 401) response.cookies.delete(TOKEN_COOKIE);
  return response;
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
