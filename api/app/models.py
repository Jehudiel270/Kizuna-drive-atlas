"""Tables : utilisateurs, soumissions Tally normalisées, paramètres, instantanés, codage qualitatif, journal."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="analyste")  # admin | analyste | lecteur
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # id de soumission Tally
    respondent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    form_id: Mapped[str] = mapped_column(String(32), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default="api")  # api | webhook | csv | demo
    answers: Mapped[dict] = mapped_column(JSONType, default=dict)
    unmapped: Mapped[dict] = mapped_column(JSONType, default=dict)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Setting(Base):
    """Paires clé/valeur JSON : plan_override, codebook_override, last_sync…"""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Snapshot(Base):
    """Jeu de données figé (reproductibilité du rapport) avec le plan et l'empreinte SHA-256."""
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    n_rows: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64))
    plan_hash: Mapped[str] = mapped_column(String(64))
    plan: Mapped[dict] = mapped_column(JSONType, default=dict)
    codebook: Mapped[dict] = mapped_column(JSONType, default=dict)
    rows: Mapped[list] = mapped_column(JSONType, default=list)


class Theme(Base):
    """Thème du codebook qualitatif (protocole 5.4 : analyse de contenu thématique)."""
    __tablename__ = "themes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(16), default="#6ea8ff")
    parent_dimension: Mapped[str] = mapped_column(String(60), default="")  # gouvernance | compétences | communication | autre
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    segments: Mapped[list["CodedSegment"]] = relationship(back_populates="theme", cascade="all, delete-orphan")


class CodedSegment(Base):
    __tablename__ = "coded_segments"
    __table_args__ = (UniqueConstraint("submission_id", "question", "coder", "theme_id", name="uq_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(String(40))
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    coder: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    theme: Mapped[Theme] = relationship(back_populates="segments")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSONType, default=dict)
