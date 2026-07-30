import { useState } from "react";
import type { RagMetrics } from "../types";
import { verdictColor, verdictLabel, verdictOf } from "../lib/format";
import { ConfidenceRing } from "./ConfidenceRing";
import { MetricMeter } from "./MetricMeter";
import { StatCell } from "./StatCell";

export function RagMetricsPanel({ m }: { m: RagMetrics }) {
  const [showClaims, setShowClaims] = useState(false);
  const color = verdictColor(m.confidence_score);
  const verdict = verdictOf(m.confidence_score);
  const flags = m.unsupported_claims ?? [];

  const verdictBg =
    verdict === "high"
      ? "color-mix(in srgb, var(--color-good) 14%, transparent)"
      : verdict === "medium"
        ? "color-mix(in srgb, var(--color-warning) 16%, transparent)"
        : "color-mix(in srgb, var(--color-critical) 14%, transparent)";

  return (
    <div className="border-t border-border bg-raised/40 px-5 py-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-mute">
          Evaluation
        </span>
        {m.intent && (
          <span className="tag" style={{ borderColor: "var(--c-border)" }}>
            🎯 {m.intent}
          </span>
        )}
      </div>

      {/* Hero: confidence dial + verdict */}
      <div className="flex items-center gap-4">
        <ConfidenceRing score={m.confidence_score} />
        <div className="flex flex-col gap-2">
          <span
            className="w-fit rounded-full px-3 py-1 text-[11px] font-semibold"
            style={{ color, background: verdictBg }}
          >
            {verdictLabel(m.confidence_score)}
          </span>
          <span className="text-[12px] leading-snug text-soft">
            Composite of faithfulness, consistency, grounding &amp; hallucination.
          </span>
        </div>
      </div>

      {/* Quality meters */}
      <div className="mt-4 flex flex-col gap-2.5">
        <MetricMeter label="Faithfulness" value={m.faithfulness_score} color="var(--color-accent)"
          hint="LLM-judged share of claims supported by sources" />
        <MetricMeter label="Consistency" value={m.consistency_score} color="var(--color-accent)"
          hint="Agreement between the primary and an independent verification answer" />
        <MetricMeter label="Entity grounding" value={m.entity_grounding} color="var(--color-accent)"
          hint="Named entities semantically present in the retrieved context" />
        <MetricMeter label="Context use" value={m.context_utilization} color="var(--color-accent)"
          hint="Share of answer sentences grounded in context" />
        <MetricMeter label="Hallucination" value={m.hallucination_rate} lowerIsBetter
          color="var(--color-critical)"
          hint="Share of answer sentences with low similarity to any source" />
      </div>

      {/* Unsupported claims (only when present) */}
      {flags.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowClaims((s) => !s)}
            className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors"
            style={{
              borderColor: "color-mix(in srgb, var(--color-critical) 30%, transparent)",
              background: "color-mix(in srgb, var(--color-critical) 8%, transparent)",
            }}
          >
            <span className="text-[12px] font-semibold" style={{ color: "var(--color-critical)" }}>
              ⚠ {flags.length} unsupported claim{flags.length > 1 ? "s" : ""}
            </span>
            <span className="font-mono text-[11px] text-mute">{showClaims ? "hide" : "show"}</span>
          </button>
          {showClaims && (
            <ul className="mt-2 flex flex-col gap-1.5">
              {flags.map((claim, i) => (
                <li key={i} className="flex gap-2 text-[12px] leading-snug text-soft">
                  <span style={{ color: "var(--color-critical)" }}>·</span>
                  <span>{claim}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Retrieval stats */}
      <div className="mt-4 grid grid-cols-3 gap-x-3 gap-y-3 border-t border-border pt-3">
        <StatCell label="Precision@K" value={m.precision_at_k} accent="var(--color-accent)" />
        <StatCell label="Recall@K" value={m.recall_at_k} accent="var(--color-accent)" />
        <StatCell label="MRR" value={m.mrr} accent="var(--color-accent)" />
        <StatCell label="ROUGE-L" value={m.rouge_l_vs_context} />
        <StatCell label="Token F1" value={m.token_f1} />
        <StatCell label="Docs" value={m.docs_primary} accent="var(--color-rag)" />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5">
        <span className="font-mono text-[10px] uppercase tracking-wide text-mute">⏱ Latency</span>
        <span className="font-mono text-[12px] tabular-nums text-soft">{m.latency}s</span>
      </div>
    </div>
  );
}
