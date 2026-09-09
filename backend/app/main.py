from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.app.api.incidents import router as incidents_router


app = FastAPI(
    title="AegisAI",
    description=(
        "Local LLM-powered autonomous DevOps "
        "incident management platform."
    ),
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Basic API health check.
    """

    return {
        "status": "healthy",
        "service": "aegisai",
    }


@app.get("/metrics")
def metrics() -> Response:
    """
    Prometheus metrics endpoint.
    """

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


app.include_router(
    incidents_router,
)
