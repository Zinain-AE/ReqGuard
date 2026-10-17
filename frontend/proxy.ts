// Runs before every page request (Next.js 16 "proxy", formerly "middleware").
// Optimistic check only: is there a token cookie? The backend still checks the token itself.

import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE } from "@/lib/session";

const PUBLIC_PAGES = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const loggedIn = request.cookies.has(TOKEN_COOKIE);
  const isPublic = PUBLIC_PAGES.includes(pathname);

  if (!loggedIn && !isPublic) {
    const url = new URL("/login", request.url);
    if (pathname !== "/") url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if (loggedIn && isPublic) {
    return NextResponse.redirect(new URL("/projects", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Skip API routes, Next.js internals and files with an extension (favicon, images, ...)
  matcher: ["/((?!api|_next/static|_next/image|.*\\..*).*)"],
};
