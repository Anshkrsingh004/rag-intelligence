import { useCallback, useEffect, useRef, useState } from "react";
import type { ConversationSummary, QueryResponse } from "../types";
import type { Turn } from "../components/ComparisonBlock";
import {
  BackendOfflineError,
  addMessage,
  createConversation,
  deleteConversation as apiDeleteConversation,
  getConversation,
  listConversations,
  postQuery,
  renameConversation as apiRenameConversation,
} from "../lib/api";

function uid(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

export interface UseConversations {
  conversations: ConversationSummary[]; // sidebar list
  activeId: number | null; // open conversation (null = a fresh, unsaved "New chat")
  turns: Turn[]; // the active conversation's messages, rendered in the main view
  busy: boolean;
  newChat: () => void;
  openConversation: (id: number) => Promise<void>;
  sendMessage: (query: string) => Promise<void>;
  removeConversation: (id: number) => Promise<void>;
  rename: (id: number, title: string) => Promise<void>;
}

/**
 * All conversation state and operations, ChatGPT-style.
 *  - Signed in: conversations are persisted; the sidebar lists them and each
 *    session's messages append to one conversation.
 *  - Signed out: a single ephemeral in-memory session (nothing persisted).
 *
 * The compute call (`postQuery`) is unchanged and separate from persistence.
 */
export function useConversations(
  token: string | null,
  onError: (msg: string) => void,
): UseConversations {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const busy = turns.some((t) => t.status === "loading");

  // Stable error reporter so the load effect depends only on `token`.
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // On any auth change: reset to a fresh chat, then load (or clear) the list.
  useEffect(() => {
    setActiveId(null);
    setTurns([]);
    if (!token) {
      setConversations([]);
      return;
    }
    let active = true;
    listConversations(token)
      .then((cs) => active && setConversations(cs))
      .catch(() => active && onErrorRef.current("Couldn't load your conversations."));
    return () => {
      active = false;
    };
  }, [token]);

  const newChat = useCallback(() => {
    setActiveId(null);
    setTurns([]);
  }, []);

  const openConversation = useCallback(
    async (id: number) => {
      if (!token) return;
      setActiveId(id);
      try {
        const detail = await getConversation(token, id);
        setTurns(
          detail.messages.map((m) => ({
            id: `msg-${m.id}`,
            query: m.query,
            status: "done" as const,
            data: m.payload,
          })),
        );
      } catch {
        onErrorRef.current("Couldn't open that conversation.");
      }
    },
    [token],
  );

  const removeConversation = useCallback(
    async (id: number) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setActiveId((cur) => (cur === id ? null : cur));
      setTurns((cur) => (activeId === id ? [] : cur));
      if (token) {
        try {
          await apiDeleteConversation(token, id);
        } catch {
          onErrorRef.current("Couldn't delete on the server.");
        }
      }
    },
    [token, activeId],
  );

  const rename = useCallback(
    async (id: number, title: string) => {
      if (!token) return;
      try {
        const updated = await apiRenameConversation(token, id, title);
        setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
      } catch {
        onErrorRef.current("Couldn't rename the conversation.");
      }
    },
    [token],
  );

  const sendMessage = useCallback(
    async (query: string) => {
      if (busy) return;
      const localId = uid();
      setTurns((prev) => [...prev, { id: localId, query, status: "loading" }]);

      // 1) Compute the three-panel answer (stateless; unchanged endpoint).
      let payload: QueryResponse;
      try {
        payload = await postQuery(query);
      } catch (err) {
        const offline = err instanceof BackendOfflineError;
        setTurns((prev) =>
          prev.map((t) => (t.id === localId ? { ...t, status: offline ? "offline" : "error" } : t)),
        );
        onErrorRef.current(
          offline
            ? "🔌 Backend offline — run: cd backend && python run.py"
            : `Error: ${(err as Error).message}`,
        );
        return;
      }
      setTurns((prev) =>
        prev.map((t) => (t.id === localId ? { ...t, status: "done", data: payload } : t)),
      );

      // 2) Persist under the active conversation (signed-in only).
      if (!token) return;
      try {
        let convId = activeId;
        if (convId === null) {
          const conv = await createConversation(token, query); // title derived from first message
          convId = conv.id;
          setActiveId(convId);
          setConversations((prev) => [conv, ...prev]);
        }
        await addMessage(token, convId, query, payload);
        // Move the conversation to the top with a fresh timestamp + count.
        setConversations((prev) => {
          const target = prev.find((c) => c.id === convId);
          if (!target) return prev;
          const bumped: ConversationSummary = {
            ...target,
            updated_at: new Date().toISOString(),
            message_count: target.message_count + 1,
          };
          return [bumped, ...prev.filter((c) => c.id !== convId)];
        });
      } catch {
        onErrorRef.current("Answer ready, but couldn't save it to your conversation.");
      }
    },
    [busy, token, activeId],
  );

  return {
    conversations,
    activeId,
    turns,
    busy,
    newChat,
    openConversation,
    sendMessage,
    removeConversation,
    rename,
  };
}
