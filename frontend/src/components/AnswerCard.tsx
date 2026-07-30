import type { ReactNode } from "react";
import type { PanelMeta } from "../lib/panels";
import { renderAnswer } from "../lib/format";

export type CardStatus = "loading" | "done" | "offline" | "error";

interface Props {
  meta: PanelMeta;
  status: CardStatus;
  answer?: string;
  metrics?: ReactNode;
  featured?: boolean;
}

export function AnswerCard({ meta, status, answer, metrics, featured }: Props) {
  return (
    <div
      className={`card flex flex-col overflow-hidden transition-transform duration-200 hover:-translate-y-0.5 ${
        featured ? "glow-rag" : ""
      }`}
      style={
        featured
          ? { borderColor: "color-mix(in srgb, var(--color-rag) 45%, var(--c-border))" }
          : undefined
      }
    >
      {/* Accent top rule */}
      <div className="h-[3px] w-full" style={{ background: `linear-gradient(90deg, ${meta.colorVar}, transparent)` }} />

      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border bg-raised/50 px-5 py-3.5">
        <span className="text-xl" aria-hidden>
          {meta.icon}
        </span>
        <div className="flex-1">
          <div className="text-[13px] font-bold tracking-wide" style={{ color: meta.colorVar }}>
            {meta.title}
          </div>
          <div className="font-mono text-[10px] text-mute">{meta.subtitle}</div>
        </div>
        <span
          className="rounded-full px-2.5 py-1 font-mono text-[10px] font-medium"
          style={{
            color: meta.colorVar,
            background: `color-mix(in srgb, ${meta.colorVar} 12%, transparent)`,
            border: `1px solid color-mix(in srgb, ${meta.colorVar} 28%, transparent)`,
          }}
        >
          {meta.badge}
        </span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col px-5 py-4">
        <div className="flex-1 text-[14.5px] leading-relaxed text-ink">
          {status === "loading" && <LoadingBody />}
          {status === "offline" && <OfflineBody />}
          {status === "error" && (
            <em style={{ color: "var(--color-critical)" }}>Failed to load this response.</em>
          )}
          {status === "done" && <p className="whitespace-pre-wrap">{renderAnswer(answer ?? "")}</p>}
        </div>
      </div>

      {status === "done" && metrics}
    </div>
  );
}

function LoadingBody() {
  return (
    <div className="flex flex-col gap-3 py-1">
      <div className="flex items-center gap-1.5">
        <span className="typing-dot" />
        <span className="typing-dot" style={{ animationDelay: "0.2s" }} />
        <span className="typing-dot" style={{ animationDelay: "0.4s" }} />
      </div>
      <div className="skeleton h-3 w-full" />
      <div className="skeleton h-3 w-[92%]" />
      <div className="skeleton h-3 w-[70%]" />
    </div>
  );
}

function OfflineBody() {
  return (
    <div
      className="flex flex-col gap-2.5 rounded-xl p-4"
      style={{
        background: "color-mix(in srgb, var(--color-critical) 7%, transparent)",
        border: "1px solid color-mix(in srgb, var(--color-critical) 26%, transparent)",
      }}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">🔌</span>
        <span className="text-[13px] font-bold" style={{ color: "var(--color-critical)" }}>
          Backend offline
        </span>
      </div>
      <p className="font-mono text-[11.5px] leading-relaxed text-soft">
        Start the API, then ask again:
      </p>
      <code className="rounded-lg bg-black/30 px-3 py-2 font-mono text-[11.5px]" style={{ color: "var(--color-accent)" }}>
        cd backend &amp;&amp; python run.py
      </code>
    </div>
  );
}
