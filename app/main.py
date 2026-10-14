import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.api.routes import router as api_router
from app.api.compat_routes import router as compat_router
from app.core.vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure persistence dir exists and ChromaDB is ready
    logger.info("Initializing Knowledge Assistant application...")
    logger.info(f"Target LLM Model: {settings.ollama_model} via endpoint {settings.chat_completions_url}")
    logger.info(f"Vector Database directory: {settings.chroma_persist_directory}")
    
    # Pre-warm vector store
    VectorStore(
        persist_dir=settings.chroma_persist_directory,
        collection_name=settings.collection_name,
    )
    yield
    logger.info("Shutting down Knowledge Assistant application...")


app = FastAPI(
    title="AI-Powered Knowledge Assistant",
    description="A factual, grounded knowledge assistant with source evidence, Ollama Cloud 120B integration, and ChromaDB.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)
app.include_router(compat_router)

# Mount Static Files & UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(static_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
