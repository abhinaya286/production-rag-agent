import argparse
from pathlib import Path

import uvicorn

from production_api.config import get_settings
from production_api.rag import ProductionRAG


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        "production_api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
    )


def ingest() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest PDF, Markdown, and text files into the configured RAG collection."
    )
    parser.add_argument("path", type=Path, help="A supported file or a directory of files")
    args = parser.parse_args()

    count = ProductionRAG(get_settings()).ingest_path(args.path)
    print(f"Ingested {count} chunks from {args.path}")
