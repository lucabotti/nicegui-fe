import os
from typing import Any, cast

from keycloak import KeycloakOpenID
from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

# Keycloak configuration
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080").rstrip("/")
REALM = "test-realm"
CLIENT_ID = "nicegui-app"
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET")

# Add SessionMiddleware with a unique cookie name to avoid clashes with Keycloak
app.add_middleware(
    cast(Any, SessionMiddleware),
    secret_key="my_secret_key",
    session_cookie="nicegui_session",
)

# Initialize Keycloak OpenID
keycloak_openid = KeycloakOpenID(
    server_url=f"{KEYCLOAK_URL}/",
    client_id=CLIENT_ID,
    realm_name=REALM,
    client_secret_key=CLIENT_SECRET,
    verify=True,
)


@app.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate Keycloak login."""
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth"
    auth_url = keycloak_openid.auth_url(
        redirect_uri=redirect_uri,
        scope="openid profile email",
        state="some_state_string",
    )
    return RedirectResponse(url=auth_url)


@app.get("/auth")
async def auth(request: Request) -> RedirectResponse:
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

        app.storage.user.update(
            {
                "username": user_info.get("preferred_username"),
                "authenticated": True,
                "access_token": token["access_token"],
                "refresh_token": token["refresh_token"],
            }
        )
    except Exception as e:
        print(f"Authentication failed: {e}")

    return RedirectResponse(url="/")


def logout() -> None:
    """Clear session data and log out."""
    refresh_token = app.storage.user.get("refresh_token")
    if refresh_token:
        try:
            keycloak_openid.logout(refresh_token)
        except Exception as e:
            print(f"Logout failed: {e}")

    app.storage.user.clear()
    ui.navigate.to("/")


@ui.page("/")
def main_page() -> None:
    """The main application page."""
    authenticated = app.storage.user.get("authenticated", False)
    user = app.storage.user.get("username", "")

    with ui.header().classes("bg-primary text-white items-center justify-between"):
        with ui.row().classes("items-center"):
            ui.button(on_click=lambda: left_drawer.toggle()).props(
                "flat round icon=menu"
            )
            ui.label("NiceGUI App").classes("text-h6")

        with ui.row().classes("items-center gap-4"):
            if authenticated:
                ui.label(f"Welcome, {user}").classes("text-subtitle1")

            with ui.button(icon="account_circle").props("flat round color=white"):
                with ui.menu():
                    if authenticated:
                        ui.menu_item(
                            "Profile", on_click=lambda: ui.notify("Profile clicked")
                        )
                        ui.separator()
                        ui.menu_item("Logout", on_click=logout)
                    else:
                        ui.menu_item("Login", on_click=lambda: ui.navigate.to("/login"))

    with ui.left_drawer().classes("bg-slate-100") as left_drawer:
        ui.label("Main Menu").classes("text-h6 p-4")
        with ui.list().classes("w-full"):
            ui.item("Home", on_click=lambda: ui.navigate.to("/")).props(
                "clickable v-ripple"
            ).classes("px-4")
            ui.item("About", on_click=lambda: ui.notify("About clicked")).props(
                "clickable v-ripple"
            ).classes("px-4")
            if not authenticated:
                ui.item("Login", on_click=lambda: ui.navigate.to("/login")).props(
                    "clickable v-ripple"
                ).classes("px-4")
            else:
                ui.item("Logout", on_click=logout).props("clickable v-ripple").classes(
                    "px-4"
                ).mark("logout-item")

    with ui.column().classes("w-full items-center p-8"):
        if authenticated:
            ui.label(f"Hello {user}!").classes("text-h2 text-primary")
            ui.label("You are successfully logged in.").classes("text-xl text-gray-600")
        else:
            ui.label("Welcome to the App!").classes("text-h2 text-primary")
            ui.label("Please log in to access more features.").classes(
                "text-xl text-gray-600"
            )
            ui.button("Get Started", on_click=lambda: ui.navigate.to("/login")).classes(
                "mt-4 text-lg"
            )


if __name__ in {"__main__", "__mp_main__", "nicegui"}:
    # Start the application
    # We use Redis for session storage (app.storage.user)
    # The default redis_url is 'redis://localhost:6379'
    # In docker, we usually set REDIS_URL=redis://redis:6379
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    os.environ["NICEGUI_REDIS_URL"] = redis_url
    ui.run(
        port=8010,
        storage_secret="my_secret_key",
        # storage_type="redis",
        # redis_url=redis_url,
    )
