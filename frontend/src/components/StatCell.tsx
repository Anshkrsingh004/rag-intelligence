interface Props {
  label: string;
  value: string | number;
  accent?: string;
}

/** Compact labelled figure used in the retrieval-stats grid. */
export function StatCell({ label, value, accent }: Props) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9px] uppercase tracking-wide text-mute">{label}</span>
      <span
        className="font-mono text-[15px] font-semibold tabular-nums"
        style={accent ? { color: accent } : { color: "var(--c-ink)" }}
      >
        {value}
      </span>
    </div>
  );
}
