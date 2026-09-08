from fastapi import FastAPI

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


app.include_router(
    incidents_router,
)
