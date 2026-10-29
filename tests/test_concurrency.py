"""
Concurrency tests.
Each request gets its own database session on a file-backed SQLite database,
so these requests genuinely race (unlike the shared-session `client` fixture).
"""

import asyncio
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.models import Base


def _trade(trade_id, side="BUY", quantity="10", price="100", symbol="BTC-USD", venue="binance"):
    return {
        "venue": venue,
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "timestamp": "2026-10-28T10:00:00Z",
    }


@pytest_asyncio.fixture
async def race_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'race.db'}")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def per_request_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = per_request_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_simultaneous_duplicates_counted_once(race_client):
    """The same (venue, trade_id) sent 20 times at once: one 201, the rest 200."""
    responses = await asyncio.gather(
        *[race_client.post("/trades", json=_trade("T-1001")) for _ in range(20)]
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [200] * 19 + [201]

    trades = (await race_client.get("/trades")).json()
    assert len(trades) == 1

    position = (await race_client.get("/positions/BTC-USD")).json()
    assert Decimal(position["net_quantity"]) == Decimal("10")
    assert Decimal(position["total_cost"]) == Decimal("1000")


@pytest.mark.asyncio
async def test_simultaneous_distinct_buys_all_applied(race_client):
    """Concurrent BUYs on a brand-new symbol must all succeed without lost updates."""
    responses = await asyncio.gather(
        *[
            race_client.post("/trades", json=_trade(f"T-{i}", quantity="1", price="100"))
            for i in range(20)
        ]
    )

    assert all(r.status_code == 201 for r in responses)

    position = (await race_client.get("/positions/BTC-USD")).json()
    assert Decimal(position["net_quantity"]) == Decimal("20")
    assert Decimal(position["total_cost"]) == Decimal("2000")


@pytest.mark.asyncio
async def test_simultaneous_sells_cannot_oversell(race_client):
    """Position of 10 and five concurrent SELLs of 4: only two fit, three get 409."""
    await race_client.post("/trades", json=_trade("B-1", quantity="10"))

    responses = await asyncio.gather(
        *[
            race_client.post("/trades", json=_trade(f"S-{i}", side="SELL", quantity="4", price="110"))
            for i in range(5)
        ]
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201, 201, 409, 409, 409]

    position = (await race_client.get("/positions/BTC-USD")).json()
    assert Decimal(position["net_quantity"]) == Decimal("2")
    assert Decimal(position["realized_pnl"]) == Decimal("80")


@pytest.mark.asyncio
async def test_same_trade_id_on_different_symbols_counted_once(race_client):
    """The UNIQUE constraint backstops races that lock different symbol rows."""
    responses = await asyncio.gather(
        race_client.post("/trades", json=_trade("T-X", symbol="BTC-USD")),
        race_client.post("/trades", json=_trade("T-X", symbol="ETH-USD")),
    )

    assert sorted(r.status_code for r in responses) == [200, 201]
    assert len((await race_client.get("/trades")).json()) == 1
