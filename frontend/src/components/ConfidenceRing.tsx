import { useEffect, useState } from "react";
import { verdictColor } from "../lib/format";

interface Props {
  score: number; // 0–100
  size?: number;
}

/**
 * The RAG panel's hero figure: a 0–100 confidence dial. Color is a reserved
 * status color (good / warning / critical) and always sits next to a text
 * verdict, so meaning is never carried by color alone.
 */
export function ConfidenceRing({ score, size = 92 }: Props) {
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = verdictColor(score);

  // Animate from empty on mount.
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setProgress(score), 80);
    return () => clearTimeout(t);
  }, [score]);
  const offset = c - (Math.max(0, Math.min(100, progress)) / 100) * c;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="color-mix(in srgb, var(--c-ink) 10%, transparent)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold leading-none" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="font-mono text-[9px] uppercase tracking-wider text-mute mt-0.5">
          / 100
        </span>
      </div>
    </div>
  );
}
