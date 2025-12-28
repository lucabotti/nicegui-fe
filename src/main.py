import os
from typing import Any, cast

from authlib.integrations.starlette_client import OAuth
from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

# Keycloak configuration
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080")
REALM = "test-realm"
CLIENT_ID = "nicegui-app"
BASE_URL = f"{KEYCLOAK_URL}/realms/{REALM}"
CONF_URL = f"{BASE_URL}/.well-known/openid-configuration"

# Add SessionMiddleware with a unique cookie name to avoid clashes with Keycloak
app.add_middleware(
    cast(Any, SessionMiddleware),
    secret_key="my_secret_key",
    session_cookie="nicegui_session",
)

# Add SessionMiddleware for OAuth lib
# NiceGUI already uses sessions for app.storage.user, but Authlib needs Starlette's
# SessionMiddleware. We need to make sure we don't conflict.
# NiceGUI uses its own session management.
# Actually, NiceGUI provides `app.add_middleware`.

oauth = OAuth()
oauth.register(
    name="keycloak",
    client_id=CLIENT_ID,
    server_metadata_url=CONF_URL,
    client_kwargs={"scope": "openid profile email"},
)


@app.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate Keycloak login."""
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth"
    return await oauth.keycloak.authorize_redirect(request, redirect_uri)


@app.get("/auth")
async def auth(request: Request) -> RedirectResponse:
    """Handle Keycloak callback."""
    token = await oauth.keycloak.authorize_access_token(request)
    user = token.get("userinfo")
    if user:
        app.storage.user.update(
            {"username": user.get("preferred_username"), "authenticated": True}
        )
    return RedirectResponse(url="/")


def logout() -> None:
    """Clear session data and log out."""
    app.storage.user.clear()
    # Simple logout - clears local session.
    # For full Keycloak logout, we would redirect to KEYCLOAK logout endpoint.
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
    ui.run(
        port=8010,
        storage_secret="my_secret_key",
        storage_type="redis",
        redis_url=redis_url,
    )
