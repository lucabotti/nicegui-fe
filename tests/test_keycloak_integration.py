import os
import unittest.mock
from importlib import reload

import pytest
from nicegui.testing import User
from testcontainers.keycloak import KeycloakContainer


@pytest.fixture
def keycloak_app(keycloak_container: KeycloakContainer):
    """
    Sets up the app to use the Keycloak container.
    """
    # Get the internal URL of the container (host and port)
    # For tests running on the same host, we use get_url()
    base_url = keycloak_container.get_url()

    # Update environment variable
    os.environ["KEYCLOAK_URL"] = base_url

    # We need to reload the main module to ensure it picks up the new KEYCLOAK_URL
    # and registers the OAuth client with the correct metadata URL.
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
async def test_auth_flow_with_real_keycloak(
    user: User, keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify the auth callback still works.
    In a full integration test, we would want to perform the real code exchange,
    but here we can verify that if we provide a valid-looking mocked token
    response that matches what we expect from Keycloak, the app handles it.

    To truly test the integration, we'll verify the login button redirects
    to the correct Keycloak URL.
    """
    # 1. Verify Guest View
    await user.open("/")
    await user.should_see("Welcome to the App!")

    # 2. Verify Login Redirect points to the real Keycloak container
    # We use httpx.AsyncClient to check the redirect response
    import httpx

    transport = httpx.ASGITransport(app=keycloak_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/login")
        assert response.status_code == 302
        assert keycloak_container.get_url() in response.headers["location"]
        assert (
            "realms/test-realm/protocol/openid-connect/auth"
            in response.headers["location"]
        )

    # 3. Simulate a successful auth callback (Mocking the token exchange part)
    # This is still partially mocked because simulating a browser login in Keycloak
    # is complex without Playwright. However, we have verified the redirect URL!
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
