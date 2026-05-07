import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import env from "@/lib/env";

/**
 * Auth middleware Supabase — refresh session + route protection.
 *
 * - Hydrata Supabase auth cookies en cada request (cookie rotation).
 * - Redirige a /login si la ruta protegida no tiene session.
 * - Redirige a /dashboard si el user logueado intenta entrar a /login.
 * - Rutas públicas: /login, /reset-password, /auth/callback, /api/health.
 */

const PUBLIC_ROUTES = [
  "/login",
  "/reset-password",
  "/auth/callback",
  "/auth/confirm",
  "/api/health",
];

const AUTH_ENTRY_ROUTES = ["/login", "/reset-password"];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

function isAuthEntryRoute(pathname: string): boolean {
  return AUTH_ENTRY_ROUTES.some((p) => pathname === p);
}

export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({
    request: { headers: request.headers },
  });

  const supabase = createServerClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_KEY,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request: { headers: request.headers } });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // Refresca el token y leemos user (canónico per @supabase/ssr docs).
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, search } = request.nextUrl;

  // 1) Si está logueado y va a /login → mandarlo a /dashboard.
  if (user && isAuthEntryRoute(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  // 2) Si NO está logueado y la ruta no es pública → /login con next=...
  if (!user && !isPublicRoute(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  return response;
}
