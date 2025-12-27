import os
from collections.abc import Generator

import pytest
from testcontainers.keycloak import KeycloakContainer


@pytest.fixture(scope="session")
def keycloak_container() -> Generator[KeycloakContainer, None, None]:
    """
    Fixture to start a Keycloak container with the realm-export.json imported.
    """
    # Path to the realm export file relative to the project root
    realm_export_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "realm-export.json")
    )

    with KeycloakContainer("quay.io/keycloak/keycloak:26.0.0") as keycloak:
        # Import the realm
        # Note: with_realm_import_file mounts the file into the container
        # and adds the necessary startup arguments.
        keycloak.with_realm_import_file(realm_export_path)
        keycloak.start()
        yield keycloak
