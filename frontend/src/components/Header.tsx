import type { Health, User } from "../types";
import { initialsOf } from "../lib/format";

interface Props {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  health: Health | null;
  onToggleSidebar: () => void;
  user: User | null;
  onSignIn: () => void;
  onLogout: () => void;
}

export function Header({
  theme,
  onToggleTheme,
  health,
  onToggleSidebar,
  user,
  onSignIn,
  onLogout,
}: Props) {
  const online = health !== null;
  return (
    <header className="glass sticky top-0 z-20 flex items-center justify-between border-b border-border px-4 py-3 sm:px-7">
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle history sidebar"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-soft transition-colors hover:border-border-strong hover:text-ink"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <line x1="9" y1="4" x2="9" y2="20" />
          </svg>
        </button>
        <div
          className="flex h-9 w-9 items-center justify-center rounded-xl text-lg"
          style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
        >
          🧠
        </div>
        <div>
          <div className="text-gradient text-[16px] font-bold leading-tight tracking-tight">
            RAG Intelligence
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-mute">
            Anti-Hallucination Engine
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span
          className="hidden items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] sm:flex"
          style={{
            color: online ? "var(--color-good)" : "var(--color-mute)",
            borderColor: online
              ? "color-mix(in srgb, var(--color-good) 30%, transparent)"
              : "var(--c-border)",
          }}
          title={health ? `${health.model_quality} · ${health.version}` : "Backend not detected"}
        >
          <span
            className="h-1.5 w-1.5 rounded-full live-dot"
            style={{ background: online ? "var(--color-good)" : "var(--color-mute)" }}
          />
          {online ? "Live" : "Offline"}
        </span>

        {user ? (
          <div className="flex items-center gap-2">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-full text-[11px] font-bold uppercase text-white"
              style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
              title={user.name || user.email}
            >
              {initialsOf(user)}
            </div>
            <button
              onClick={onLogout}
              className="rounded-lg border border-border px-2.5 py-1.5 text-[12px] text-soft transition-colors hover:border-border-strong hover:text-ink"
            >
              Log out
            </button>
          </div>
        ) : (
          <button
            onClick={onSignIn}
            className="rounded-lg px-3 py-1.5 text-[12.5px] font-semibold text-white transition-transform hover:scale-[1.03]"
            style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
          >
            Sign in
          </button>
        )}

        <button
          onClick={onToggleTheme}
          aria-label="Toggle theme"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-[15px] text-soft transition-colors hover:border-border-strong hover:text-ink"
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}
