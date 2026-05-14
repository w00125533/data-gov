"""FastAPI app factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import health, metadata
from backend.metadata.graph import close_driver, get_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly verify Neo4j connectivity at startup
    get_driver()
    yield
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wireless RNO Data Semantic Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(metadata.router, tags=["metadata"])
    return app


app = create_app()
