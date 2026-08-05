import type {
  AuthResponse,
  ConversationDetail,
  ConversationSummary,
  Health,
  MessageRecord,
  QueryResponse,
  User,
} from "../types";

/**
 * Error thrown when the backend is unreachable (vs. an error it returned).
 * Lets the UI show the friendly "start the backend" panel.
 */
export class BackendOfflineError extends Error {
  constructor() {
    super("Backend offline");
    this.name = "BackendOfflineError";
  }
}

/**
 * In production the frontend (Vercel) and backend (Cloud Run) live on different
 * origins, so every request is prefixed with VITE_API_BASE_URL. In local dev the
 * var is unset, requests stay relative, and Vite's proxy forwards /api/* to the
 * backend on :8000 (see vite.config.ts).
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const api = (path: string) => `${API_BASE}${path}`;

export async function postQuery(query: string, signal?: AbortSignal): Promise<QueryResponse> {
  let resp: Response;
  try {
    resp = await fetch(api("/api/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal,
    });
  } catch {
    // Network-level failure — the server isn't running / not reachable.
    throw new BackendOfflineError();
  }

  if (resp.status === 502 || resp.status === 503 || resp.status === 504) {
    throw new BackendOfflineError();
  }
  if (!resp.ok) {
    let detail = `Server error ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore parse failure */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as QueryResponse;
}

export async function getHealth(): Promise<Health | null> {
  try {
    const resp = await fetch(api("/api/health"));
    if (!resp.ok) return null;
    return (await resp.json()) as Health;
  } catch {
    return null;
  }
}

// ── Auth + chats ───────────────────────────────────────────────
async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

const authHeaders = (token: string) => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${token}`,
});

export async function register(email: string, password: string): Promise<AuthResponse> {
  const resp = await fetch(api("/api/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return jsonOrThrow<AuthResponse>(resp);
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const resp = await fetch(api("/api/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return jsonOrThrow<AuthResponse>(resp);
}

/** Returns the configured Google client id, or null when Google sign-in is off. */
export async function getGoogleClientId(): Promise<string | null> {
  try {
    const resp = await fetch(api("/api/auth/config"));
    if (!resp.ok) return null;
    const body = (await resp.json()) as { google_client_id: string | null };
    return body.google_client_id ?? null;
  } catch {
    return null;
  }
}

export async function googleAuth(credential: string): Promise<AuthResponse> {
  const resp = await fetch(api("/api/auth/google"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  return jsonOrThrow<AuthResponse>(resp);
}

/** Validate a stored token; returns the user, or null if the token is invalid. */
export async function fetchMe(token: string): Promise<User | null> {
  try {
    const resp = await fetch(api("/api/auth/me"), { headers: authHeaders(token) });
    if (!resp.ok) return null;
    return (await resp.json()) as User;
  } catch {
    return null;
  }
}

// ── Conversations ──────────────────────────────────────────────
export async function listConversations(token: string): Promise<ConversationSummary[]> {
  return jsonOrThrow<ConversationSummary[]>(
    await fetch(api("/api/conversations"), { headers: authHeaders(token) }),
  );
}

export async function createConversation(
  token: string,
  firstMessage?: string,
): Promise<ConversationSummary> {
  return jsonOrThrow<ConversationSummary>(
    await fetch(api("/api/conversations"), {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ first_message: firstMessage ?? null }),
    }),
  );
}

export async function getConversation(token: string, id: number): Promise<ConversationDetail> {
  return jsonOrThrow<ConversationDetail>(
    await fetch(api(`/api/conversations/${id}`), { headers: authHeaders(token) }),
  );
}

export async function addMessage(
  token: string,
  conversationId: number,
  query: string,
  payload: QueryResponse,
): Promise<MessageRecord> {
  return jsonOrThrow<MessageRecord>(
    await fetch(api(`/api/conversations/${conversationId}/messages`), {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ query, payload }),
    }),
  );
}

export async function renameConversation(
  token: string,
  id: number,
  title: string,
): Promise<ConversationSummary> {
  return jsonOrThrow<ConversationSummary>(
    await fetch(api(`/api/conversations/${id}`), {
      method: "PATCH",
      headers: authHeaders(token),
      body: JSON.stringify({ title }),
    }),
  );
}

export async function deleteConversation(token: string, id: number): Promise<void> {
  const resp = await fetch(api(`/api/conversations/${id}`), {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!resp.ok && resp.status !== 204) throw new Error(`Delete failed (${resp.status})`);
}
