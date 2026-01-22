import os
from typing import Any, cast

import httpx
from keycloak import KeycloakOpenID
from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse


class State:
    def __init__(self, value: Any = None):
        self._value = value

    @property
    def value(self):
        return self._value

    def set_value(self, value: Any):
        self._value = value


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

# Add SessionMiddleware with a unique cookie name to avoid clashes with Keycloak
# We check if middleware is already added to support module reloading in tests
if not any(
    m.cls == SessionMiddleware for m in app.user_middleware if hasattr(m, "cls")
):
    app.add_middleware(
        cast(Any, SessionMiddleware),
        secret_key="my_secret_key",
        session_cookie="nicegui_session",
    )

# Initialize Keycloak OpenID for all server-side calls
# (token exchange, userinfo, validation)
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
    # Generate auth URL using internal instance, then fix URL for browser
    auth_url = keycloak_openid.auth_url(
        redirect_uri=redirect_uri,
        scope="openid profile email",
        state="some_state_string",
    )
    auth_url = auth_url.replace(KEYCLOAK_URL, KEYCLOAK_EXTERNAL_URL)
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

        # Decode token to get roles
        # Note: We use Keycloak internal URL for certs but the issuer is usually the external one
        expected_issuer = f"{KEYCLOAK_EXTERNAL_URL}/realms/{REALM}"
        try:
            # First try with the most likely issuer for this environment
            decoded_token = keycloak_openid.decode_token(
                token["access_token"],
                validate=True,
                issuer=expected_issuer,
            )
        except Exception:
            try:
                # Try internal issuer as secondary option
                decoded_token = keycloak_openid.decode_token(
                    token["access_token"], validate=True
                )
            except Exception:
                # Last resort: disable issuer verification
                decoded_token = keycloak_openid.decode_token(
                    token["access_token"],
                    validate=True,
                    options={"verify_iss": False},
                )

        realm_access = decoded_token.get("realm_access", {})
        roles = realm_access.get("roles", [])

        app.storage.user.update(
            {
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
    roles = app.storage.user.get("roles", [])
    email = app.storage.user.get("email", "")
    first_name = app.storage.user.get("first_name", "")
    last_name = app.storage.user.get("last_name", "")
    phone_number = app.storage.user.get("phone_number", "")
    user_info_raw = app.storage.user.get("user_info_raw", {})

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
                        ui.menu_item(f"{first_name} {last_name}").props("disabled")
                        ui.menu_item(email).props("disabled")
                        if phone_number:
                            ui.menu_item(phone_number).props("disabled")
                        ui.menu_item(f"Roles: {', '.join(roles)}").props("disabled")
                        ui.separator()
                        account_management_url = (
                            f"{KEYCLOAK_EXTERNAL_URL}/realms/{REALM}/account/"
                        )
                        ui.menu_item(
                            "Account Management",
                            on_click=lambda: ui.navigate.to(
                                account_management_url, new_tab=True
                            ),
                        )
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
            ui.item("Contacts", on_click=lambda: ui.navigate.to("/contacts")).props(
                "clickable v-ripple"
            ).classes("px-4")
            ui.item(
                "Organizations", on_click=lambda: ui.navigate.to("/organizations")
            ).props("clickable v-ripple").classes("px-4")
            if not authenticated:
                ui.item("Login", on_click=lambda: ui.navigate.to("/login")).props(
                    "clickable v-ripple"
                ).classes("px-4")
            else:
                if "role2" in roles:
                    ui.item(
                        "Role 2 Menu", on_click=lambda: ui.notify("Role 2 clicked")
                    ).props("clickable v-ripple").classes("px-4")
                if "admin" in roles:
                    ui.item(
                        "Admin Menu", on_click=lambda: ui.notify("Admin menu clicked")
                    ).props("clickable v-ripple").classes("px-4").mark(
                        "admin-menu-item"
                    )

                ui.item("Logout", on_click=logout).props("clickable v-ripple").classes(
                    "px-4"
                ).mark("logout-item")

    with ui.column().classes("w-full items-center p-8"):
        if authenticated:
            ui.label(f"Hello {user}!").classes("text-h2 text-primary")
            ui.label("You are successfully logged in.").classes("text-xl text-gray-600")

            with ui.card().classes("w-full mt-8"):
                ui.label("User Information From Keycloak").classes("text-h6 mb-4")
                ui.json_editor({"content": {"json": user_info_raw}}).classes(
                    "w-full"
                ).props("read-only")

            with ui.card().classes("w-full mt-8"):
                ui.label("Contacts").classes("text-h6 mb-4")
                ui.label("Manage your contacts and organizations.").classes("mb-4")
                ui.button(
                    "Go to Contacts", on_click=lambda: ui.navigate.to("/contacts")
                ).classes("w-full")

            with ui.card().classes("w-full mt-8"):
                ui.label("Backend Service Interaction").classes("text-h6 mb-4")

                async def call_backend_service():
                    access_token = app.storage.user.get("access_token")
                    if not access_token:
                        ui.notify("Not authenticated", type="negative")
                        return

                    result_area.clear()
                    with result_area:
                        ui.spinner(size="lg")

                    try:
                        async with httpx.AsyncClient(follow_redirects=True) as client:
                            response = await client.get(
                                f"{SERVICE_URL}/hello",
                                headers={"Authorization": f"Bearer {access_token}"},
                                timeout=10.0,
                            )

                            result_area.clear()
                            if response.status_code == 200:
                                data = response.json()
                                ui.notify(data["message"], type="positive")
                                with result_area:
                                    ui.label("Response from service:").classes(
                                        "font-bold"
                                    )
                                    ui.json_editor({"content": {"json": data}}).classes(
                                        "w-full"
                                    )
                            elif response.status_code == 403:
                                ui.notify(
                                    "Unauthorized: role2 required", type="negative"
                                )
                                with result_area:
                                    ui.label(
                                        "Error: User does not have required role: role2"
                                    ).classes("text-red")
                            else:
                                ui.notify(
                                    f"Error: {response.status_code}", type="negative"
                                )
                                with result_area:
                                    ui.label(
                                        f"Error: {response.status_code} - "
                                        f"{response.text}"
                                    ).classes("text-red")
                    except Exception as e:
                        ui.notify(f"Service call failed: {e}", type="negative")
                        result_area.clear()
                        with result_area:
                            ui.label(f"Connection Error: {e}").classes("text-red")

                ui.button(
                    "Call Authenticated Service", on_click=call_backend_service
                ).classes("w-full")
                result_area = ui.column().classes("w-full mt-4")
        else:
            ui.label("Welcome to the App!").classes("text-h2 text-primary")
            ui.label("Please log in to access more features.").classes(
                "text-xl text-gray-600"
            )
            ui.button("Get Started", on_click=lambda: ui.navigate.to("/login")).classes(
                "mt-4 text-lg"
            )


@ui.page("/contacts")
async def contacts_page() -> None:
    """The contact management page."""
    authenticated = app.storage.user.get("authenticated", False)
    if not authenticated:
        ui.navigate.to("/login")
        return

    user = app.storage.user.get("username", "")

    async def get_contacts():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(f"{CONTACT_SVC_URL}/", timeout=10.0)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                ui.notify(f"Failed to fetch contacts: {e}", type="negative")
        return []

    async def get_organizations():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(f"{ORG_SVC_URL}/", timeout=10.0)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                ui.notify(f"Failed to fetch organizations: {e}", type="negative")
        return []

    async def add_contact():
        new_contact = {
            "first_name": first_name_input.value,
            "last_name": last_name_input.value,
            "role": role_input.value,
            "organization_id": str(org_select.value) if org_select.value else None,
            "tags": tags_input.value.split(",") if tags_input.value else [],
            "emails": [
                {"address": row.default_slot.children[0].value}
                for row in emails_container
                if row.default_slot.children[0].value
            ],
            "phone_numbers": [
                {"number": row.default_slot.children[0].value}
                for row in phones_container
                if row.default_slot.children[0].value
            ],
        }
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                if editing_contact_id.value:
                    response = await client.patch(
                        f"{CONTACT_SVC_URL}/{editing_contact_id.value}",
                        json=new_contact,
                        timeout=10.0,
                    )
                else:
                    response = await client.post(
                        f"{CONTACT_SVC_URL}/", json=new_contact, timeout=10.0
                    )

                if response.status_code == 200:
                    ui.notify("Success", type="positive")
                    cancel_contact_edit()
                    await refresh_contacts()
                else:
                    print(f"Error adding contact: {response.text}")
                    ui.notify(f"Error: {response.text}", type="negative")
            except Exception as e:
                ui.notify(f"Operation failed: {e}", type="negative")

    async def delete_contact(contact_id: int):
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.delete(
                    f"{CONTACT_SVC_URL}/{contact_id}", timeout=10.0
                )
                if response.status_code == 200:
                    ui.notify("Contact deleted", type="positive")
                    await refresh_contacts()
                else:
                    ui.notify(
                        f"Error deleting contact: {response.text}", type="negative"
                    )
            except Exception as e:
                ui.notify(f"Failed to delete contact: {e}", type="negative")

    def start_contact_edit(contact: dict):
        editing_contact_id.set_value(contact["id"])
        first_name_input.set_value(contact["first_name"])
        last_name_input.set_value(contact["last_name"])
        role_input.set_value(contact["role"])
        # Find org ID from name if needed, but the row should have org_id if we include it
        # Let's ensure load_data includes org_id
        org_select.set_value(contact.get("organization_id"))
        emails_container.clear()
        for email in contact.get("emails", []):
            add_email_field(email["address"])
        if not contact.get("emails"):
            add_email_field()

        phones_container.clear()
        for phone in contact.get("phone_numbers", []):
            add_phone_field(phone["number"])
        if not contact.get("phone_numbers"):
            add_phone_field()

        tags_input.set_value(contact["tags"])

        add_contact_btn.set_text("Save Changes")
        cancel_contact_btn.set_visibility(True)
        ui.notify(f"Editing contact {contact['id']}")

    def cancel_contact_edit():
        editing_contact_id.set_value(None)
        first_name_input.set_value("")
        last_name_input.set_value("")
        role_input.set_value("")
        org_select.set_value(None)

        emails_container.clear()
        add_email_field()

        phones_container.clear()
        add_phone_field()

        tags_input.set_value("")
        add_contact_btn.set_text("Add")
        cancel_contact_btn.set_visibility(False)

    async def refresh_contacts():
        await table.update_rows()

    editing_contact_id = State(None)

    with ui.header().classes("bg-primary text-white items-center justify-between"):
        ui.label("Contact Management").classes("text-h6 ml-4")
        ui.button("Back Home", on_click=lambda: ui.navigate.to("/")).props(
            "flat color=white"
        )

    with ui.column().classes("w-full p-8 gap-8"):
        with ui.card().classes("w-full p-6"):
            ui.label("Add/Edit Contact").classes("text-h5 mb-4")
            with ui.row().classes("w-full items-end gap-4"):
                first_name_input = ui.input("First Name").classes("flex-1")
                last_name_input = ui.input("Last Name").classes("flex-1")
                role_input = ui.input("Role").classes("flex-1")
                orgs = await get_organizations()
                org_select = ui.select(
                    {o["id"]: o["name"] for o in orgs}, label="Organization"
                ).classes("flex-1")

                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Emails")
                    emails_container = ui.column().classes("w-full gap-2")

                    def add_email_field(value=""):
                        with emails_container:
                            with ui.row().classes("w-full items-center gap-2") as row:
                                ui.input(value=value, placeholder="Email").classes(
                                    "flex-1"
                                )
                                ui.button(
                                    icon="delete",
                                    color="negative",
                                    on_click=lambda: emails_container.remove(row),
                                ).props("flat round dense")

                    ui.button(
                        "Add Email", on_click=lambda: add_email_field(), icon="add"
                    ).props("flat dense")
                    add_email_field()  # Add initial field

                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Phone Numbers")
                    phones_container = ui.column().classes("w-full gap-2")

                    def add_phone_field(value=""):
                        with phones_container:
                            with ui.row().classes("w-full items-center gap-2") as row:
                                ui.input(value=value, placeholder="Phone").classes(
                                    "flex-1"
                                )
                                ui.button(
                                    icon="delete",
                                    color="negative",
                                    on_click=lambda: phones_container.remove(row),
                                ).props("flat round dense")

                    ui.button(
                        "Add Phone", on_click=lambda: add_phone_field(), icon="add"
                    ).props("flat dense")
                    add_phone_field()  # Add initial field

                tags_input = ui.input("Tags (comma separated)").classes("flex-1")
                add_contact_btn = ui.button("Add", on_click=add_contact).classes("mb-1")
                cancel_contact_btn = ui.button(
                    "Cancel", on_click=cancel_contact_edit, color="grey"
                ).classes("mb-1")
                cancel_contact_btn.set_visibility(False)

        with ui.card().classes("w-full p-6"):
            ui.label("Contact List").classes("text-h5 mb-4")

            columns = [
                {
                    "name": "first_name",
                    "label": "First Name",
                    "field": "first_name",
                    "align": "left",
                },
                {
                    "name": "last_name",
                    "label": "Last Name",
                    "field": "last_name",
                    "align": "left",
                },
                {
                    "name": "role",
                    "label": "Role",
                    "field": "role",
                    "required": True,
                    "align": "left",
                },
                {
                    "name": "org",
                    "label": "Organization",
                    "field": "organization_name",
                    "align": "left",
                },
                {
                    "name": "emails",
                    "label": "Emails",
                    "field": "emails",
                    "align": "left",
                },
                {
                    "name": "phones",
                    "label": "Phones",
                    "field": "phone_numbers",
                    "align": "left",
                },
                {"name": "tags", "label": "Tags", "field": "tags", "align": "left"},
                {"name": "actions", "label": "Actions", "field": "id"},
            ]

            async def load_data():
                data = await get_contacts()
                rows = []
                for c in data:
                    rows.append(
                        {
                            "id": c["id"],
                            "first_name": c.get("first_name", ""),
                            "last_name": c.get("last_name", ""),
                            "role": c["role"],
                            "organization_id": c.get("organization_id"),
                            "organization_name": c.get("organization_name", "Unknown"),
                            "emails": ", ".join([e["address"] for e in c["emails"]]),
                            "phone_numbers": ", ".join(
                                [p["number"] for p in c["phone_numbers"]]
                            ),
                            "tags": ", ".join(c["tags"]),
                        }
                    )
                return rows

            table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")
            table.add_slot(
                "body-cell-actions",
                """
                <q-td :props="props">
                    <q-btn flat round color="primary" icon="edit" @click="$parent.$emit('edit', props.row)" />
                    <q-btn flat round color="negative" icon="delete" @click="$parent.$emit('delete', props.row.id)" />
                </q-td>
            """,
            )
            table.on("edit", lambda msg: start_contact_edit(msg.args))
            table.on("delete", lambda msg: delete_contact(msg.args))

            async def update_rows():
                table.rows = await load_data()

            table.update_rows = update_rows
            await update_rows()


@ui.page("/organizations")
async def organizations_page() -> None:
    """The organization management page."""
    authenticated = app.storage.user.get("authenticated", False)
    if not authenticated:
        ui.navigate.to("/login")
        return

    async def get_orgs():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(f"{ORG_SVC_URL}/", timeout=10.0)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                ui.notify(f"Failed to fetch organizations: {e}", type="negative")
        return []

    async def add_org():
        if not org_name_input.value:
            ui.notify("Name is required", type="negative")
            return

        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                if editing_id.value:
                    response = await client.put(
                        f"{ORG_SVC_URL}/{editing_id.value}",
                        json={"name": org_name_input.value},
                        timeout=10.0,
                    )
                else:
                    response = await client.post(
                        f"{ORG_SVC_URL}/",
                        json={"name": org_name_input.value},
                        timeout=10.0,
                    )

                if response.status_code == 200:
                    ui.notify("Success", type="positive")
                    cancel_edit()
                    await refresh_orgs()
                else:
                    ui.notify(f"Error: {response.text}", type="negative")
            except Exception as e:
                ui.notify(f"Operation failed: {e}", type="negative")

    async def delete_org(org_id: int):
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.delete(f"{ORG_SVC_URL}/{org_id}", timeout=10.0)
                if response.status_code == 200:
                    ui.notify("Deleted", type="positive")
                    await refresh_orgs()
                else:
                    ui.notify(f"Error: {response.text}", type="negative")
            except Exception as e:
                ui.notify(f"Failed to delete: {e}", type="negative")

    def start_edit(org: dict):
        editing_id.set_value(org["id"])
        org_name_input.set_value(org["name"])
        add_btn.set_text("Save Changes")
        cancel_btn.set_visibility(True)

    def cancel_edit():
        editing_id.set_value(None)
        org_name_input.set_value("")
        add_btn.set_text("Add")
        cancel_btn.set_visibility(False)

    async def refresh_orgs():
        table.rows = await get_orgs()

    editing_id = State(None)

    with ui.header().classes("bg-primary text-white items-center justify-between"):
        ui.label("Organization Management").classes("text-h6 ml-4")
        ui.button("Back Home", on_click=lambda: ui.navigate.to("/")).props(
            "flat color=white"
        )

    with ui.column().classes("w-full p-8 gap-8"):
        with ui.card().classes("w-full p-6"):
            ui.label("Add/Edit Organization").classes("text-h5 mb-4")
            with ui.row().classes("w-full items-end gap-4"):
                org_name_input = ui.input("Organization Name").classes("flex-1")
                add_btn = ui.button("Add", on_click=add_org).classes("mb-1")
                cancel_btn = ui.button(
                    "Cancel", on_click=cancel_edit, color="grey"
                ).classes("mb-1")
                cancel_btn.set_visibility(False)

        with ui.card().classes("w-full p-6"):
            ui.label("Organization List").classes("text-h5 mb-4")

            columns = [
                {"name": "id", "label": "ID", "field": "id", "align": "left"},
                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "actions", "label": "Actions", "field": "id"},
            ]

            table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")
            table.add_slot(
                "body-cell-actions",
                """
                <q-td :props="props">
                    <q-btn flat round color="primary" icon="edit" @click="$parent.$emit('edit', props.row)" />
                    <q-btn flat round color="negative" icon="delete" @click="$parent.$emit('delete', props.row.id)" />
                </q-td>
            """,
            )
            table.on("edit", lambda msg: start_edit(msg.args))
            table.on("delete", lambda msg: delete_org(msg.args))

            await refresh_orgs()


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
    )
