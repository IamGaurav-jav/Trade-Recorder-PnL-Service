"""
PnL calculation service.
Computes realized PnL (from trades) and unrealized PnL (from latest prices).
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import SymbolNotFoundException
from app.logger import logger
from app.models import LatestPrice, Position
from app.schemas import PnLResponse


async def get_pnl_for_symbol(session: AsyncSession, symbol: str) -> PnLResponse:
    """
    Calculate PnL report for a single symbol.

    Raises:
        SymbolNotFoundException: If no position exists for the symbol.
    """
    # Fetch position
    result = await session.execute(
        select(Position).where(Position.symbol == symbol)
    )
    position = result.scalar_one_or_none()

    if position is None:
        logger.warning("PnL requested for unknown symbol: %s", symbol)
        raise SymbolNotFoundException(symbol=symbol)

    # Fetch latest price
    price_result = await session.execute(
        select(LatestPrice).where(LatestPrice.symbol == symbol)
    )
    latest_price_record = price_result.scalar_one_or_none()

    latest_price = latest_price_record.price if latest_price_record else None

    # Calculate unrealized PnL
    unrealized_pnl = Decimal("0")
    average_cost = Decimal("0")

    if position.net_quantity > 0:
        average_cost = position.total_cost / position.net_quantity
        if latest_price is not None:
            unrealized_pnl = (latest_price - average_cost) * position.net_quantity

    total_pnl = position.realized_pnl + unrealized_pnl

    logger.info(
        "PnL calculated for %s: realized=%s, unrealized=%s, total=%s",
        symbol, position.realized_pnl, unrealized_pnl, total_pnl,
    )

    return PnLResponse(
        symbol=symbol,
        net_quantity=position.net_quantity,
        average_cost=average_cost,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        latest_price=latest_price,
    )


async def get_pnl_all(session: AsyncSession) -> list[PnLResponse]:
    """Calculate PnL report for all symbols with positions."""
    result = await session.execute(select(Position))
    positions = result.scalars().all()

    reports = []
    for position in positions:
        try:
            report = await get_pnl_for_symbol(session, position.symbol)
            reports.append(report)
        except SymbolNotFoundException:
            continue

    logger.info("PnL report generated for %d symbols", len(reports))
    return reports
