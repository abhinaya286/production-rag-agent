from production_api.config import get_settings
from production_api.rag import ProductionRAG


class ProductionAgent:
    def __init__(self, rag: ProductionRAG | None = None):
        self.rag = rag or ProductionRAG(get_settings())

    def invoke(self, message: str) -> dict:
        return self.rag.answer(message)
