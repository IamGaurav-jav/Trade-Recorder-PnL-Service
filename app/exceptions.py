"""
Custom domain exceptions and error response structure.
Each exception maps to a specific HTTP status code via global handlers in main.py.
"""

from decimal import Decimal


class TradeRecorderException(Exception):
    """Base exception for all Trade Recorder errors."""
    pass


class OversellException(TradeRecorderException):
    """Raised when a SELL would take a position below zero."""

    def __init__(self, symbol: str, available: Decimal, requested: Decimal):
        self.symbol = symbol
        self.available = available
        self.requested = requested
        super().__init__(
            f"Oversell rejected for {symbol}: "
            f"available={available}, requested={requested}"
        )


class DuplicateTradeException(TradeRecorderException):
    """Raised when a trade with the same (venue, trade_id) already exists."""

    def __init__(self, venue: str, trade_id: str):
        self.venue = venue
        self.trade_id = trade_id
        super().__init__(
            f"Duplicate trade ignored: venue={venue}, trade_id={trade_id}"
        )


class SymbolNotFoundException(TradeRecorderException):
    """Raised when a requested symbol has no position or price data."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"Symbol not found: {symbol}")
