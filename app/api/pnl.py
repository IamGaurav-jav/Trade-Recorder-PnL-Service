"""
PnL API endpoints: GET /pnl, GET /pnl/{symbol}
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.db import get_session
from app.exceptions import SymbolNotFoundException
from app.logger import logger
from app.schemas import ErrorResponse, PnLResponse
from app.services import pnl_service

router = APIRouter(prefix="/pnl", tags=["PnL"])


@router.get("", response_model=list[PnLResponse])
async def get_pnl_all(session: AsyncSession = Depends(get_session)):
    """Get PnL report for all symbols."""
    try:
        reports = await pnl_service.get_pnl_all(session)
        return reports

    except Exception as e:
        logger.error("Error generating PnL report: %s", str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while generating the PnL report.",
            ).model_dump(),
        )


@router.get("/{symbol}", response_model=PnLResponse)
async def get_pnl_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Get PnL report for a specific symbol."""
    try:
        report = await pnl_service.get_pnl_for_symbol(session, symbol)
        return report

    except SymbolNotFoundException as e:
        logger.warning("PnL not found: %s", str(e))
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="not_found",
                detail=str(e),
            ).model_dump(),
        )

    except Exception as e:
        logger.error("Error generating PnL for %s: %s", symbol, str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred while generating the PnL report.",
            ).model_dump(),
        )
