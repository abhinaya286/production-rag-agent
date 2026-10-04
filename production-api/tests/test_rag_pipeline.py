from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from production_api.config import Settings
from production_api.rag import ProductionRAG


class FakeVectorStore:
    def __init__(self, results=None):
        self.results = results or []
        self.added_documents = []
        self.last_query = None
        self.last_k = None

    def add_documents(self, documents):
        self.added_documents.extend(documents)

    def similarity_search_with_score(self, query, k):
        self.last_query = query
        self.last_k = k
        return self.results[:k]


class FakeLLM:
    def __init__(self, content="Grounded answer [S1]", error=None):
        self.content = content
        self.error = error
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


def make_rag(vector_store, primary=None, fallback=None, **settings_kwargs):
    settings = Settings(
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://test:test@localhost/test",
        **settings_kwargs,
    )
    return ProductionRAG(
        settings,
        vector_store=vector_store,
        embeddings=object(),
        primary_llm=primary or FakeLLM(),
        fallback_llm=fallback or FakeLLM(),
    )


def test_ingestion_splits_text_and_preserves_source_metadata(tmp_path: Path):
    document = tmp_path / "guide.md"
    document.write_text("A short sentence. " * 50, encoding="utf-8")
    store = FakeVectorStore()
    rag = make_rag(store, chunk_size=80, chunk_overlap=15)

    chunk_count = rag.ingest_path(document)

    assert chunk_count > 1
    assert len(store.added_documents) == chunk_count
    assert all(chunk.metadata["source"] == "guide.md" for chunk in store.added_documents)
    assert all("start_index" in chunk.metadata for chunk in store.added_documents)


def test_ingestion_rejects_unsupported_file_type(tmp_path: Path):
    document = tmp_path / "data.csv"
    document.write_text("x,y\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported document type"):
        make_rag(FakeVectorStore()).ingest_path(document)


def test_answer_uses_retrieved_context_and_returns_citations():
    document = Document(
        page_content="The deployment uses PostgreSQL.",
        metadata={"source": "architecture.md", "page": 2},
    )
    store = FakeVectorStore([(document, 0.12)])
    llm = FakeLLM("It uses PostgreSQL [S1].")
    rag = make_rag(store, primary=llm)

    result = rag.answer("What database is used?")

    assert result["response"] == "It uses PostgreSQL [S1]."
    assert result["model_used"] == "primary"
    assert result["sources"] == [
        {"source": "architecture.md", "page": 2, "score": 0.12}
    ]
    assert "The deployment uses PostgreSQL." in llm.messages[1].content
    assert "only the supplied reference context" in llm.messages[0].content


def test_answer_falls_back_when_primary_model_fails():
    store = FakeVectorStore(
        [(Document(page_content="The answer is 42.", metadata={"source": "facts.txt"}), 0.2)]
    )
    primary = FakeLLM(error=RuntimeError("primary unavailable"))
    fallback = FakeLLM("The answer is 42 [S1].")
    rag = make_rag(store, primary=primary, fallback=fallback)

    result = rag.answer("What is the answer?")

    assert result["model_used"] == "fallback"
    assert result["response"] == "The answer is 42 [S1]."
    assert fallback.messages is not None


def test_answer_does_not_call_model_without_retrieved_documents():
    primary = FakeLLM()
    rag = make_rag(FakeVectorStore(), primary=primary)

    result = rag.answer("Question without supporting docs")

    assert result["model_used"] == "no_context"
    assert result["sources"] == []
    assert primary.messages is None
