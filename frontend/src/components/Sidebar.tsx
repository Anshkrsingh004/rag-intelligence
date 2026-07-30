import type { ConversationSummary } from "../types";
import { timeAgo } from "../lib/format";

interface Props {
  conversations: ConversationSummary[];
  open: boolean;
  activeId: number | null;
  authed: boolean;
  onNewChat: () => void;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
  onClose: () => void;
  onSignIn: () => void;
}

/**
 * Recent Chats: one card per conversation (session), newest activity first.
 * Collapsible column on desktop, slide-over on mobile.
 */
export function Sidebar({
  conversations,
  open,
  activeId,
  authed,
  onNewChat,
  onOpen,
  onDelete,
  onClose,
  onSignIn,
}: Props) {
  return (
    <>
      {open && (
        <button
          aria-label="Close sidebar"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
        />
      )}

      <aside
        className={`glass fixed inset-y-0 left-0 z-40 flex h-full flex-col border-r border-border
          transition-[transform,width] duration-300 ease-out
          md:static md:translate-x-0
          ${open
            ? "w-72 translate-x-0"
            : "w-72 -translate-x-full md:w-0 md:overflow-hidden md:border-r-0"}`}
      >
        <div className="flex h-full w-72 flex-col">
          {/* Header + New chat */}
          <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-3">
            <button
              onClick={onNewChat}
              className="flex flex-1 items-center gap-2 rounded-xl border border-border px-3 py-2 text-[13px] font-semibold text-ink transition-colors hover:border-accent/60 hover:text-accent"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              New chat
            </button>
            <button
              onClick={onClose}
              aria-label="Collapse sidebar"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[15px] text-soft transition-colors hover:bg-raised hover:text-ink"
            >
              «
            </button>
          </div>

          <div className="px-4 pb-1 pt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-mute">
            Recent chats
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-2 py-1">
            {!authed ? (
              <EmptyState
                title="Not signed in"
                hint="Sign in to save conversations across sessions."
              />
            ) : conversations.length === 0 ? (
              <EmptyState title="No conversations yet" hint="Start one — it'll appear here." />
            ) : (
              <ul className="flex flex-col gap-1">
                {conversations.map((c) => (
                  <li key={c.id} className="group relative">
                    <button
                      onClick={() => onOpen(c.id)}
                      className={`flex w-full flex-col gap-1 rounded-xl border px-3 py-2.5 pr-8 text-left transition-colors ${
                        activeId === c.id
                          ? "border-accent/50 bg-accent/10"
                          : "border-transparent hover:border-border hover:bg-raised/60"
                      }`}
                    >
                      <span className="line-clamp-2 text-[13px] font-medium leading-snug text-ink">
                        {c.title}
                      </span>
                      <span className="font-mono text-[10px] text-mute">
                        {timeAgo(c.updated_at)} · {c.message_count} msg
                        {c.message_count === 1 ? "" : "s"}
                      </span>
                    </button>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(c.id);
                      }}
                      aria-label="Delete conversation"
                      title="Delete"
                      className="absolute right-1.5 top-2 flex h-6 w-6 items-center justify-center rounded-lg text-mute opacity-0 transition-opacity hover:bg-raised hover:text-[color:var(--color-critical)] focus:opacity-100 group-hover:opacity-100"
                    >
                      <TrashIcon />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!authed && (
            <div className="border-t border-border p-2">
              <button
                onClick={onSignIn}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg py-2 text-[11.5px] text-soft transition-colors hover:text-accent"
              >
                🔒 Sign in to save your history
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mt-10 px-3 text-center">
      <p className="text-[13px] text-soft">{title}</p>
      <p className="mt-1 text-[12px] text-mute">{hint}</p>
    </div>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  );
}
