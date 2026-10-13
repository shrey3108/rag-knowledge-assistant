import pytest
import shutil
import tempfile
from pathlib import Path
from typing import Generator

from app.config import Settings
from app.core.vector_store import VectorStore
from app.core.embedding import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService


@pytest.fixture(scope="session")
def sample_docs_dir() -> Path:
    return Path(__file__).parent.parent / "sample_documents"


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    tmp = tempfile.mkdtemp(prefix="chroma_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_settings(temp_dir: str) -> Settings:
    return Settings(
        ollama_url="https://ollama.com/",
        ollama_api_key="mock-key-for-tests",
        ollama_model="gpt-oss:120b-cloud",
        chroma_persist_directory=temp_dir,
        collection_name="test_knowledge_base",
        mock_llm=True,  # Fast offline deterministic mock for test execution
        top_k=4,
        similarity_threshold=0.25,
        max_chunk_size=500,
        chunk_overlap=80,
        redis_enabled=False,  # Use fast in-memory cache fallback for automated unit tests
    )


@pytest.fixture
def cache_manager(test_settings: Settings):
    from app.core.cache import CacheManager
    return CacheManager(settings=test_settings)


@pytest.fixture
def vector_store(test_settings: Settings) -> VectorStore:
    return VectorStore(
        persist_dir=test_settings.chroma_persist_directory,
        collection_name=test_settings.collection_name,
    )


@pytest.fixture
def embedding_service(test_settings: Settings) -> EmbeddingService:
    return EmbeddingService.get_instance(model_name=test_settings.embedding_model)


@pytest.fixture
def llm_service(test_settings: Settings) -> LLMService:
    return LLMService(settings=test_settings)


@pytest.fixture
def rag_service(
    test_settings: Settings,
    vector_store: VectorStore,
    embedding_service: EmbeddingService,
    llm_service: LLMService,
    cache_manager,
) -> RAGService:
    return RAGService(
        settings=test_settings,
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_service=llm_service,
        cache=cache_manager,
    )

