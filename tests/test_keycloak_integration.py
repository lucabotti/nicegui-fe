import os
import unittest.mock
from importlib import reload

import pytest
from nicegui.testing import User
from testcontainers.keycloak import KeycloakContainer
from testcontainers.redis import RedisContainer


@pytest.fixture
def keycloak_app(
    keycloak_container: KeycloakContainer, redis_container: RedisContainer
):
    """
    Sets up the app to use the Keycloak and Redis containers.
    """
    # Keycloak setup
    base_url = keycloak_container.get_url()
    os.environ["KEYCLOAK_URL"] = base_url

    # Redis setup
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)
    os.environ["REDIS_URL"] = f"redis://{redis_host}:{redis_port}"

    # We need to reload the main module to ensure it picks up the new
    # environment variables
    import main

    reload(main)

    return main.app


@pytest.mark.asyncio
async def test_keycloak_metadata_discovery(
    keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify that the app can successfully discover Keycloak metadata.
    This proves the integration at the network level and configuration level.
    """
    from main import oauth

    # Authlib's load_server_metadata is called internally during registration
    # or first use. We can trigger it manually to verify.
    metadata = await oauth.keycloak.load_server_metadata()
    assert metadata is not None
    assert "issuer" in metadata
    assert "/realms/test-realm" in metadata["issuer"]


@pytest.mark.asyncio
async def test_auth_flow_with_multiple_users(
    user: User, keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify the auth flow works for multiple users.
    We'll test testuser and testuser2.
    """
    # 1. Test first user: testuser
    with unittest.mock.patch(
        "authlib.integrations.starlette_client.apps.StarletteOAuth2App.authorize_access_token"
    ) as mock_token:
        mock_token.return_value = {
            "userinfo": {
                "preferred_username": "testuser",
                "email": "testuser@example.com",
            }
        }

        await user.open("/auth")
        await user.should_see("Hello testuser!")
        await user.should_see("Welcome, testuser")

        # Logout testuser
        user.find(marker="logout-item").click()
        await user.should_see("Welcome to the App!")

    # 2. Test second user: testuser2
    with unittest.mock.patch(
        "authlib.integrations.starlette_client.apps.StarletteOAuth2App.authorize_access_token"
    ) as mock_token:
        mock_token.return_value = {
            "userinfo": {
                "preferred_username": "testuser2",
                "email": "testuser2@example.com",
            }
        }

        await user.open("/auth")
        await user.should_see("Hello testuser2!")
        await user.should_see("Welcome, testuser2")

        # Logout testuser2
        user.find(marker="logout-item").click()
        await user.should_see("Welcome to the App!")
