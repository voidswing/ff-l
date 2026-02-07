from fastapi.testclient import TestClient

from src.feature.judge import service
from src.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_judge_endpoint_works_without_api_key() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    client = TestClient(app)
    try:
        response = client.post("/api/judge", json={"story": "친구 카드로 결제했어요."})
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]
    assert isinstance(payload["possible_crimes"], list)
    assert "법률 자문" in payload["disclaimer"]
