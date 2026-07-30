// Mirrors the FastAPI /api/query response shape.

export interface AnswerLength {
  total_tokens: number;
  content_tokens: number;
}

export interface BasicMetrics {
  length: AnswerLength;
  lexical_diversity: number;
  latency: number;
}

export interface RagMetrics {
  precision_at_k: number;
  recall_at_k: number;
  f1_at_k: number;
  mrr: number;
  source_coverage: number;
  context_utilization: number;
  hallucination_rate: number;
  unsupported_sentences: string[];
  unsupported_claims: string[];
  entity_grounding: number;
  rouge_l_vs_context: number;
  token_f1: number;
  token_precision: number;
  token_recall: number;
  lexical_diversity: number;
  answer_length: AnswerLength;
  faithfulness_score: number;
  consistency_score: number;
  confidence_score: number;
  docs_primary: number;
  docs_verify: number;
  passes_used: number;
  latency: number;
  intent: string;
  answer_type: string;
  scoring_method: string;
}

export interface QueryResponse {
  baseline_answer: string;
  baseline_metrics: BasicMetrics;
  hallu_answer: string;
  hallu_metrics: BasicMetrics;
  rag_answer: string;
  rag_metrics: RagMetrics;
}

export type PanelKind = "hallu" | "baseline" | "rag";

export interface Health {
  status: string;
  version: string;
  model_fast: string;
  model_quality: string;
}

// ── Auth + saved history ───────────────────────────────────────
export interface User {
  id: number;
  email: string;
  name?: string | null;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface MessageRecord {
  id: number;
  query: string;
  payload: QueryResponse;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail extends ConversationSummary {
  messages: MessageRecord[];
}
