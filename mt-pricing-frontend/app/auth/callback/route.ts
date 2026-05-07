import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

/**
 * Auth callback — intercambia `code` (PKCE) por session y setea cookies.
 *
 * Usado por:
 * - Magic link → Supabase redirige aquí con `code` y `next`.
 * - Reset password → idem.
 * - OAuth (futuro).
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const url = request.nextUrl;
  const code = url.searchParams.get("code");
  const nextPath = url.searchParams.get("next") ?? "/dashboard";

  if (!code) {
    const redirect = url.clone();
    redirect.pathname = "/login";
    redirect.search = "?reason=missing-code";
    return NextResponse.redirect(redirect);
  }

  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  const redirect = url.clone();
  redirect.search = "";
  if (error) {
    redirect.pathname = "/login";
    redirect.search = `?reason=callback-error&message=${encodeURIComponent(error.message)}`;
    return NextResponse.redirect(redirect);
  }

  redirect.pathname = nextPath.startsWith("/") ? nextPath : `/${nextPath}`;
  return NextResponse.redirect(redirect);
}
