"""FastAPI app factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agent.chat_session import ChatSessionStore
from backend.api import chat, health, metadata, schema_evolution, search
from backend.config import get_settings
from backend.metadata.graph import close_driver, get_driver
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_driver()
    settings = get_settings()
    embedder = Embedder(
        model_name=settings.search_embed_model,
        chroma_dir=settings.search_chroma_dir,
    )
    searcher = HybridSearcher(
        embedder=embedder,
        rerank_threshold=settings.search_rerank_threshold,
        rrf_k=settings.search_rrf_k,
    )
    try:
        docs = build_docs_from_neo4j(seed_only=settings.search_bootstrap_from_seed)
        searcher.build_index(docs)
        logger.info("Search index built: %d docs, version=%d",
                    len(docs), searcher.get_index_version())
    except Exception as e:
        logger.warning("Search index build failed at startup: %s", e)

    app.state.searcher = searcher
    app.state.chat_store = ChatSessionStore()
    yield
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wireless RNO Data Semantic Service",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(metadata.router, tags=["metadata"])
    app.include_router(search.router, tags=["search"])
    app.include_router(schema_evolution.router, tags=["schema"])
    app.include_router(chat.router, tags=["chat"])
    return app


app = create_app()
