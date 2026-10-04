"""Cost log stored in the ai_calls table (implements app.ai.gemini.CostLog)."""

from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select

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
