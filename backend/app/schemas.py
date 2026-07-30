"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's question.")


class PanelResponse(BaseModel):
    """A single AI panel's answer plus its metrics (shape kept flexible)."""

    answer: str
    metrics: dict[str, Any]


class QueryResponse(BaseModel):
    """Full three-way comparison payload returned by POST /query."""

    baseline_answer: str
    baseline_metrics: dict[str, Any]
    hallu_answer: str
    hallu_metrics: dict[str, Any]
    rag_answer: str
    rag_metrics: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    version: str
    model_fast: str
    model_quality: str


# ── Auth ───────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="The Google ID token (JWT) from the browser.")


class AuthConfigResponse(BaseModel):
    google_client_id: str | None = None


# ── Conversations & messages (saved history) ───────────────────
class MessageOut(BaseModel):
    id: int
    query: str
    payload: dict[str, Any]  # the full QueryResponse for this exchange
    created_at: str


class ConversationSummary(BaseModel):
    """Lightweight row for the sidebar — no message payloads."""

    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationDetail(ConversationSummary):
    """A conversation with its full ordered messages, for the main view."""

    messages: list[MessageOut]


class ConversationCreate(BaseModel):
    # Optional first message → used to derive the title at creation time.
    first_message: str | None = None


class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class MessageCreate(BaseModel):
    query: str = Field(..., min_length=1)
    payload: dict[str, Any]
