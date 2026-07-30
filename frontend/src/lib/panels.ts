import type { PanelKind } from "../types";

export interface PanelMeta {
  kind: PanelKind;
  icon: string;
  title: string;
  subtitle: string;
  badge: string;
  /** CSS variable holding this panel's identity color. */
  colorVar: string;
}

export const PANELS: Record<PanelKind, PanelMeta> = {
  hallu: {
    kind: "hallu",
    icon: "🎭",
    title: "Hallucinating AI",
    subtitle: "Overconfident · no grounding",
    badge: "Ungrounded",
    colorVar: "var(--color-hallu)",
  },
  baseline: {
    kind: "baseline",
    icon: "🧩",
    title: "Baseline LLM",
    subtitle: "Parametric memory only",
    badge: "No retrieval",
    colorVar: "var(--color-baseline)",
  },
  rag: {
    kind: "rag",
    icon: "🔬",
    title: "RAG Pipeline",
    subtitle: "Retrieved · reranked · verified",
    badge: "Grounded",
    colorVar: "var(--color-rag)",
  },
};

/** Left-to-right display order of the three panels. */
export const PANEL_ORDER: PanelKind[] = ["hallu", "baseline", "rag"];
