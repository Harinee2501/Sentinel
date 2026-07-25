"""
Audit Logger — every verdict, from every adaptor, written to a shared
SQLite database. This is what the dashboard reads from, and what makes
the whole system's decisions inspectable after the fact.
"""

from __future__ import annotations

import json
from datetime import datetime
import os

from sqlmodel import Field, Session, SQLModel, create_engine, select

from agent_sentinel.core.types import Action, Source, Verdict, VerdictType


class AuditLogEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    action_id: str
    tool: str
    agent_id: str
    session_id: str
    source: Source
    verdict: VerdictType
    reason: str
    layer: str
    args_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog:
    def __init__(self, db_path: str = "data/audit_log.db"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self.engine)

    def record(self, action: Action, verdict: Verdict) -> None:
        entry = AuditLogEntry(
            action_id=action.action_id,
            tool=action.tool,
            agent_id=action.agent_id,
            session_id=action.session_id,
            source=action.source,
            verdict=verdict.verdict,
            reason=verdict.reason,
            layer=verdict.layer,
            args_json=json.dumps(action.args),
        )
        with Session(self.engine) as session:
            session.add(entry)
            session.commit()

    def recent(self, limit: int = 100) -> list[AuditLogEntry]:
        with Session(self.engine) as session:
            statement = (
                select(AuditLogEntry)
                .order_by(AuditLogEntry.created_at.desc())
                .limit(limit)
            )
            return list(session.exec(statement))

    def stats(self) -> dict:
        with Session(self.engine) as session:
            entries = session.exec(select(AuditLogEntry)).all()

        total = len(entries)
        by_verdict = {"allow": 0, "block": 0, "flag": 0}
        by_source = {"python_middleware": 0, "mcp_proxy": 0}

        for e in entries:
            by_verdict[e.verdict.value] += 1
            by_source[e.source.value] += 1

        return {
            "total": total,
            "by_verdict": by_verdict,
            "by_source": by_source,
            "block_rate": (by_verdict["block"] / total) if total else 0.0,
        }
