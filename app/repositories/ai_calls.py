"""Cost log stored in the ai_calls table (implements app.ai.gemini.CostLog), plus read queries."""

from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.gemini import CallRecord
from app.db.models import AICall
from app.db.session import session_scope


class DbCostLog:
    def total_spent_usd(self) -> Decimal:
        with session_scope() as s:
            return s.scalar(select(func.coalesce(func.sum(AICall.cost_usd), 0)))

    def record(self, entry: CallRecord) -> None:
        # Own transaction on purpose: the cost row is committed immediately, so it survives even
        # if the job that made the call later fails and rolls back its own work. A request that
        # happened must always stay on the books.
        with session_scope() as s:
            s.add(AICall(**asdict(entry)))


def totals_by_purpose_and_model(session: Session) -> list[dict]:
    rows = session.execute(
        select(
            AICall.purpose,
            AICall.model,
            func.count().label("calls"),
            func.count().filter(AICall.outcome == "ok").label("ok"),
            func.count().filter(AICall.outcome == "invalid_output").label("invalid_output"),
            func.count().filter(AICall.outcome == "rate_limited").label("rate_limited"),
            func.count().filter(AICall.outcome == "error").label("error"),
            func.sum(AICall.input_tokens).label("input_tokens"),
            func.sum(AICall.output_tokens).label("output_tokens"),
            func.sum(AICall.thinking_tokens).label("thinking_tokens"),
            func.sum(AICall.cost_usd).label("cost_usd"),
        )
        .group_by(AICall.purpose, AICall.model)
        .order_by(AICall.purpose, AICall.model)
    )
    return [dict(row._mapping) for row in rows]


def list_calls(
    session: Session,
    limit: int,
    offset: int,
    owner_type: str | None = None,
    owner_id: int | None = None,
) -> list[AICall]:
    query = select(AICall).order_by(AICall.id).limit(limit).offset(offset)
    if owner_type is not None:
        query = query.where(AICall.owner_type == owner_type, AICall.owner_id == owner_id)
    return list(session.scalars(query))


def count_calls(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(AICall))
