import { useEffect, useRef, useState } from "react";

interface Props {
  onSubmit: (q: string) => void;
  disabled: boolean;
  /** Set by the parent to prefill the box (e.g. from a suggestion chip). */
  prefill?: string;
}

export function QueryInput({ onSubmit, disabled, prefill }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (prefill) {
      setValue(prefill);
      const el = ref.current;
      if (el) {
        el.focus();
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 140) + "px";
      }
    }
  }, [prefill]);

  const submit = () => {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const resize = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  };

  return (
    <div className="glass border-t border-border px-4 py-3.5 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="card flex items-end gap-3 rounded-2xl px-4 py-3 focus-within:border-accent transition-colors">
          <textarea
            ref={ref}
            value={value}
            rows={1}
            disabled={disabled}
            placeholder="Ask anything — political, scientific, medical, historical…"
            onChange={(e) => {
              setValue(e.target.value);
              resize(e.target);
            }}
            onKeyDown={onKeyDown}
            className="max-h-[140px] min-h-6 flex-1 resize-none bg-transparent text-[15px] leading-relaxed text-ink outline-none placeholder:text-mute disabled:opacity-60"
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg text-white transition-transform enabled:hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
          >
            {disabled ? <Spinner /> : "➤"}
          </button>
        </div>
        <p className="mt-2 text-center font-mono text-[10px] tracking-wide text-mute">
          Enter to send · Shift+Enter for a new line · Powered by Groq + DuckDuckGo
        </p>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" className="animate-spin" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
