import { pct } from "../lib/format";

interface Props {
  label: string;
  /** Raw 0–1 value. */
  value: number;
  /** Fill color (defaults to the accent). */
  color?: string;
  /** When true, a LOWER value is better (e.g. hallucination) — flips fill length. */
  lowerIsBetter?: boolean;
  hint?: string;
}

/**
 * A single 0–1 magnitude meter. Thin track, rounded data-end. The number shown
 * is always the true metric value; for "lower is better" metrics the bar length
 * represents the good portion (1 - value) while the label still reads the rate.
 */
export function MetricMeter({ label, value, color = "var(--color-accent)", lowerIsBetter, hint }: Props) {
  const fillPct = lowerIsBetter ? pct(1 - value) : pct(value);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[10px] uppercase tracking-wide text-mute" title={hint}>
          {label}
          {lowerIsBetter && <span className="ml-1 opacity-70">↓</span>}
        </span>
        <span className="font-mono text-[11px] font-semibold tabular-nums" style={{ color }}>
          {value.toFixed(2)}
        </span>
      </div>
      <div className="metric-track">
        <div className="metric-fill" style={{ width: `${fillPct}%`, background: color }} />
      </div>
    </div>
  );
}
