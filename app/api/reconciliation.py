"""
Reconciliation API endpoint: POST /reconcile
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.db import get_session
from app.logger import logger
from app.schemas import ErrorResponse, ReconciliationRequest, ReconciliationResponse
from app.services import reconciliation_service

router = APIRouter(prefix="/reconcile", tags=["Reconciliation"])


@router.post("", response_model=ReconciliationResponse)
async def reconcile_trades(
    request: ReconciliationRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Compare an external venue trade statement against stored trades.
    Reports missing, extra, and mismatched trades.
    """
    try:
        result = await reconciliation_service.reconcile(
            session=session,
            venue=request.venue,
            statement_trades=request.trades,
        )
        return result

    except Exception as e:
        logger.error("Error during reconciliation for venue %s: %s", request.venue, str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred during reconciliation.",
            ).model_dump(),
        )
