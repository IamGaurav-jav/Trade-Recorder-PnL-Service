"""
Trade API endpoints: POST /trades, GET /trades
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.db import get_session
from app.exceptions import DuplicateTradeException, OversellException
from app.logger import logger
from app.models import Trade
from app.schemas import ErrorResponse, TradeCreateRequest, TradeResponse
from app.services import trade_service

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.post(
    "",
    response_model=TradeResponse,
    status_code=201,
    responses={
        200: {"model": TradeResponse, "description": "Duplicate trade (idempotent)"},
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Oversell rejected"},
    },
)
async def create_trade(
    trade_data: TradeCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Ingest a single trade.

    - Returns 201 if the trade is new.
    - Returns 200 if the trade is a duplicate (idempotent).
    - Returns 409 if the SELL would exceed the current position (oversell).
    """
    try:
        trade, is_new = await trade_service.ingest_trade(
            session=session,
            venue=trade_data.venue,
            trade_id=trade_data.trade_id,
            symbol=trade_data.symbol,
            side=trade_data.side.value,
            quantity=trade_data.quantity,
            price=trade_data.price,
            timestamp=trade_data.timestamp,
        )
        await session.commit()

        return TradeResponse(
            id=trade.id,
            venue=trade.venue,
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=trade.price,
            timestamp=trade.timestamp,
            created_at=trade.created_at,
            status="created",
        )

    except DuplicateTradeException as e:
        # Idempotent: return existing trade with 200
        logger.warning("Handling duplicate trade: %s", str(e))
        result = await session.execute(
            select(Trade).where(
                Trade.venue == trade_data.venue,
                Trade.trade_id == trade_data.trade_id,
            )
        )
        existing = result.scalar_one()
        return JSONResponse(
            status_code=200,
            content=TradeResponse(
                id=existing.id,
                venue=existing.venue,
                trade_id=existing.trade_id,
                symbol=existing.symbol,
                side=existing.side,
                quantity=existing.quantity,
                price=existing.price,
                timestamp=existing.timestamp,
                created_at=existing.created_at,
                status="duplicate_ignored",
            ).model_dump(mode="json"),
        )

    except OversellException as e:
        logger.error("Oversell error: %s", str(e))
        await session.rollback()
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="oversell_rejected",
                detail=str(e),
            ).model_dump(),
        )

    except Exception as e:
        logger.error("Unexpected error during trade ingestion: %s", str(e))
        await session.rollback()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while processing the trade.",
            ).model_dump(),
        )


@router.get("", response_model=list[TradeResponse])
async def list_trades(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    venue: Optional[str] = Query(None, description="Filter by venue"),
    session: AsyncSession = Depends(get_session),
):
    """List all trades, optionally filtered by symbol and/or venue."""
    try:
        query = select(Trade)
        if symbol:
            query = query.where(Trade.symbol == symbol)
        if venue:
            query = query.where(Trade.venue == venue)

        query = query.order_by(Trade.timestamp)
        result = await session.execute(query)
        trades = result.scalars().all()

        return [
            TradeResponse(
                id=t.id,
                venue=t.venue,
                trade_id=t.trade_id,
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                timestamp=t.timestamp,
                created_at=t.created_at,
            )
            for t in trades
        ]

    except Exception as e:
        logger.error("Error listing trades: %s", str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while listing trades.",
            ).model_dump(),
        )
