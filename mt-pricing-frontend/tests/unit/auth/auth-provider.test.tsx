import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import * as React from "react";

// ---- Setup mocks: env, supabase client, fetch, next/navigation -------------
vi.mock("@/lib/env", () => ({
  default: {
    NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
    NEXT_PUBLIC_SUPABASE_KEY: "anon-test",
    NEXT_PUBLIC_BACKEND_URL: "http://localhost:8000",
    NEXT_PUBLIC_DEFAULT_LOCALE: "es",
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const getSessionMock = vi.fn();
const onAuthStateChangeMock = vi.fn();
const signOutMock = vi.fn().mockResolvedValue({ error: null });
const channelOn = vi.fn();
const channel = {
  on: channelOn,
  subscribe: vi.fn().mockReturnValue({}),
};
channelOn.mockReturnValue(channel);

const supabaseMock = {
  auth: {
    getSession: getSessionMock,
    onAuthStateChange: onAuthStateChangeMock,
    signOut: signOutMock,
  },
  channel: vi.fn().mockReturnValue(channel),
  removeChannel: vi.fn(),
};

vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => supabaseMock,
  createClient: () => supabaseMock,
}));

import {
  AuthProvider,
  useAuth,
} from "@/components/auth/auth-provider";

function Probe() {
  const { user, isLoading, session } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="user-email">{user?.email ?? ""}</span>
      <span data-testid="session-token">{session?.access_token ?? ""}</span>
    </div>
  );
}

describe("AuthProvider", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    getSessionMock.mockReset();
    onAuthStateChangeMock.mockReset();
    onAuthStateChangeMock.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("expone user=null y isLoading=false cuando no hay sesión", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false"),
    );
    expect(screen.getByTestId("user-email").textContent).toBe("");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("hace fetch a /api/v1/me con Authorization Bearer y rellena el usuario", async () => {
    getSessionMock.mockResolvedValue({
      data: {
        session: { access_token: "tok-123", user: { id: "u-1" } },
      },
    });
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "u-1",
        email: "comercial@mt.test",
        full_name: "MT Tester",
        avatar_url: null,
        locale: "es",
        is_active: true,
        role: { id: "r1", code: "comercial", name: "Comercial" },
        permissions: ["products:read"],
      }),
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("user-email").textContent).toBe("comercial@mt.test"),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer tok-123",
        }),
      }),
    );
  });

  it("subscribe a onAuthStateChange y propaga nueva sesión", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    let captured: ((evt: string, s: unknown) => void) | undefined;
    onAuthStateChangeMock.mockImplementation((cb) => {
      captured = cb;
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    });
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "u-2",
        email: "new@mt.test",
        full_name: null,
        avatar_url: null,
        locale: "es",
        is_active: true,
        role: null,
        permissions: [],
      }),
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false"),
    );

    await act(async () => {
      captured?.("SIGNED_IN", {
        access_token: "tok-new",
        user: { id: "u-2" },
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("user-email").textContent).toBe("new@mt.test"),
    );
  });
});
