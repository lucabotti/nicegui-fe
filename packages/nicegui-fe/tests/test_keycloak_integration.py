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
    import src.main

    reload(src.main)

    return src.main.app


@pytest.mark.asyncio
async def test_keycloak_metadata_discovery(
    keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify that the app can successfully discover Keycloak metadata.
    This proves the integration at the network level and configuration level.
    """
    from src.main import keycloak_openid

    # python-keycloak's well_known is called internally.
    # We can trigger it manually to verify.
    metadata = keycloak_openid.well_known()
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
    with (
        unittest.mock.patch("keycloak.KeycloakOpenID.token") as mock_token,
        unittest.mock.patch("keycloak.KeycloakOpenID.userinfo") as mock_userinfo,
        unittest.mock.patch("keycloak.KeycloakOpenID.decode_token") as mock_decode,
    ):
        mock_decode.return_value = {"realm_access": {"roles": []}}
        mock_token.return_value = {
            "access_token": "fake_access_token",
            "refresh_token": "fake_refresh_token",
        }
        mock_userinfo.return_value = {
            "preferred_username": "testuser",
            "email": "testuser@example.com",
        }

        await user.open("/auth?code=fake_code")
        await user.should_see("Hello testuser!")
        await user.should_see("Welcome, testuser")

        # Logout testuser
        with unittest.mock.patch("keycloak.KeycloakOpenID.logout") as mock_logout:
            user.find(marker="logout-item").click()
            await user.should_see("Welcome to the App!")
            mock_logout.assert_called_once()

    # 2. Test second user: testuser2
    with (
        unittest.mock.patch("keycloak.KeycloakOpenID.token") as mock_token,
        unittest.mock.patch("keycloak.KeycloakOpenID.userinfo") as mock_userinfo,
        unittest.mock.patch("keycloak.KeycloakOpenID.decode_token") as mock_decode,
    ):
        mock_decode.return_value = {"realm_access": {"roles": []}}
        mock_token.return_value = {
            "access_token": "fake_access_token_2",
            "refresh_token": "fake_refresh_token_2",
        }
        mock_userinfo.return_value = {
            "preferred_username": "testuser2",
            "email": "testuser2@example.com",
        }

        await user.open("/auth?code=fake_code_2")
        await user.should_see("Hello testuser2!")
        await user.should_see("Welcome, testuser2")

        # Logout testuser2
        with unittest.mock.patch("keycloak.KeycloakOpenID.logout") as mock_logout:
            user.find(marker="logout-item").click()
            await user.should_see("Welcome to the App!")
            mock_logout.assert_called_once()


@pytest.mark.asyncio
async def test_admin_menu_visibility(
    user: User, keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify that the Admin Menu is only visible to users with the 'admin' role.
    """
    # 1. Test user with admin role
    with (
        unittest.mock.patch("keycloak.KeycloakOpenID.token") as mock_token,
        unittest.mock.patch("keycloak.KeycloakOpenID.userinfo") as mock_userinfo,
        unittest.mock.patch("keycloak.KeycloakOpenID.decode_token") as mock_decode,
        unittest.mock.patch("keycloak.KeycloakOpenID.logout") as mock_logout,
    ):
        mock_token.return_value = {
            "access_token": "admin_access_token",
            "refresh_token": "admin_refresh_token",
        }
        mock_userinfo.return_value = {
            "preferred_username": "testadmin",
            "email": "testadmin@example.com",
        }
        mock_decode.return_value = {"realm_access": {"roles": ["admin", "user"]}}

        await user.open("/auth?code=admin_code")
        await user.should_see("Hello testadmin!")
        # Should see Admin Menu
        await user.should_see("Admin Menu")

        # Logout
        user.find(marker="logout-item").click()
        await user.should_see("Welcome to the App!")

    # 2. Test user WITHOUT admin role
    with (
        unittest.mock.patch("keycloak.KeycloakOpenID.token") as mock_token,
        unittest.mock.patch("keycloak.KeycloakOpenID.userinfo") as mock_userinfo,
        unittest.mock.patch("keycloak.KeycloakOpenID.decode_token") as mock_decode,
        unittest.mock.patch("keycloak.KeycloakOpenID.logout") as mock_logout,
    ):
        mock_token.return_value = {
            "access_token": "user_access_token",
            "refresh_token": "user_refresh_token",
        }
        mock_userinfo.return_value = {
            "preferred_username": "testuser",
            "email": "testuser@example.com",
        }
        mock_decode.return_value = {"realm_access": {"roles": ["user"]}}

        await user.open("/auth?code=user_code")
        await user.should_see("Hello testuser!")

        # Should NOT see Admin Menu
        await user.should_not_see("Admin Menu")

        # Logout
        user.find(marker="logout-item").click()
        await user.should_see("Welcome to the App!")


@pytest.mark.asyncio
async def test_account_management_access(
    user: User, keycloak_container: KeycloakContainer, keycloak_app
):
    """
    Verify that the Account Management link is visible after a successful login.
    """
    with (
        unittest.mock.patch("keycloak.KeycloakOpenID.token") as mock_token,
        unittest.mock.patch("keycloak.KeycloakOpenID.userinfo") as mock_userinfo,
        unittest.mock.patch("keycloak.KeycloakOpenID.decode_token") as mock_decode,
    ):
        mock_token.return_value = {
            "access_token": "acc_access_token",
            "refresh_token": "acc_refresh_token",
        }
        mock_userinfo.return_value = {
            "preferred_username": "acctestuser",
            "email": "acctestuser@example.com",
            "given_name": "Acc",
            "family_name": "Test",
        }
        mock_decode.return_value = {"realm_access": {"roles": ["user"]}}

        await user.open("/auth?code=acc_code")
        await user.should_see("Welcome, acctestuser")

        # The Account Management link should be present in the profile menu
        await user.should_see("Account Management")
