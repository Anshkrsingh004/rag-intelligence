import { useState } from "react";
import { GoogleButton } from "./GoogleButton";

interface Props {
  open: boolean;
  onClose: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
  onGoogle: (credential: string) => Promise<void>;
  googleClientId: string | null;
  theme: "light" | "dark";
}

export function AuthModal({
  open,
  onClose,
  onLogin,
  onRegister,
  onGoogle,
  googleClientId,
  theme,
}: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleGoogle = async (credential: string) => {
    setError(null);
    setBusy(true);
    try {
      await onGoogle(credential);
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await onLogin(email.trim(), password);
      else await onRegister(email.trim(), password);
      setEmail("");
      setPassword("");
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (m: "login" | "register") => {
    setMode(m);
    setError(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/55 backdrop-blur-sm"
      />

      <div className="card animate-fadeUp relative z-10 w-full max-w-sm p-6">
        <div className="mb-5 flex flex-col items-center gap-2 text-center">
          <div
            className="flex h-11 w-11 items-center justify-center rounded-2xl text-xl"
            style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
          >
            🧠
          </div>
          <h2 className="text-[19px] font-bold text-ink">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="text-[13px] text-soft">
            {mode === "login"
              ? "Sign in to see your saved question history."
              : "Save your history and pick up where you left off."}
          </p>
        </div>

        {/* Google sign-in (only when configured on the server) */}
        {googleClientId && (
          <div className="mb-4">
            <GoogleButton clientId={googleClientId} theme={theme} onCredential={handleGoogle} />
            <div className="mt-4 flex items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="font-mono text-[10px] uppercase tracking-wide text-mute">
                or use email
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>
          </div>
        )}

        {/* Mode tabs */}
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-xl border border-border p-1">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`rounded-lg py-1.5 text-[13px] font-medium transition-colors ${
                mode === m ? "bg-accent/15 text-accent" : "text-mute hover:text-soft"
              }`}
            >
              {m === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-mute">Email</span>
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="rounded-xl border border-border bg-raised/60 px-3 py-2.5 text-[14px] text-ink outline-none transition-colors placeholder:text-mute focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-mute">Password</span>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "At least 6 characters" : "••••••••"}
              className="rounded-xl border border-border bg-raised/60 px-3 py-2.5 text-[14px] text-ink outline-none transition-colors placeholder:text-mute focus:border-accent"
            />
          </label>

          {error && (
            <div
              className="rounded-lg px-3 py-2 text-[12.5px]"
              style={{
                color: "var(--color-critical)",
                background: "color-mix(in srgb, var(--color-critical) 10%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-critical) 26%, transparent)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-1 flex items-center justify-center rounded-xl py-2.5 text-[14px] font-semibold text-white transition-transform enabled:hover:scale-[1.02] disabled:opacity-60"
            style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
          >
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button
          onClick={onClose}
          className="mt-4 w-full text-center font-mono text-[11px] text-mute transition-colors hover:text-soft"
        >
          Continue without an account
        </button>
      </div>
    </div>
  );
}
