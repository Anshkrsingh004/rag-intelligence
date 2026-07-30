import type { QueryResponse } from "../types";
import { PANELS, PANEL_ORDER } from "../lib/panels";
import { AnswerCard, type CardStatus } from "./AnswerCard";
import { RagMetricsPanel } from "./RagMetricsPanel";
import { BasicMetricsPanel } from "./BasicMetricsPanel";

export interface Turn {
  id: string;
  query: string;
  status: CardStatus;
  data?: QueryResponse;
}

export function ComparisonBlock({ turn }: { turn: Turn }) {
  const { status, data } = turn;

  return (
    <div id={`turn-${turn.id}`} className="animate-fadeUp flex scroll-mt-4 flex-col gap-4">
      {/* User question */}
      <div className="flex justify-end">
        <div
          className="flex max-w-[600px] items-start gap-3 rounded-2xl rounded-br-md border px-4 py-3"
          style={{
            background: "color-mix(in srgb, var(--color-accent) 10%, transparent)",
            borderColor: "color-mix(in srgb, var(--color-accent) 25%, transparent)",
          }}
        >
          <div className="text-[15px] font-medium text-ink">{turn.query}</div>
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px]"
            style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-rag))" }}
          >
            🧑
          </div>
        </div>
      </div>

      {/* Section label */}
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-mute">
          {status === "loading" ? "Running three systems in parallel" : "Three systems · one question"}
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      {/* Three cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {PANEL_ORDER.map((kind) => {
          const meta = PANELS[kind];
          if (kind === "rag") {
            return (
              <AnswerCard
                key={kind}
                meta={meta}
                status={status}
                featured
                answer={data?.rag_answer}
                metrics={data && <RagMetricsPanel m={data.rag_metrics} />}
              />
            );
          }
          const answer = kind === "hallu" ? data?.hallu_answer : data?.baseline_answer;
          const metrics = kind === "hallu" ? data?.hallu_metrics : data?.baseline_metrics;
          return (
            <AnswerCard
              key={kind}
              meta={meta}
              status={status}
              answer={answer}
              metrics={metrics && <BasicMetricsPanel m={metrics} accent={meta.colorVar} />}
            />
          );
        })}
      </div>
    </div>
  );
}
