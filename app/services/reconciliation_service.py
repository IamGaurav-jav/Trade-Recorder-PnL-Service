"""
Reconciliation service.
Compares an external venue trade statement against internally stored trades.
Reports missing, extra, and mismatched trades.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.models import Trade
from app.schemas import (
    MismatchDetail,
    ReconciliationResponse,
    TradeResponse,
    VenueStatementTrade,
)


async def reconcile(
    session: AsyncSession,
    venue: str,
    statement_trades: list[VenueStatementTrade],
) -> ReconciliationResponse:
    """
    Compare venue statement trades against our stored trades for that venue.

    Returns:
        ReconciliationResponse with missing, extra, and mismatched trades.
    """
    # ── Load all stored trades for this venue ────────
    result = await session.execute(
        select(Trade).where(Trade.venue == venue)
    )
    stored_trades = result.scalars().all()

    # Index stored trades by trade_id for fast lookup
    stored_by_id: dict[str, Trade] = {t.trade_id: t for t in stored_trades}

    # Index statement trades by trade_id
    statement_by_id: dict[str, VenueStatementTrade] = {
        t.trade_id: t for t in statement_trades
    }

    missing_trades: list[VenueStatementTrade] = []
    extra_trades: list[TradeResponse] = []
    mismatched_trades: list[MismatchDetail] = []

    # ── Find missing and mismatched trades ───────────
    for stmt_trade in statement_trades:
        stored = stored_by_id.get(stmt_trade.trade_id)

        if stored is None:
            # Trade is in the venue statement but NOT in our database
            missing_trades.append(stmt_trade)
            logger.warning(
                "Reconciliation: MISSING trade_id=%s from venue=%s",
                stmt_trade.trade_id, venue,
            )
        else:
            # Trade exists in both — check for field mismatches
            differences = []

            if stored.symbol != stmt_trade.symbol:
                differences.append("symbol")
            if stored.side != stmt_trade.side.value:
                differences.append("side")
            if stored.quantity != stmt_trade.quantity:
                differences.append("quantity")
            if stored.price != stmt_trade.price:
                differences.append("price")

            if differences:
                mismatched_trades.append(
                    MismatchDetail(
                        trade_id=stmt_trade.trade_id,
                        stored={
                            "symbol": stored.symbol,
                            "side": stored.side,
                            "quantity": str(stored.quantity),
                            "price": str(stored.price),
                        },
                        venue_statement={
                            "symbol": stmt_trade.symbol,
                            "side": stmt_trade.side.value,
                            "quantity": str(stmt_trade.quantity),
                            "price": str(stmt_trade.price),
                        },
                        differences=differences,
                    )
                )
                logger.warning(
                    "Reconciliation: MISMATCH trade_id=%s fields=%s",
                    stmt_trade.trade_id, differences,
                )

    # ── Find extra trades (in our DB but not in statement) ──
    statement_ids = set(statement_by_id.keys())
    for stored_trade in stored_trades:
        if stored_trade.trade_id not in statement_ids:
            extra_trades.append(
                TradeResponse(
                    id=stored_trade.id,
                    venue=stored_trade.venue,
                    trade_id=stored_trade.trade_id,
                    symbol=stored_trade.symbol,
                    side=stored_trade.side,
                    quantity=stored_trade.quantity,
                    price=stored_trade.price,
                    timestamp=stored_trade.timestamp,
                    created_at=stored_trade.created_at,
                )
            )
            logger.warning(
                "Reconciliation: EXTRA trade_id=%s in our DB but not in venue statement",
                stored_trade.trade_id,
            )

    logger.info(
        "Reconciliation complete for venue=%s: missing=%d, extra=%d, mismatched=%d",
        venue, len(missing_trades), len(extra_trades), len(mismatched_trades),
    )

    return ReconciliationResponse(
        venue=venue,
        missing_trades=missing_trades,
        extra_trades=extra_trades,
        mismatched_trades=mismatched_trades,
    )
