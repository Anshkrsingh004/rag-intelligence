import type { ReactNode } from "react";

/** Confidence thresholds shared across ring, verdict, and coloring. */
export const HIGH = 72;
export const MEDIUM = 45;

export type Verdict = "high" | "medium" | "low";

export function verdictOf(score: number): Verdict {
  if (score >= HIGH) return "high";
  if (score >= MEDIUM) return "medium";
  return "low";
}

export function verdictColor(score: number): string {
  const v = verdictOf(score);
  return v === "high" ? "var(--color-good)" : v === "medium" ? "var(--color-warning)" : "var(--color-critical)";
}

export function verdictLabel(score: number): string {
  const v = verdictOf(score);
  return v === "high" ? "High confidence" : v === "medium" ? "Medium confidence" : "Low confidence";
}

/**
 * Render answer text, turning [Source N] citations into pills and preserving
 * paragraph breaks. Returns React nodes (safe — no dangerouslySetInnerHTML).
 */
export function renderAnswer(text: string): ReactNode {
  if (!text?.trim()) {
    return <em className="text-mute">No answer returned.</em>;
  }
  // Matches a whole citation bracket in any common shape:
  //   [Source 1]   ·   [Source 1, Source 2, Source 3]   ·   [Sources 2-4]
  const parts = text.split(/(\[\s*sources?[^\]]*\])/gi);
  return parts.map((part, i) => {
    if (/^\[\s*sources?/i.test(part)) {
      const nums = part.match(/\d+/g) ?? [];
      if (nums.length === 0) {
        return (
          <span key={i} className="source-pill">
            src
          </span>
        );
      }
      return (
        <span key={i} className="whitespace-nowrap">
          {nums.map((n, j) => (
            <span key={j} className="source-pill">
              S{n}
            </span>
          ))}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export const fmt = (n: number | undefined | null, digits = 2): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

export const pct = (n: number): number => Math.max(0, Math.min(100, Math.round(n * 100)));

/** Compact relative time for conversation cards ("just now", "3h", "2d"). */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Up to two initials for the avatar: first + last name when a name exists
 * ("John Doe" → "JD"), otherwise derived from the email local part
 * ("john.doe@x" → "JD", "johndoe@x" → "J").
 */
export function initialsOf(user: { name?: string | null; email: string }): string {
  const source = (user.name && user.name.trim()) || user.email.split("@")[0] || "";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return (user.email[0] || "?").toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
