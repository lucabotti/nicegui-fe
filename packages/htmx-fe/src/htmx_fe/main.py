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
CONTACT_SVC_URL = os.environ.get(
    "CONTACT_SVC_URL", "http://api.localhost/contacts"
).rstrip("/")
ORG_SVC_URL = os.environ.get("ORG_SVC_URL", "http://api.localhost/orgs").rstrip("/")
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
        async with httpx.AsyncClient(follow_redirects=True) as client:
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


@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    """The contact management page."""
    user = request.session.get("user")
    if not user or not user.get("authenticated"):
        return RedirectResponse(url="/login")

    organizations = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{ORG_SVC_URL}/", timeout=10.0)
            if response.status_code == 200:
                organizations = response.json()
    except Exception as e:
        print(f"Error fetching organizations from {ORG_SVC_URL}: {e}")
        pass

    return templates.TemplateResponse(
        request,
        "contacts.html",
        {"user": user, "organizations": organizations},
    )


@app.get("/contacts/list", response_class=HTMLResponse)
async def list_contacts(request: Request):
    """List contacts via HTMX partial."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    contacts = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{CONTACT_SVC_URL}/", timeout=10.0)
            if response.status_code == 200:
                contacts = response.json()
    except Exception as e:
        print(f"Failed to fetch contacts from {CONTACT_SVC_URL}: {e}")

    return templates.TemplateResponse(
        request,
        "partials/contact_list.html",
        {"contacts": contacts},
    )


@app.post("/contacts", response_class=HTMLResponse)
async def create_contact(request: Request):
    """Create a new contact."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    form_data = await request.form()
    new_contact = {
        "first_name": form_data.get("first_name"),
        "last_name": form_data.get("last_name"),
        "role": form_data.get("role"),
        "organization_id": form_data.get("organization_id") or None,
        "tags": [t.strip() for t in form_data.get("tags", "").split(",") if t.strip()],
        "emails": [{"address": form_data.get("email")}],
        "phone_numbers": [{"number": form_data.get("phone")}],
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                f"{CONTACT_SVC_URL}/", json=new_contact, timeout=10.0
            )
            if response.status_code == 200:
                # After successful creation, return the updated list
                return await list_contacts(request)
            else:
                return HTMLResponse(
                    f"Error: {response.text}", status_code=response.status_code
                )
    except Exception as e:
        return HTMLResponse(f"Creation failed: {e}", status_code=500)


@app.delete("/contacts/{contact_id}")
async def delete_contact(request: Request, contact_id: int):
    """Delete a contact."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.delete(
                f"{CONTACT_SVC_URL}/{contact_id}", timeout=10.0
            )
            if response.status_code == 200:
                return HTMLResponse("")  # Empty response for outerHTML swap
            else:
                return HTMLResponse(
                    f"Error: {response.text}", status_code=response.status_code
                )
    except Exception as e:
        return HTMLResponse(f"Deletion failed: {e}", status_code=500)


@app.get("/organizations", response_class=HTMLResponse)
async def organizations_page(request: Request):
    """The organization management page."""
    user = request.session.get("user")
    if not user or not user.get("authenticated"):
        return RedirectResponse(url="/login")

    organizations = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{ORG_SVC_URL}/", timeout=10.0)
            if response.status_code == 200:
                organizations = response.json()
    except Exception as e:
        print(f"Error fetching organizations: {e}")

    return templates.TemplateResponse(
        request,
        "organizations.html",
        {"user": user, "organizations": organizations},
    )


@app.post("/organizations", response_class=HTMLResponse)
async def create_organization(request: Request):
    """Create a new organization."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    form_data = await request.form()
    org_name = form_data.get("name")
    if not org_name:
        return HTMLResponse("Name is required", status_code=400)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                f"{ORG_SVC_URL}/", json={"name": org_name}, timeout=10.0
            )
            if response.status_code == 200:
                # Refresh list (optimization: return just the new row or valid html list)
                # Re-fetching full list for simplicity in htmx swap
                return await list_organizations(request)
            else:
                return HTMLResponse(
                    f"Error: {response.text}", status_code=response.status_code
                )
    except Exception as e:
        return HTMLResponse(f"Creation failed: {e}", status_code=500)


@app.get("/organizations/list", response_class=HTMLResponse)
async def list_organizations(request: Request):
    """List organizations via HTMX partial."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    organizations = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{ORG_SVC_URL}/", timeout=10.0)
            if response.status_code == 200:
                organizations = response.json()
    except Exception as e:
        print(f"Failed to fetch organizations: {e}")

    return templates.TemplateResponse(
        request,
        "partials/organization_list.html",
        {"organizations": organizations},
    )


@app.delete("/organizations/{org_id}")
async def delete_organization(request: Request, org_id: int):
    """Delete an organization."""
    user = request.session.get("user")
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.delete(f"{ORG_SVC_URL}/{org_id}", timeout=10.0)
            if response.status_code == 200:
                return HTMLResponse("")  # Empty response for outerHTML swap
            else:
                return HTMLResponse(
                    f"Error: {response.text}", status_code=response.status_code
                )
    except Exception as e:
        return HTMLResponse(f"Deletion failed: {e}", status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8011)
