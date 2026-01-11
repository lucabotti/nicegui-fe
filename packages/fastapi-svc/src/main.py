import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from keycloak import KeycloakOpenID

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

# Configure OpenTelemetry
OTEL_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
)

resource = Resource.create({"service.name": "fastapi-svc"})

# Setup tracing
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
)
trace.get_tracer_provider().add_span_processor(span_processor)

# Setup metrics
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
)
metrics.set_meter_provider(
    MeterProvider(resource=resource, metric_readers=[metric_reader])
)
meter = metrics.get_meter(__name__)

# Custom metrics
hello_endpoint_counter = meter.create_counter(
    name="hello_endpoint_calls",
    description="Number of calls to /hello endpoint",
    unit="1",
)

app = FastAPI(title="Backend Service")

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keycloak configuration
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080").rstrip("/")
KEYCLOAK_EXTERNAL_URL = os.environ.get("KEYCLOAK_EXTERNAL_URL", KEYCLOAK_URL).rstrip(
    "/"
)
REALM = "test-realm"
CLIENT_ID = "nicegui-app"
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET")

keycloak_openid = KeycloakOpenID(
    server_url=f"{KEYCLOAK_URL}/",
    client_id=CLIENT_ID,
    realm_name=REALM,
    client_secret_key=CLIENT_SECRET,
    verify=True,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    # Decode and validate token
    expected_issuer = f"{KEYCLOAK_EXTERNAL_URL}/realms/{REALM}"
    try:
        # First try with the most likely issuer for this environment
        decoded_token = keycloak_openid.decode_token(
            token, validate=True, issuer=expected_issuer
        )
        return decoded_token
    except Exception:
        try:
            # Try internal issuer as secondary option
            decoded_token = keycloak_openid.decode_token(token, validate=True)
            return decoded_token
        except Exception:
            # Last resort: disable issuer verification entirely
            try:
                decoded_token = keycloak_openid.decode_token(
                    token,
                    validate=True,
                    options={"verify_iss": False},
                )
                return decoded_token
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid authentication credentials: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )


@app.get("/hello")
async def hello(user: Annotated[dict, Depends(get_current_user)]):
    # Increment custom metric
    hello_endpoint_counter.add(1, {"user": user.get("preferred_username", "unknown")})

    # Check for role2 in realm_access
    roles = user.get("realm_access", {}).get("roles", [])
    if "role2" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have required role: role2",
        )

    return {
        "message": f"Hello {user.get('preferred_username', 'User')}!",
        "decoded_token": user,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8020)
