import pytest
from fastapi.testclient import TestClient
from keycloak import KeycloakOpenID
from testcontainers.keycloak import KeycloakContainer

from src.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_service_with_real_keycloak(
    keycloak_container: KeycloakContainer, test_client
):
    url = keycloak_container.get_url()

    # Configure internal client for test (like the service does)
    # We monkeypatch the config in the service
    from src import main

    main.KEYCLOAK_URL = url
    main.keycloak_openid = KeycloakOpenID(
        server_url=f"{url}/",
        client_id="nicegui-app",
        realm_name="test-realm",
        verify=True,
    )

    # Get a token for testuser2 (who has role2)
    keycloak_openid = KeycloakOpenID(
        server_url=f"{url}/",
        client_id="nicegui-app",
        realm_name="test-realm",
        verify=True,
    )

    token_info = keycloak_openid.token("testuser2", "user")
    access_token = token_info["access_token"]

    # Call the service using TestClient
    response = test_client.get(
        "/hello", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Hello testuser2!"


@pytest.mark.asyncio
async def test_service_unauthorized_with_real_keycloak(
    keycloak_container: KeycloakContainer, test_client
):
    url = keycloak_container.get_url()

    # Monkeypatch service config
    from src import main

    main.KEYCLOAK_URL = url
    main.keycloak_openid = KeycloakOpenID(
        server_url=f"{url}/",
        client_id="nicegui-app",
        realm_name="test-realm",
        verify=True,
    )

    # Get a token for testuser (who does NOT have role2)
    keycloak_openid = KeycloakOpenID(
        server_url=f"{url}/",
        client_id="nicegui-app",
        realm_name="test-realm",
        verify=True,
    )

    token_info = keycloak_openid.token("testuser", "user")
    access_token = token_info["access_token"]

    # Call the service
    response = test_client.get(
        "/hello", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 403
    assert "User does not have required role: role2" in response.json()["detail"]
