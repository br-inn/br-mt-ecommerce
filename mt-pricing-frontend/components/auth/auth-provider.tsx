"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import type { Session } from "@supabase/supabase-js";

import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import env from "@/lib/env";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string | null;
  avatarUrl: string | null;
  locale: "es" | "en" | "ar";
  isActive: boolean;
  role: { id: string; code: string; name: string } | null;
  permissions: string[];
}

interface AuthContextValue {
  user: AuthUser | null;
  session: Session | null;
  permissions: string[];
  isLoading: boolean;
  isError: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  session: null,
  permissions: [],
  isLoading: true,
  isError: false,
  refresh: async () => undefined,
  signOut: async () => undefined,
});

interface MeApiResponse {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  locale: "es" | "en" | "ar";
  is_active: boolean;
  role: { id: string; code: string; name: string } | null;
  permissions: string[];
}

function mapMeResponse(data: MeApiResponse): AuthUser {
  return {
    id: data.id,
    email: data.email,
    fullName: data.full_name,
    avatarUrl: data.avatar_url,
    locale: data.locale,
    isActive: data.is_active,
    role: data.role,
    permissions: data.permissions ?? [],
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const supabase = useMemo(() => createSupabaseBrowserClient(), []);

  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const fetchInFlight = useRef(false);

  const fetchProfile = useCallback(
    async (currentSession: Session | null): Promise<void> => {
      if (!currentSession) {
        setUser(null);
        setIsError(false);
        return;
      }
      if (fetchInFlight.current) return;
      fetchInFlight.current = true;
      try {
        const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/me`, {
          headers: {
            Authorization: `Bearer ${currentSession.access_token}`,
            "Content-Type": "application/json",
          },
          cache: "no-store",
        });
        if (res.status === 401) {
          // JWT stale o invalido — limpiar sesion Supabase para que el browser
          // arranque fresh en el proximo login. Evita el loop "/me 401" en
          // cada page load por una sesion cacheada vieja.
          // eslint-disable-next-line no-console
          console.warn(
            "[auth] /me devolvio 401 — invalidando sesion Supabase stale.",
          );
          await supabase.auth.signOut({ scope: "local" });
          setUser(null);
          setIsError(false);
          return;
        }
        if (!res.ok) {
          setIsError(true);
          setUser(null);
          return;
        }
        const data = (await res.json()) as MeApiResponse;
        setUser(mapMeResponse(data));
        setIsError(false);
      } catch {
        setIsError(true);
        setUser(null);
      } finally {
        fetchInFlight.current = false;
      }
    },
    [],
  );

  // Carga inicial + suscripción a cambios de auth state.
  useEffect(() => {
    let mounted = true;

    void (async () => {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;
      setSession(data.session);
      await fetchProfile(data.session);
      setIsLoading(false);
    })();

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      void fetchProfile(newSession);
    });

    return () => {
      mounted = false;
      subscription.subscription.unsubscribe();
    };
  }, [supabase, fetchProfile]);

  // Realtime: force-logout emitido por backend cuando se revoca un rol (ADR-032).
  // El backend inserta una row en `public.force_logout_events` con publication
  // `supabase_realtime` habilitada. RLS asegura que solo recibimos los nuestros,
  // pero filtramos por user_id de todos modos como defensa-en-profundidad.
  useEffect(() => {
    if (!user) return;
    const channel = supabase
      .channel(`force-logout-${user.id}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "force_logout_events",
          filter: `user_id=eq.${user.id}`,
        },
        async (payload: { new?: { reason?: string; user_id?: string } }) => {
          // Defensa-en-profundidad — RLS ya filtra, pero nunca confiar.
          if (payload.new?.user_id !== user.id) return;
          const reason = payload.new?.reason ?? "session_revoked";
          toast.error("Tu sesión fue revocada por un administrador.");
          await supabase.auth.signOut({ scope: "local" });
          // window.location para garantizar reset completo de estado SPA.
          window.location.href = `/login?reason=revoked&message=${encodeURIComponent(reason)}`;
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [supabase, user, router]);

  const refresh = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    setSession(data.session);
    await fetchProfile(data.session);
  }, [supabase, fetchProfile]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    router.replace("/login");
  }, [supabase, router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      session,
      permissions: user?.permissions ?? [],
      isLoading,
      isError,
      refresh,
      signOut,
    }),
    [user, session, isLoading, isError, refresh, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
