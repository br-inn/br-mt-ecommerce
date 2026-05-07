"use client";

import { useAuth, type AuthUser } from "@/components/auth/auth-provider";

export type CurrentUser = AuthUser;

export interface UseUserResult {
  user: AuthUser | null;
  isLoading: boolean;
  isError: boolean;
  isAuthenticated: boolean;
}

/** Hook canónico — devuelve el usuario aplicativo + flags de estado. */
export function useUser(): UseUserResult {
  const { user, isLoading, isError } = useAuth();
  return {
    user,
    isLoading,
    isError,
    isAuthenticated: !!user,
  };
}

/** Helper boolean: ¿el usuario tiene este `role.code`? */
export function useHasRole(roleCode: string): boolean {
  const { user } = useAuth();
  return user?.role?.code === roleCode;
}
