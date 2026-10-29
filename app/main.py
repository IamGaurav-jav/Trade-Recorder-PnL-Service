"""
FastAPI application entry point.
- Lifespan: creates database tables on startup, closes connection on shutdown.
- Global exception handlers for consistent JSON error responses.
- Includes all API routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.db import close_db, init_db
from app.exceptions import (
    DuplicateTradeException,
    OversellException,
    SymbolNotFoundException,
    TradeRecorderException,
)
from app.logger import logger


# ── Application Lifespan ─────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: close DB connection."""
    logger.info("Starting Trade Recorder & PnL Service...")
    await init_db()
    logger.info("Application started successfully")
    yield
    logger.info("Shutting down Trade Recorder & PnL Service...")
    await close_db()
    logger.info("Application shut down")


# ── FastAPI App ──────────────────────────────────────

app = FastAPI(
    title="Trade Recorder & PnL Service",
    description=(
        "A backend service that ingests trades from multiple venues, "
        "tracks positions using Average Cost, and reports realized & unrealized PnL. "
        "Features: idempotency, oversell prevention, and reconciliation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (open for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ───────────────────────


@app.exception_handler(OversellException)
async def oversell_exception_handler(request: Request, exc: OversellException):
    logger.error("Global handler: %s", str(exc))
    return JSONResponse(
        status_code=409,
        content={
            "error": "oversell_rejected",
            "detail": str(exc),
            "symbol": exc.symbol,
            "available": str(exc.available),
            "requested": str(exc.requested),
        },
    )


@app.exception_handler(DuplicateTradeException)
async def duplicate_trade_exception_handler(
    request: Request, exc: DuplicateTradeException
):
    logger.warning("Global handler: %s", str(exc))
    return JSONResponse(
        status_code=200,
        content={
            "error": "duplicate_ignored",
            "detail": str(exc),
            "venue": exc.venue,
            "trade_id": exc.trade_id,
        },
    )


@app.exception_handler(SymbolNotFoundException)
async def symbol_not_found_handler(request: Request, exc: SymbolNotFoundException):
    logger.warning("Global handler: %s", str(exc))
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "detail": str(exc),
            "symbol": exc.symbol,
        },
    )


@app.exception_handler(TradeRecorderException)
async def trade_recorder_exception_handler(
    request: Request, exc: TradeRecorderException
):
    logger.error("Global handler (generic): %s", str(exc))
    return JSONResponse(
        status_code=400,
        content={"error": "trade_recorder_error", "detail": str(exc)},
    )


# ── Include API Routers ─────────────────────────────

from app.api import pnl, positions, prices, reconciliation, trades  # noqa: E402

app.include_router(trades.router)
app.include_router(positions.router)
app.include_router(pnl.router)
app.include_router(prices.router)
app.include_router(reconciliation.router)


# ── Health Check ─────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "Trade Recorder & PnL Service"}
