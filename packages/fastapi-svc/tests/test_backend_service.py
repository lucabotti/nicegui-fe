from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest
from src.main import app

client = TestClient(app)


@pytest.fixture
def mock_keycloak():
    with patch("src.main.keycloak_openid.decode_token") as mock_decode:
        yield mock_decode


def test_hello_unauthenticated():
    response = client.get("/hello")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_hello_authorized(mock_keycloak):
    mock_keycloak.return_value = {
        "preferred_username": "testuser",
        "realm_access": {"roles": ["role2"]},
    }

    response = client.get("/hello", headers={"Authorization": "Bearer mock_token"})

    assert response.status_code == 200
    assert response.json()["message"] == "Hello testuser!"
    assert "decoded_token" in response.json()


def test_hello_unauthorized(mock_keycloak):
    mock_keycloak.return_value = {
        "preferred_username": "testuser",
        "realm_access": {"roles": ["role1"]},  # Missing role2
    }

    response = client.get("/hello", headers={"Authorization": "Bearer mock_token"})

    assert response.status_code == 403
    assert "User does not have required role: role2" in response.json()["detail"]


def test_hello_invalid_token(mock_keycloak):
    mock_keycloak.side_effect = Exception("Invalid token")

    response = client.get("/hello", headers={"Authorization": "Bearer invalid_token"})

    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]
