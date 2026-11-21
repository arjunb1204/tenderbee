import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/vault",
  "/audit",
  "/corrigendum",
  "/settings",
];

const AUTH_PAGES = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasAccessToken = Boolean(
    request.cookies.get("access_token")?.value ||
    request.cookies.get("tenderbee_access")?.value
  );
  const hasRefreshToken = Boolean(
    request.cookies.get("refresh_token")?.value ||
    request.cookies.get("tenderbee_refresh")?.value
  );

  const isAuthenticated = hasAccessToken || hasRefreshToken;

  // 1. If accessing a protected route without any auth token cookie -> redirect to /login
  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isProtected && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 2. If logged in and visiting login or register -> redirect to /dashboard
  const isAuthPage = AUTH_PAGES.some((page) => pathname.startsWith(page));
  if (isAuthPage && hasAccessToken) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export default proxy;

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/vault/:path*",
    "/audit/:path*",
    "/corrigendum/:path*",
    "/settings/:path*",
    "/login",
    "/register",
  ],
};
