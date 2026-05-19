"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

/**
 * Acepta invitaciones de Supabase que usan implicit flow (hash-based tokens).
 * El server-side /auth/callback sólo maneja PKCE (?code=); este page maneja
 * el caso donde Supabase redirige con #access_token=... en el hash.
 */
export default function InviteCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session) {
        router.replace("/dashboard");
      }
    });
    return () => subscription.unsubscribe();
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <p className="text-sm text-muted-foreground">Verificando invitación…</p>
    </div>
  );
}
