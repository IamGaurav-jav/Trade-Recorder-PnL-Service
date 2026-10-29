"""
Position API endpoints: GET /positions, GET /positions/{symbol}
"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.db import get_session
from app.logger import logger
from app.models import Position
from app.schemas import ErrorResponse, PositionResponse

router = APIRouter(prefix="/positions", tags=["Positions"])


@router.get("", response_model=list[PositionResponse])
async def list_positions(session: AsyncSession = Depends(get_session)):
    """List all positions with average cost."""
    try:
        result = await session.execute(select(Position))
        positions = result.scalars().all()

        return [
            PositionResponse(
                symbol=p.symbol,
                net_quantity=p.net_quantity,
                average_cost=p.average_cost,
                total_cost=p.total_cost,
                realized_pnl=p.realized_pnl,
            )
            for p in positions
        ]

    except Exception as e:
        logger.error("Error listing positions: %s", str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while listing positions.",
            ).model_dump(),
        )


@router.get("/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Get position for a specific symbol."""
    try:
        result = await session.execute(
            select(Position).where(Position.symbol == symbol)
        )
        position = result.scalar_one_or_none()

        if position is None:
            logger.warning("Position not found for symbol: %s", symbol)
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="not_found",
                    detail=f"No position found for symbol: {symbol}",
                ).model_dump(),
            )

        return PositionResponse(
            symbol=position.symbol,
            net_quantity=position.net_quantity,
            average_cost=position.average_cost if position.net_quantity > Decimal("0") else Decimal("0"),
            total_cost=position.total_cost,
            realized_pnl=position.realized_pnl,
        )

    except Exception as e:
        logger.error("Error fetching position for %s: %s", symbol, str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while fetching the position.",
            ).model_dump(),
        )
