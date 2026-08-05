"""
SQLite + SQLAlchemy setup: engine, session factory, ORM models, and helpers.

Data model (ChatGPT-style):
    User 1──< Conversation 1──< Message
A Conversation is one chat session; a Message is one exchange within it (the
user's query plus the full three-panel response payload). SQLite is zero-config
and perfect for a self-contained demo; swap the URL for Postgres with no model
changes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from itertools import groupby

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import DATA_DIR, DB_PATH
from .text_utils import derive_title


def _make_engine():
    """Managed Postgres in production (set DATABASE_URL); zero-config SQLite locally.

    For Cloud SQL over the Cloud Run unix socket the URL looks like:
        postgresql+psycopg2://USER:PASS@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE
    The ORM models are identical for both backends.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # pool_pre_ping recycles connections Cloud SQL may have dropped while idle.
        return create_engine(url, pool_pre_ping=True, future=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},  # sessions cross FastAPI's threadpool
        future=True,
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Display name (from Google); email/password accounts leave this null.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Google account subject id, set when the user has linked "Sign in with Google".
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
    )


class Conversation(Base):
    """One chat session: a titled, ordered container of messages."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now,
    )  # bumped when a message is added

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """One exchange in a conversation: the user's query + the three-panel response."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of QueryResponse
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


# ── Schema helpers / migrations ────────────────────────────────────
def _ensure_columns() -> None:
    """Add columns that create_all won't add to an existing table (SQLite)."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("users")}
    to_add = {"google_sub": "VARCHAR(255)", "name": "VARCHAR(255)"}
    with engine.begin() as conn:
        for col, ddl in to_add.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))


def _migrate_chats_to_conversations() -> None:
    """One-time move from the old flat `chats` table to conversations/messages.

    Old rows had no session grouping, so each user's chats are collapsed into a
    single conversation (title from the oldest), preserving them as messages.
    Runs only when `chats` exists and `conversations` is still empty; the legacy
    table is dropped afterwards.
    """
    inspector = inspect(engine)
    if "chats" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        already = conn.execute(text("SELECT COUNT(*) FROM conversations")).scalar() or 0
        if already > 0:
            conn.execute(text("DROP TABLE IF EXISTS chats"))
            return

        rows = conn.execute(text(
            "SELECT user_id, query, payload, created_at FROM chats "
            "ORDER BY user_id, created_at, id"
        )).fetchall()

        for user_id, group in groupby(rows, key=lambda r: r[0]):
            items = list(group)
            conv = conn.execute(
                text(
                    "INSERT INTO conversations (user_id, title, created_at, updated_at) "
                    "VALUES (:u, :t, :c, :up)"
                ),
                {"u": user_id, "t": derive_title(items[0][1]),
                 "c": items[0][3], "up": items[-1][3]},
            )
            conv_id = conv.lastrowid
            for _uid, query, payload, created in items:
                conn.execute(
                    text(
                        "INSERT INTO messages (conversation_id, query, payload, created_at) "
                        "VALUES (:c, :q, :p, :cr)"
                    ),
                    {"c": conv_id, "q": query, "p": payload, "cr": created},
                )

        conn.execute(text("DROP TABLE chats"))
        print(f"  [Migration] moved {len(rows)} legacy chat(s) into conversations.")


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_columns()
    _migrate_chats_to_conversations()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: a request-scoped session that always closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
