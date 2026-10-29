"""
Price API endpoint: POST /prices
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.db import get_session
from app.logger import logger
from app.models import LatestPrice
from app.schemas import ErrorResponse, PriceResponse, PriceUpdateRequest

router = APIRouter(prefix="/prices", tags=["Prices"])


@router.post("", response_model=PriceResponse)
async def set_latest_price(
    price_data: PriceUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Set (upsert) the latest market price for a symbol."""
    try:
        result = await session.execute(
            select(LatestPrice).where(LatestPrice.symbol == price_data.symbol)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.price = price_data.price
            existing.updated_at = datetime.now(timezone.utc)
            logger.info(
                "Updated latest price for %s: %s",
                price_data.symbol, price_data.price,
            )
        else:
            existing = LatestPrice(
                symbol=price_data.symbol,
                price=price_data.price,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(existing)
            logger.info(
                "Set initial latest price for %s: %s",
                price_data.symbol, price_data.price,
            )

        await session.commit()

        return PriceResponse(
            symbol=existing.symbol,
            price=existing.price,
            updated_at=existing.updated_at,
        )

    except Exception as e:
        logger.error("Error setting price for %s: %s", price_data.symbol, str(e))
        await session.rollback()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while setting the price.",
            ).model_dump(),
        )
