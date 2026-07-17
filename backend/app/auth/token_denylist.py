"""Server-side token revocation (logout) without Redis.

Stores revoked `jti` values until their original expiry. Single-admin scale
— a small SQLite/Postgres table is enough.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RevokedToken(SQLModel, table=True):
    __tablename__ = "revoked_tokens"

    jti: str = Field(primary_key=True, max_length=64)
    expires_at: datetime
    revoked_at: datetime = Field(default_factory=_utcnow)
    username: str | None = None


def revoke_jti(
    session: Session,
    jti: str,
    *,
    expires_at: datetime,
    username: str | None = None,
) -> None:
    if not jti:
        return
    existing = session.get(RevokedToken, jti)
    if existing is not None:
        return
    session.add(
        RevokedToken(jti=jti, expires_at=expires_at, username=username)
    )
    session.commit()


def is_jti_revoked(session: Session, jti: str | None) -> bool:
    if not jti:
        return False
    row = session.get(RevokedToken, jti)
    if row is None:
        return False
    now = _utcnow()
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        session.delete(row)
        session.commit()
        return False
    return True


def purge_expired_revocations(session: Session) -> int:
    now = _utcnow()
    rows = list(session.exec(select(RevokedToken)).all())
    removed = 0
    for row in rows:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            session.delete(row)
            removed += 1
    if removed:
        session.commit()
    return removed
