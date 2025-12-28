import asyncio
from unittest.mock import patch

import pytest
from nicegui import ui
from nicegui.testing import User


# We patch the KeycloakOpenID class directly to ensure all instances are mocked
# especially the one created in main.py during import.
@pytest.fixture(autouse=True)
def mock_keycloak():
    with (
        patch(
            "keycloak.KeycloakOpenID.auth_url",
        ) as mock_auth_url,
        patch(
            "keycloak.KeycloakOpenID.token",
        ) as mock_token,
        patch(
            "keycloak.KeycloakOpenID.userinfo",
        ) as mock_userinfo,
        patch(
            "keycloak.KeycloakOpenID.logout",
        ) as mock_logout,
    ):
        mock_auth_url.return_value = "http://keycloak/auth"
        mock_token.return_value = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        }
        mock_userinfo.return_value = {
            "preferred_username": "mockuser",
            "email": "mockuser@example.com",
        }
        yield mock_auth_url, mock_token, mock_userinfo, mock_logout


@pytest.mark.asyncio
async def test_guest_view(user: User):
    """Verify the main page content for an unauthenticated user."""
    await user.open("/")
    await user.should_see("Welcome to the App!")
    await user.should_see("Please log in to access more features.")
    await user.should_see("Get Started")


@pytest.mark.asyncio
async def test_login_redirect(user: User, mock_keycloak):
    mock_auth_url, _, _, _ = mock_keycloak
    await user.open("/")
    user.find("Get Started").click()
    # We use sleep instead of user.wait
    await asyncio.sleep(0.1)
    # Verify auth_url was called
    assert mock_auth_url.called


@pytest.mark.asyncio
async def test_auth_callback_success(user: User, mock_keycloak):
    _, mock_token, mock_userinfo, _ = mock_keycloak

    # Simulate hitting the callback URL
    # Now that /auth returns a RedirectResponse to /, user.open should work
    await user.open("/auth?code=mock_code")

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
async def test_logout(user: User, mock_keycloak):
    """Verify that logging out works."""
    _, _, _, mock_logout = mock_keycloak

    # Log in first
    await user.open("/auth?code=mock_code")
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

    # Verify logout was called
    mock_logout.assert_called()
