import type { BasicMetrics } from "../types";
import { StatCell } from "./StatCell";

export function BasicMetricsPanel({ m, accent }: { m: BasicMetrics; accent: string }) {
  return (
    <div className="border-t border-border bg-raised/40 px-5 py-4">
      <div className="mb-3 font-mono text-[10px] uppercase tracking-widest text-mute">Output stats</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-3">
        <StatCell label="Tokens" value={m.length.total_tokens} accent={accent} />
        <StatCell label="Content words" value={m.length.content_tokens} accent={accent} />
        <StatCell label="Lexical diversity" value={m.lexical_diversity} />
        <StatCell label="Latency" value={`${m.latency}s`} />
      </div>
    </div>
  );
}
