"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ChannelState =
  | "inactive"
  | "pre_launch"
  | "pilot"
  | "live"
  | "paused"
  | "deprecated";

export interface Channel {
  id: string;
  code: string;
  name: string;
  state: ChannelState;
  pilot_with_warnings: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChannelStateHistoryEntry {
  id: string;
  channel_id: string;
  from_state: ChannelState | null;
  to_state: ChannelState;
  actor_user_id: string | null;
  comment: string | null;
  pilot_with_warnings: boolean;
  created_at: string;
}

export interface ChannelTransitionRequest {
  target_state: ChannelState;
  subset_skus?: string[];
  comment?: string;
  override_warnings?: boolean;
}

export interface ChannelTransitionResponse {
  channel_id: string;
  channel_code: string;
  from_state: ChannelState;
  to_state: ChannelState;
  pilot_with_warnings: string[];
  missing_skus: string[];
  history_id: string;
}

// ---------------------------------------------------------------------------
// Valid transitions FSM
// ---------------------------------------------------------------------------

export const VALID_TRANSITIONS: Record<ChannelState, ChannelState[]> = {
  inactive: ["pre_launch"],
  pre_launch: ["pilot", "inactive"],
  pilot: ["live", "inactive"],
  live: ["paused", "deprecated"],
  paused: ["live", "deprecated"],
  deprecated: [],
};

// ---------------------------------------------------------------------------
// Static fallback data (4 known channels)
// ---------------------------------------------------------------------------

export const STATIC_CHANNELS: Channel[] = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    code: "AMAZON_UAE",
    name: "Amazon UAE",
    state: "live",
    pilot_with_warnings: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    code: "NOON_UAE",
    name: "Noon UAE",
    state: "pilot",
    pilot_with_warnings: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    code: "B2C_DIRECT",
    name: "B2C Direct",
    state: "pre_launch",
    pilot_with_warnings: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000004",
    code: "B2B_DIRECT",
    name: "B2B Direct",
    state: "inactive",
    pilot_with_warnings: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ChannelsAdminApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ChannelsAdminApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// authedFetch helper
// ---------------------------------------------------------------------------

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new ChannelsAdminApiError(
      res.status,
      detail,
      res.statusText || "Error desconocido",
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// API object
// ---------------------------------------------------------------------------

export const channelsAdminApi = {
  /** GET /channels — lista todos los canales. Fallback a estáticos si 404. */
  list: (): Promise<Channel[]> =>
    authedFetch<Channel[]>("/api/v1/channels"),

  /** GET /channels/{id}/history */
  history: (channelId: string): Promise<ChannelStateHistoryEntry[]> =>
    authedFetch<ChannelStateHistoryEntry[]>(
      `/api/v1/channels/${channelId}/history`,
    ),

  /** POST /channels/{id}/transition */
  transition: (
    channelId: string,
    payload: ChannelTransitionRequest,
  ): Promise<ChannelTransitionResponse> =>
    authedFetch<ChannelTransitionResponse>(
      `/api/v1/channels/${channelId}/transition`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
