from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest

from production_api import main
from production_api.config import Settings


class FakeAgent:
    def __init__(self):
        self.last_message = None

    def invoke(self, message: str) -> dict:
        self.last_message = message
        return {
            "response": "The indexed guide describes the deployment [S1].",
            "model_used": "primary",
            "sources": [{"source": "guide.md", "page": None, "score": 0.2}],
        }


def test_chat_requires_token_and_returns_cited_rag_response(monkeypatch):
    settings = Settings(
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://test:test@localhost/test",
        api_access_token=SecretStr("test-token"),
        app_env="production",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "ProductionAgent", FakeAgent)

    with TestClient(main.app) as client:
        payload = {
            "message": "How is it deployed?",
            "thread_id": "test-thread",
        }
        unauthorized = client.post("/chat", json=payload)
        response = client.post(
            "/chat",
            headers={"Authorization": "Bearer test-token"},
            json=payload,
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "The indexed guide describes the deployment [S1]."
    assert body["sources"][0]["source"] == "guide.md"
    assert body["model_used"] == "primary"


def test_settings_builds_encoded_supabase_connection_url():
    settings = Settings(
        gemini_api_key="test-key",
        supabase_host="db.example.invalid",
        supabase_password="not-a-real@password",
    )

    assert settings.vector_database_url == (
        "postgresql+psycopg://postgres:not-a-real%40password@"
        "db.example.invalid:5432/postgres"
    )


def test_empty_development_token_does_not_require_authentication(monkeypatch):
    settings = Settings(
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://test:test@localhost/test",
        api_access_token=SecretStr(""),
        app_env="development",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    assert main.require_api_access() is None


def test_production_rejects_empty_access_token():
    settings = Settings(
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://test:test@localhost/test",
        api_access_token=SecretStr(""),
        app_env="production",
    )

    with pytest.raises(ValueError, match="API_ACCESS_TOKEN"):
        settings.validate_rag_configuration()