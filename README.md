# NiceGUI & FastAPI Microservices Demo

This project is a comprehensive demonstration of a modern microservices architecture using **NiceGUI**, **FastAPI**, **HTMX**, and **Keycloak**. It showcases a monorepo setup with multiple frontends and backends interacting through a centralized identity provider and API gateway.

## Architecture Overview

The ecosystem is composed of several specialized services orchestrated with Docker:

### Frontends
*   **NiceGUI FE (`packages/nicegui-fe`)**: A feature-rich, interactive web application built with Python's NiceGUI. It handles OIDC authentication with Keycloak and provides a dashboard for user info and service interaction.
*   **HTMX FE (`packages/htmx-fe`)**: A lightweight alternative frontend using HTMX and FastAPI, demonstrating a different approach to building dynamic UIs.

### Backends
*   **Contact Service (`packages/contact-svc`)**: Manages contact information using a PostgreSQL database. It includes Alembic migrations and interacts with the Organization service.
*   **Organization Service (`packages/org-svc`)**: A dedicated service for managing organizational entities.
*   **FastAPI Service (`packages/fastapi-svc`)**: A general-purpose backend service used for demonstrating authenticated service-to-service communication.

### Infrastructure & Security
*   **Keycloak**: The central Identity and Access Management (IAM) provider, handling authentication (OIDC) and authorization (RBAC).
*   **Traefik**: Acts as the API Gateway and reverse proxy, routing requests based on hostnames and paths.
*   **OAuth2 Proxy**: Handles authentication for services that don't natively support OIDC.
*   **PostgreSQL**: Persistent storage for Keycloak and the Contact service.
*   **Redis**: Shared session storage for the frontends to ensure statelessness and scalability.

## Key Features

- **Single Sign-On (SSO)**: Seamless authentication across multiple frontends.
- **Role-Based Access Control (RBAC)**: UI elements and API endpoints secured based on Keycloak roles (e.g., `admin`, `role2`).
- **Service Mesh Simulation**: Internal communication between services through the Traefik gateway.
- **Monorepo Management**: Optimized development workflow using `uv` for package management and `just` for task automation.
- **Automated Infrastructure**: Full environment bootstrap with Docker Compose, including database initialization and Keycloak realm import.

## Getting Started

### Prerequisites
- [Docker](https://www.docker.com/) and Docker Compose.
- [uv](https://github.com/astral-sh/uv) (for local development).
- [just](https://github.com/casey/just) (optional, for task running).

### Running the Application

1.  **Start the environment**:
    ```bash
    docker compose up -d
    ```

2.  **Access the services**:
    - **NiceGUI Frontend**: [http://app.localhost](http://app.localhost)
    - **HTMX Frontend**: [http://htmx.localhost](http://htmx.localhost)
    - **Keycloak Admin**: [http://keycloak.localhost:8080](http://keycloak.localhost:8080) (Admin: `admin`/`admin`)
    - **Traefik Dashboard**: [http://traefik.localhost](http://traefik.localhost)
    - **API Documentation**: [http://api.localhost/docs](http://api.localhost/docs)

### Development Commands

Use `just` to run common tasks:
- `just lint`: Lint and format the codebase.
- `just test`: Run tests for all packages.
- `just type`: Run type checking.

## Configuration

The environment variables and service configurations are primarily managed in the `docker-compose.yml` file. Keycloak realm configuration is imported from `realm-export.json` on startup.