import { PANEL_ORDER, PANELS } from "../lib/panels";

const SUGGESTIONS = [
  "Who is the current CM of Maharashtra?",
  "Who won the 2023 Cricket World Cup?",
  "What are the side effects of Metformin?",
  "Who directed the movie Oppenheimer?",
];

export function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="animate-fadeUp mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center gap-5 py-8 text-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full text-3xl animate-spin-slow"
        style={{
          background:
            "conic-gradient(from 0deg, var(--color-accent), var(--color-rag), var(--color-baseline), var(--color-accent))",
          boxShadow: "0 0 50px color-mix(in srgb, var(--color-accent) 30%, transparent)",
        }}
      >
        <span className="[animation:spin-slow_14s_linear_infinite_reverse]">🔬</span>
      </div>

      <div className="flex flex-col gap-3">
        <h1 className="text-[40px] font-bold leading-[1.05] tracking-tight sm:text-[50px]">
          <span className="text-ink">Ask anything.</span>
          <br />
          <span className="text-gradient">See the truth.</span>
        </h1>
        <p className="mx-auto max-w-lg text-[15.5px] leading-relaxed text-soft">
          Every question runs through three AI systems at once — so you can watch hallucination and
          grounded, source-cited intelligence answer the same prompt side by side.
        </p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
        {PANEL_ORDER.map((k) => (
          <div key={k} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: PANELS[k].colorVar }} />
            <span className="font-mono text-[11px] text-mute">{PANELS[k].title}</span>
          </div>
        ))}
      </div>

      <div className="mt-1 flex flex-wrap justify-center gap-2.5">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => onPick(s)}>
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
