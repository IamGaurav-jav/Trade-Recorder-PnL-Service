"""
Tests for PnL calculation.
Verifies the exact worked example from the assignment (Average Cost method).
"""

import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_worked_example_pnl(client):
    """
    Full worked example from the assignment (Average Cost column):
      1. BUY 10 @ 100
      2. BUY 10 @ 110
      3. SELL 5 @ 120
      4. Set latest price = 125

    Expected:
      - Quantity: 15
      - Average Cost: 105
      - Realized PnL: 75  (5 * (120 - 105))
      - Unrealized PnL: 300  ((125 - 105) * 15)
      - Total PnL: 375
    """
    # Step 1: BUY 10 @ 100
    r1 = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert r1.status_code == 201

    # Step 2: BUY 10 @ 110
    r2 = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "110",
        "timestamp": "2026-10-28T11:00:00Z",
    })
    assert r2.status_code == 201

    # Step 3: SELL 5 @ 120
    r3 = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-3",
        "symbol": "BTC-USD",
        "side": "SELL",
        "quantity": "5",
        "price": "120",
        "timestamp": "2026-10-28T12:00:00Z",
    })
    assert r3.status_code == 201

    # Step 4: Set latest price to 125
    price_resp = await client.post("/prices", json={
        "symbol": "BTC-USD",
        "price": "125",
    })
    assert price_resp.status_code == 200

    # Step 5: Check PnL
    pnl_resp = await client.get("/pnl/BTC-USD")
    assert pnl_resp.status_code == 200
    pnl = pnl_resp.json()

    assert Decimal(pnl["net_quantity"]) == Decimal("15")
    assert Decimal(pnl["average_cost"]) == Decimal("105")
    assert Decimal(pnl["realized_pnl"]) == Decimal("75")
    assert Decimal(pnl["unrealized_pnl"]) == Decimal("300")
    assert Decimal(pnl["total_pnl"]) == Decimal("375")
    assert Decimal(pnl["latest_price"]) == Decimal("125")


@pytest.mark.asyncio
async def test_pnl_without_latest_price(client):
    """PnL without a latest price should have unrealized_pnl = 0."""
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "ETH-USD",
        "side": "BUY",
        "quantity": "5",
        "price": "200",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    pnl_resp = await client.get("/pnl/ETH-USD")
    assert pnl_resp.status_code == 200
    pnl = pnl_resp.json()
    assert Decimal(pnl["unrealized_pnl"]) == Decimal("0")
    assert pnl["latest_price"] is None


@pytest.mark.asyncio
async def test_pnl_not_found(client):
    """PnL for a symbol with no trades should return 404."""
    response = await client.get("/pnl/FAKE-USD")
    assert response.status_code == 404
