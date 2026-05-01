import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from src.main import app


@pytest.mark.asyncio
async def test_health_ok():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    async def override_get_db():
        yield mock_session

    from src.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "connected"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_db_disconnected():
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB error")

    async def override_get_db():
        yield mock_session

    from src.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "disconnected"
    finally:
        app.dependency_overrides.clear()
