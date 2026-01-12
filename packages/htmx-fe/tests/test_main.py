from unittest.mock import patch

from fastapi.testclient import TestClient

# Mock the entire keycloak module or just the instance in main
with patch("keycloak.KeycloakOpenID"):
    from htmx_fe.main import app, keycloak_openid

client = TestClient(app)


def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "HTMX App" in response.text
    assert "Welcome to the App!" in response.text


def test_login_redirect():
    with patch.object(keycloak_openid, "auth_url") as mock_auth_url:
        mock_auth_url.return_value = (
            "http://keycloak:8080/realms/test-realm/protocol/openid-connect/auth?..."
        )
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 307
        assert (
            "realms/test-realm/protocol/openid-connect/auth"
            in response.headers["location"]
        )


def test_logout_redirect():
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/"
