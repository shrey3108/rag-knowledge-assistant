import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from app.config import get_settings
from app.services.rag_service import RAGService
from app.api.routes import get_rag_service


@pytest.fixture
def client(rag_service: RAGService):
    # Override FastAPI dependency to use test fixture rag_service
    app.dependency_overrides[get_rag_service] = lambda: rag_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "gpt-oss:120b-cloud" in data["model"]


def test_upload_and_query_flow(client: TestClient, sample_docs_dir: Path):
    # 1. Upload sample text file
    txt_path = sample_docs_dir / "cloud_infrastructure_guide.txt"
    with open(txt_path, "rb") as f:
        files = [("files", ("cloud_infrastructure_guide.txt", f, "text/plain"))]
        upload_resp = client.post("/api/v1/documents/upload", files=files)

    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["successful_count"] == 1
    assert upload_data["results"][0]["filename"] == "cloud_infrastructure_guide.txt"

    # 2. List documents
    docs_resp = client.get("/api/v1/documents")
    assert docs_resp.status_code == 200
    docs_data = docs_resp.json()
    assert docs_data["total_documents"] >= 1

    # 3. Query
    query_resp = client.post(
        "/api/v1/query",
        json={"question": "What is the Recovery Point Objective (RPO)?"},
    )
    assert query_resp.status_code == 200
    ans_data = query_resp.json()
    assert "question" in ans_data
    assert "answer" in ans_data
    assert "evidence" in ans_data

    # 4. Delete document
    del_resp = client.delete("/api/v1/documents/cloud_infrastructure_guide.txt")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"
