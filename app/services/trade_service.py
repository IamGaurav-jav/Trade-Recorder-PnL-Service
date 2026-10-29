"""
Trade ingestion service.
Handles idempotency (duplicate detection), oversell prevention,
and position updates — all inside a single atomic transaction.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateTradeException, OversellException
from app.logger import logger
from app.models import Position, Trade


async def _lock_position(session: AsyncSession, symbol: str) -> Position:
    """
    Return the Position row for `symbol`, creating it if needed, holding a
    write lock on it until the transaction ends.

    INSERT ... ON CONFLICT DO NOTHING makes creation race-free; it also takes
    the SQLite write lock up front. SELECT ... FOR UPDATE locks the row on
    PostgreSQL (SQLAlchemy omits it on SQLite, which serializes writers anyway).
    """
    dialect = session.get_bind().dialect.name
    insert = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}.get(dialect)

    if insert is not None:
        await session.execute(
            insert(Position)
            .values(
                symbol=symbol,
                net_quantity=Decimal("0"),
                total_cost=Decimal("0"),
                realized_pnl=Decimal("0"),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["symbol"])
        )

    result = await session.execute(
        select(Position)
        .where(Position.symbol == symbol)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    position = result.scalar_one_or_none()

    if position is None:  # dialect without ON CONFLICT support
        position = Position(
            symbol=symbol,
            net_quantity=Decimal("0"),
            total_cost=Decimal("0"),
            realized_pnl=Decimal("0"),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(position)
        await session.flush()
    return position


async def ingest_trade(
    session: AsyncSession,
    venue: str,
    trade_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    timestamp: datetime,
) -> tuple[Trade, bool]:
    """
    Ingest a single trade with full atomic guarantees.

    Returns:
        (trade, is_new): The Trade object and whether it was newly created.

    Raises:
        DuplicateTradeException: If (venue, trade_id) already exists.
        OversellException: If SELL quantity exceeds current position.
    """
    # ── Step 1: Lock the symbol's position row ───────
    # Every trade for a symbol is serialized on this row, so the idempotency
    # check, oversell check and position update below are atomic across
    # concurrent requests (and across worker processes on PostgreSQL).
    position = await _lock_position(session, symbol)

    # ── Step 2: Idempotency check ────────────────────
    existing = await session.execute(
        select(Trade.id).where(Trade.venue == venue, Trade.trade_id == trade_id)
    )
    if existing.first() is not None:
        logger.warning("Duplicate trade ignored: venue=%s, trade_id=%s", venue, trade_id)
        raise DuplicateTradeException(venue=venue, trade_id=trade_id)

    # ── Step 3: Oversell check ───────────────────────
    if side == "SELL":
        if position.net_quantity < quantity:
            logger.error(
                "Oversell rejected for %s: available=%s, requested=%s",
                symbol, position.net_quantity, quantity,
            )
            raise OversellException(
                symbol=symbol,
                available=position.net_quantity,
                requested=quantity,
            )

    # ── Step 4: Update position (Average Cost) ───────
    if side == "BUY":
        position.net_quantity += quantity
        position.total_cost += quantity * price
        logger.info(
            "BUY applied: %s qty=%s price=%s | new position: qty=%s, avg_cost=%s",
            symbol, quantity, price, position.net_quantity, position.average_cost,
        )
    elif side == "SELL":
        current_avg_cost = position.total_cost / position.net_quantity
        realized = quantity * (price - current_avg_cost)
        position.realized_pnl += realized
        position.net_quantity -= quantity
        position.total_cost -= quantity * current_avg_cost

        # Guard against floating point dust when fully closing
        if position.net_quantity == Decimal("0"):
            position.total_cost = Decimal("0")

        logger.info(
            "SELL applied: %s qty=%s price=%s | realized=%s | remaining: qty=%s",
            symbol, quantity, price, realized, position.net_quantity,
        )

    position.updated_at = datetime.now(timezone.utc)

    # ── Step 5: Save the trade record ────────────────
    trade = Trade(
        venue=venue,
        trade_id=trade_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        timestamp=timestamp,
    )
    session.add(trade)
    try:
        await session.flush()
    except IntegrityError:
        # Same (venue, trade_id) raced in under a different symbol lock; the
        # UNIQUE constraint is the final arbiter. Roll back the position change.
        await session.rollback()
        logger.warning("Duplicate trade ignored (constraint): venue=%s, trade_id=%s", venue, trade_id)
        raise DuplicateTradeException(venue=venue, trade_id=trade_id)

    logger.info("Trade ingested: venue=%s, trade_id=%s, symbol=%s", venue, trade_id, symbol)
    return trade, True
