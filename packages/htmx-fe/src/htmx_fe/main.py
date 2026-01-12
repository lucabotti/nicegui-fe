import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from keycloak import KeycloakOpenID
from starlette.middleware.sessions import SessionMiddleware

# Keycloak configuration
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080").rstrip("/")
KEYCLOAK_EXTERNAL_URL = os.environ.get("KEYCLOAK_EXTERNAL_URL", KEYCLOAK_URL).rstrip(
    "/"
)
REALM = "test-realm"
CLIENT_ID = "nicegui-app"
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET")
SERVICE_URL = os.environ.get("SERVICE_URL", "http://127.0.0.1:8020").rstrip("/")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "my_secret_key")

app = FastAPI(title="HTMX Frontend")

# Add SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="htmx_session",
)

# Initialize Keycloak OpenID
keycloak_openid = KeycloakOpenID(
    server_url=f"{KEYCLOAK_URL}/",
    client_id=CLIENT_ID,
    realm_name=REALM,
    client_secret_key=CLIENT_SECRET,
    verify=True,
)

# Templates setup
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@app.get("/login")
async def login(request: Request):
    """Initiate Keycloak login."""
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth"

    auth_url = keycloak_openid.auth_url(
        redirect_uri=redirect_uri,
        scope="openid profile email",
        state="some_state_string",
    )
    auth_url = auth_url.replace(KEYCLOAK_URL, KEYCLOAK_EXTERNAL_URL)
    return RedirectResponse(url=auth_url)


@app.get("/auth")
async def auth(request: Request):
    """Handle Keycloak callback."""
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse(url="/")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth"

    try:
        token = keycloak_openid.token(
            grant_type="authorization_code", code=code, redirect_uri=redirect_uri
        )
        user_info = keycloak_openid.userinfo(token["access_token"])

        # Decode token to get roles
        expected_issuer = f"{KEYCLOAK_EXTERNAL_URL}/realms/{REALM}"
        try:
            decoded_token = keycloak_openid.decode_token(
                token["access_token"],
                validate=True,
                issuer=expected_issuer,
            )
        except Exception:
            try:
                decoded_token = keycloak_openid.decode_token(
                    token["access_token"], validate=True
                )
            except Exception:
                decoded_token = keycloak_openid.decode_token(
                    token["access_token"],
                    validate=True,
                    options={"verify_iss": False},
                )

        realm_access = decoded_token.get("realm_access", {})
        roles = realm_access.get("roles", [])

        # Store in session
        request.session["user"] = {
            "username": user_info.get("preferred_username"),
            "email": user_info.get("email"),
            "first_name": user_info.get("given_name"),
            "last_name": user_info.get("family_name"),
            "phone_number": user_info.get("phone_number"),
            "authenticated": True,
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "roles": roles,
            "user_info_raw": user_info,
        }
    except Exception as e:
        print(f"Authentication failed: {e}")

    return RedirectResponse(url="/")


@app.get("/logout")
async def logout(request: Request):
    """Clear session data and log out."""
    user = request.session.get("user")
    if user and user.get("refresh_token"):
        try:
            keycloak_openid.logout(user["refresh_token"])
        except Exception as e:
            print(f"Logout failed: {e}")

    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """The main application page."""
    user = request.session.get("user", {})
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "authenticated": user.get("authenticated", False),
            "keycloak_external_url": KEYCLOAK_EXTERNAL_URL,
            "realm": REALM,
        },
    )


@app.get("/service-call")
async def service_call(request: Request):
    """Call backend service via HTMX."""
    user = request.session.get("user")
    if not user or not user.get("access_token"):
        return templates.TemplateResponse(
            request,
            "partials/service_result.html",
            {"error": "Not authenticated"},
        )

    access_token = user["access_token"]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SERVICE_URL}/hello",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return templates.TemplateResponse(
                    request,
                    "partials/service_result.html",
                    {"data": data},
                )
            elif response.status_code == 403:
                return templates.TemplateResponse(
                    request,
                    "partials/service_result.html",
                    {"error": "Unauthorized: role2 required"},
                )
            else:
                return templates.TemplateResponse(
                    request,
                    "partials/service_result.html",
                    {"error": f"Error: {response.status_code}"},
                )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "partials/service_result.html",
            {"error": f"Service call failed: {e}"},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8011)
