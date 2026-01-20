import pytest
from contact_svc.db import get_db
from contact_svc.main import app
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_contact(db_session):
    # Override get_db to use our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/contacts/",
            json={
                "role": "Developer",
                "organization_id": "1",
                "tags": ["python", "fastapi"],
                "emails": [{"address": "test@example.com"}],
                "phone_numbers": [{"number": "123456789"}],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "Developer"
    assert len(data["emails"]) == 1
    assert data["emails"][0]["address"] == "test@example.com"

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_contacts(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create one
        await ac.post(
            "/contacts/", json={"role": "Manager", "emails": [], "phone_numbers": []}
        )

        response = await ac.get("/contacts/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

    app.dependency_overrides.clear()
