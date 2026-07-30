"""
/api/conversations — ChatGPT-style chat sessions for the signed-in user.

A conversation groups the messages of one session. Every route is scoped to the
authenticated user, so conversations are fully isolated between accounts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import current_user
from .db import Conversation, Message, User, get_db, _now
from .judges import generate_title
from .schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationRename,
    ConversationSummary,
    MessageCreate,
    MessageOut,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ── Serializers ────────────────────────────────────────────────────
def _iso_utc(dt: datetime) -> str:
    """Serialize as unambiguous UTC ISO. Stored datetimes are UTC but SQLite
    returns them naive, so tag them so the browser doesn't read UTC as local."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id, query=m.query, payload=json.loads(m.payload),
        created_at=_iso_utc(m.created_at),
    )


def _summary(conv: Conversation, message_count: int) -> ConversationSummary:
    return ConversationSummary(
        id=conv.id, title=conv.title,
        created_at=_iso_utc(conv.created_at),
        updated_at=_iso_utc(conv.updated_at),
        message_count=message_count,
    )


def _owned_or_404(conv_id: int, user: User, db: Session) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


# ── Routes ─────────────────────────────────────────────────────────
@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> list[ConversationSummary]:
    """Sidebar list: summaries only, newest activity first."""
    counts = dict(
        db.execute(
            select(Message.conversation_id, func.count(Message.id)).group_by(Message.conversation_id)
        ).all()
    )
    convs = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [_summary(c, counts.get(c.id, 0)) for c in convs]


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ConversationSummary:
    title = generate_title(body.first_message) if body.first_message else "New chat"
    conv = Conversation(user_id=user.id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _summary(conv, 0)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    conv = _owned_or_404(conversation_id, user, db)
    return ConversationDetail(
        id=conv.id, title=conv.title,
        created_at=_iso_utc(conv.created_at),
        updated_at=_iso_utc(conv.updated_at),
        message_count=len(conv.messages),
        messages=[_message_out(m) for m in conv.messages],
    )


@router.post("/{conversation_id}/messages", response_model=MessageOut,
             status_code=status.HTTP_201_CREATED)
def add_message(
    conversation_id: int,
    body: MessageCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    conv = _owned_or_404(conversation_id, user, db)
    message = Message(
        conversation_id=conv.id, query=body.query, payload=json.dumps(body.payload),
    )
    db.add(message)
    # First message names an as-yet-untitled conversation.
    if conv.title == "New chat":
        conv.title = generate_title(body.query)
    conv.updated_at = _now()  # move to top of the sidebar
    db.commit()
    db.refresh(message)
    return _message_out(message)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: int,
    body: ConversationRename,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ConversationSummary:
    conv = _owned_or_404(conversation_id, user, db)
    conv.title = body.title.strip()
    db.commit()
    db.refresh(conv)
    return _summary(conv, len(conv.messages))


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    conv = _owned_or_404(conversation_id, user, db)
    db.delete(conv)  # messages cascade
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
