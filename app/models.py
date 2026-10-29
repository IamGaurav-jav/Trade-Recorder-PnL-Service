"""
SQLAlchemy ORM models for Trade, Position, and LatestPrice.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    """Stores every ingested trade. UNIQUE(venue, trade_id) enforces idempotency."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY or SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("venue", "trade_id", name="uq_venue_trade_id"),
        Index("ix_venue_trade_id", "venue", "trade_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trade(id={self.id}, venue={self.venue}, trade_id={self.trade_id}, "
            f"symbol={self.symbol}, side={self.side}, qty={self.quantity}, "
            f"price={self.price})>"
        )


class Position(Base):
    """Aggregated position per symbol: net quantity, total cost, and realized PnL."""

    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    net_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=Decimal("0")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def average_cost(self) -> Decimal:
        """Computed average cost = total_cost / net_quantity."""
        if self.net_quantity > 0:
            return self.total_cost / self.net_quantity
        return Decimal("0")

    def __repr__(self) -> str:
        return (
            f"<Position(symbol={self.symbol}, qty={self.net_quantity}, "
            f"avg_cost={self.average_cost}, realized_pnl={self.realized_pnl})>"
        )


class LatestPrice(Base):
    """Stores the latest market price per symbol, used for unrealized PnL."""

    __tablename__ = "latest_prices"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<LatestPrice(symbol={self.symbol}, price={self.price})>"
