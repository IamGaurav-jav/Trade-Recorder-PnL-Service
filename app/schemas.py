"""
Pydantic request/response schemas with Decimal validation.
All monetary and quantity fields use Decimal — never float.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


# ── Trade Schemas ────────────────────────────────────


class TradeCreateRequest(BaseModel):
    """Request body for POST /trades."""

    venue: str = Field(..., min_length=1, examples=["binance"])
    trade_id: str = Field(..., min_length=1, examples=["T-1001"])
    symbol: str = Field(..., min_length=1, examples=["BTC-USD"])
    side: TradeSide
    quantity: Decimal = Field(..., examples=["10"])
    price: Decimal = Field(..., examples=["100"])
    timestamp: datetime

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price must be positive")
        return v


class TradeResponse(BaseModel):
    """Response body for a single trade."""

    id: int
    venue: str
    trade_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime
    created_at: datetime
    status: Optional[str] = None  # "created" or "duplicate_ignored"

    model_config = {"from_attributes": True}


# ── Position Schemas ─────────────────────────────────


class PositionResponse(BaseModel):
    """Response body for a position."""

    symbol: str
    net_quantity: Decimal
    average_cost: Decimal
    total_cost: Decimal
    realized_pnl: Decimal

    model_config = {"from_attributes": True}


# ── Price Schemas ────────────────────────────────────


class PriceUpdateRequest(BaseModel):
    """Request body for POST /prices."""

    symbol: str = Field(..., min_length=1, examples=["BTC-USD"])
    price: Decimal = Field(..., examples=["125"])

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price must be positive")
        return v


class PriceResponse(BaseModel):
    """Response body for a price update."""

    symbol: str
    price: Decimal
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── PnL Schemas ──────────────────────────────────────


class PnLResponse(BaseModel):
    """Profit & Loss report for a single symbol."""

    symbol: str
    net_quantity: Decimal
    average_cost: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    latest_price: Optional[Decimal] = None


# ── Reconciliation Schemas ───────────────────────────


class VenueStatementTrade(BaseModel):
    """A single trade from an external venue statement."""

    trade_id: str
    symbol: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    timestamp: datetime


class ReconciliationRequest(BaseModel):
    """Request body for POST /reconcile."""

    venue: str = Field(..., min_length=1)
    trades: list[VenueStatementTrade]


class MismatchDetail(BaseModel):
    """Details of a mismatched trade between our records and the venue statement."""

    trade_id: str
    stored: dict
    venue_statement: dict
    differences: list[str]


class ReconciliationResponse(BaseModel):
    """Response body for reconciliation results."""

    venue: str
    missing_trades: list[VenueStatementTrade]  # In statement, not in our DB
    extra_trades: list[TradeResponse]  # In our DB, not in statement
    mismatched_trades: list[MismatchDetail]


# ── Error Schema ─────────────────────────────────────


class ErrorResponse(BaseModel):
    """Consistent JSON error structure."""

    error: str
    detail: str
