import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from nicegui import ui
from nicegui.testing import User
from starlette.responses import RedirectResponse


# We patch the OAuth class directly to ensure all instances are mocked
# especially the one created in main.py during import.
@pytest.fixture(autouse=True)
def mock_oauth():
    with (
        patch(
            "authlib.integrations.starlette_client.apps.StarletteOAuth2App.authorize_redirect",
            new_callable=AsyncMock,
        ) as mock_redir,
        patch(
            "authlib.integrations.starlette_client.apps.StarletteOAuth2App.authorize_access_token",
            new_callable=AsyncMock,
        ) as mock_token,
    ):
        mock_redir.return_value = RedirectResponse(url="http://keycloak/auth")
        mock_token.return_value = {
            "userinfo": {
                "preferred_username": "mockuser",
                "email": "mockuser@example.com",
            }
        }
        yield mock_redir, mock_token


@pytest.mark.asyncio
async def test_guest_view(user: User):
    """Verify the main page content for an unauthenticated user."""
    await user.open("/")
    await user.should_see("Welcome to the App!")
    await user.should_see("Please log in to access more features.")
    await user.should_see("Get Started")


@pytest.mark.asyncio
async def test_login_redirect(user: User, mock_oauth):
    mock_redir, _ = mock_oauth
    await user.open("/")
    user.find("Get Started").click()
    # We use sleep instead of user.wait
    await asyncio.sleep(0.1)
    # Verify authorize_redirect was called
    assert mock_redir.called


@pytest.mark.asyncio
async def test_auth_callback_success(user: User, mock_oauth):
    _, mock_token = mock_oauth

    # Simulate hitting the callback URL
    # Now that /auth returns a RedirectResponse to /, user.open should work
    await user.open("/auth")

    # After callback, user should be redirected to home and see welcome message
    await user.should_see("Hello mockuser!")
    await user.should_see("Welcome, mockuser")


@pytest.mark.asyncio
async def test_profile_icon_present(user: User):
    """Verify that the profile icon is present on the main page."""
    await user.open("/")
    found = False
    for button in user.find(ui.button).elements:
        if "account_circle" in str(button.props):
            found = True
            break
    assert found


@pytest.mark.asyncio
async def test_logout(user: User, mock_oauth):
    """Verify that logging out works."""
    # Log in first
    await user.open("/auth")
    await user.should_see("Welcome, mockuser")

    # The Logout element might be hard to click if it's in a menu
    # There are two: one in the profile menu and one in the drawer.
    # Let's target the one in the drawer using its marker.
    user.find(marker="logout-item").click()

    # Wait for logout and redirect
    await asyncio.sleep(0.5)

    # After logout, should see guest view
    await user.should_see("Welcome to the App!")
    await user.should_not_see("Welcome, mockuser")
