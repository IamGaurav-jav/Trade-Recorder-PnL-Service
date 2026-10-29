"""
Tests for idempotency.
Sending the same (venue, trade_id) twice should be counted only once.
"""

import pytest
from decimal import Decimal


TRADE_PAYLOAD = {
    "venue": "binance",
    "trade_id": "T-1001",
    "symbol": "BTC-USD",
    "side": "BUY",
    "quantity": "10",
    "price": "100",
    "timestamp": "2026-10-28T10:00:00Z",
}


@pytest.mark.asyncio
async def test_duplicate_trade_returns_200(client):
    """Sending the same trade twice: first should be 201, second should be 200."""
    # First submission
    response1 = await client.post("/trades", json=TRADE_PAYLOAD)
    assert response1.status_code == 201

    # Duplicate submission
    response2 = await client.post("/trades", json=TRADE_PAYLOAD)
    assert response2.status_code == 200

    data2 = response2.json()
    assert data2.get("status") == "duplicate_ignored" or data2.get("error") == "duplicate_ignored"


@pytest.mark.asyncio
async def test_duplicate_trade_position_unchanged(client):
    """After sending the same trade twice, position should reflect only one trade."""
    # Send trade twice
    await client.post("/trades", json=TRADE_PAYLOAD)
    await client.post("/trades", json=TRADE_PAYLOAD)

    # Check position — should be qty=10, NOT qty=20
    response = await client.get("/positions/BTC-USD")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["net_quantity"]) == Decimal("10")
    assert Decimal(data["total_cost"]) == Decimal("1000")
