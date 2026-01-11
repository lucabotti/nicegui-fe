import pytest
from keycloak import KeycloakOpenID
from testcontainers.keycloak import KeycloakContainer


@pytest.mark.asyncio
async def test_user_roles(keycloak_container: KeycloakContainer):
    # Get the base URL from the container
    url = keycloak_container.get_url()
    print(f"DEBUG: Keycloak URL: {url}")

    # Configure Keycloak client
    # Note: verify=True might fail if using self-signed certs or http, but testcontainers usually just exposes http port.
    keycloak_openid = KeycloakOpenID(
        server_url=url, client_id="nicegui-app", realm_name="test-realm", verify=True
    )

    # --- Test User 1 (testuser) ---
    # Expected: Has role1, does NOT have role2
    try:
        token_info = keycloak_openid.token("testuser", "user")
    except Exception as e:
        pytest.fail(f"Failed to get token for testuser: {e}")

    # keycloak_openid.token returns a dict with access_token, etc.
    access_token = token_info["access_token"]

    # Decode token to check roles. We verify signature using the public key from the server.
    # options={"verify_signature": True, "verify_aud": False, "exp": True}
    # verify_aud=False because the token might be issued for account or other clients too?
    # Usually publicClient=true in realm-export for "nicegui-app".

    # Simple decode with verify=False just to inspect claims if we trust the container environment,
    # but let's try to verify signature for correctness.
    # Verify token validity using UserInfo endpoint (server-side check)
    try:
        userinfo = keycloak_openid.userinfo(access_token)
    except Exception as e:
        pytest.fail(f"Failed to get userinfo for testuser: {e}")

    # Manual decode of access token payload to check roles
    # We trust the token because userinfo call succeeded.
    import json
    import base64

    # JWT is header.payload.signature
    payload_part = access_token.split(".")[1]
    # Padding
    payload_part += "=" * (-len(payload_part) % 4)
    decoded_payload = json.loads(base64.urlsafe_b64decode(payload_part))

    realm_roles = decoded_payload.get("realm_access", {}).get("roles", [])

    assert "role1" in realm_roles, f"testuser should have role1. Found: {realm_roles}"
    assert "role2" not in realm_roles, (
        f"testuser should NOT have role2. Found: {realm_roles}"
    )

    # Verify phone number claim
    assert "phone_number" in decoded_payload, "phone_number claim should be present"
    assert decoded_payload["phone_number"] == "918273645098", (
        f"Unexpected phone number: {decoded_payload.get('phone_number')}"
    )

    # --- Test User 2 (testuser2) ---
    # Expected: Has role2, does NOT have role1
    try:
        token_info2 = keycloak_openid.token("testuser2", "user")
    except Exception as e:
        pytest.fail(f"Failed to get token for testuser2: {e}")

    access_token2 = token_info2["access_token"]

    # Verify validity
    try:
        keycloak_openid.userinfo(access_token2)
    except Exception as e:
        pytest.fail(f"Failed to get userinfo for testuser2: {e}")

    payload_part2 = access_token2.split(".")[1]
    payload_part2 += "=" * (-len(payload_part2) % 4)
    decoded_payload2 = json.loads(base64.urlsafe_b64decode(payload_part2))

    realm_roles2 = decoded_payload2.get("realm_access", {}).get("roles", [])

    assert "role2" in realm_roles2, (
        f"testuser2 should have role2. Found: {realm_roles2}"
    )
    assert "role1" not in realm_roles2, (
        f"testuser2 should NOT have role1. Found: {realm_roles2}"
    )

    # Verify phone number claim for user 2
    assert "phone_number" in decoded_payload2, (
        "phone_number claim should be present for user2"
    )
    assert decoded_payload2["phone_number"] == "564738291023", (
        f"Unexpected phone number for user2: {decoded_payload2.get('phone_number')}"
    )
