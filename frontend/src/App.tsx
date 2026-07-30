import { useEffect, useRef, useState } from "react";
import type { Health } from "./types";
import { getGoogleClientId, getHealth } from "./lib/api";
import { useTheme } from "./hooks/useTheme";
import { useAuth } from "./hooks/useAuth";
import { useConversations } from "./hooks/useConversations";
import { Aurora } from "./components/Aurora";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Welcome } from "./components/Welcome";
import { QueryInput } from "./components/QueryInput";
import { AuthModal } from "./components/AuthModal";
import { ComparisonBlock } from "./components/ComparisonBlock";

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const { token, user, login, register, googleLogin, logout } = useAuth();

  const [health, setHealth] = useState<Health | null>(null);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>();
  const [toast, setToast] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window !== "undefined" && window.innerWidth >= 768,
  );

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4200);
  };

  const {
    conversations,
    activeId,
    turns,
    busy,
    newChat,
    openConversation,
    sendMessage,
    removeConversation,
  } = useConversations(token, showToast);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Poll health on mount + light heartbeat so the badge reflects reality.
  useEffect(() => {
    let active = true;
    const check = () => getHealth().then((h) => active && setHealth(h));
    check();
    const id = setInterval(check, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  // Discover whether "Sign in with Google" is configured on the server.
  useEffect(() => {
    let active = true;
    getGoogleClientId().then((cid) => active && setGoogleClientId(cid));
    return () => {
      active = false;
    };
  }, []);

  // Once signed in, stop Google One Tap from auto-re-authenticating (which would
  // churn the token and reset the view).
  useEffect(() => {
    if (user) {
      try {
        window.google?.accounts?.id?.cancel();
        window.google?.accounts?.id?.disableAutoSelect();
      } catch {
        /* GIS not loaded — nothing to disable */
      }
    }
  }, [user]);

  // Keep the newest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const handleOpen = (id: number) => {
    openConversation(id);
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  const handleNewChat = () => {
    newChat();
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  return (
    <>
      <Aurora />
      <div className="relative z-10 flex h-screen">
        <Sidebar
          conversations={conversations}
          open={sidebarOpen}
          activeId={activeId}
          authed={!!user}
          onNewChat={handleNewChat}
          onOpen={handleOpen}
          onDelete={removeConversation}
          onClose={() => setSidebarOpen(false)}
          onSignIn={() => setAuthOpen(true)}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <Header
            theme={theme}
            onToggleTheme={toggleTheme}
            health={health}
            onToggleSidebar={() => setSidebarOpen((o) => !o)}
            user={user}
            onSignIn={() => setAuthOpen(true)}
            onLogout={logout}
          />

          <main ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col gap-8 px-4 py-7 sm:px-6">
              {turns.length === 0 ? (
                <Welcome onPick={setPrefill} />
              ) : (
                turns.map((turn) => <ComparisonBlock key={turn.id} turn={turn} />)
              )}
            </div>
          </main>

          <QueryInput onSubmit={sendMessage} disabled={busy} prefill={prefill} />

          {toast && (
            <div
              className="animate-fadeUp fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-5 py-3 font-mono text-[12px] backdrop-blur"
              style={{
                color: "var(--color-critical)",
                background: "color-mix(in srgb, var(--color-critical) 12%, var(--c-surface))",
                borderColor: "color-mix(in srgb, var(--color-critical) 30%, transparent)",
              }}
            >
              {toast}
            </div>
          )}
        </div>
      </div>

      <AuthModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onLogin={login}
        onRegister={register}
        onGoogle={googleLogin}
        googleClientId={googleClientId}
        theme={theme}
      />
    </>
  );
}
