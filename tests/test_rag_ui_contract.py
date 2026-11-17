"""Garante que o backend expõe observabilidade sem perder as fontes."""
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from src.rag.answer_reviews import answer_question


class TestRAGUIContract(unittest.TestCase):
    def test_retorna_distancia_similaridade_e_metadados(self):
        documento = {
            "document_id": "review__order",
            "text": "Entrega atrasada.",
            "metadata": {
                "review_score": 1,
                "order_status": "delivered",
                "delivery_delay_days": 3,
            },
            "cosine_distance": 0.22,
            "cosine_similarity": 0.78,
        }
        openai_module = ModuleType("openai")
        llm = MagicMock()
        llm.return_value.responses.create.return_value = SimpleNamespace(
            output_text="O cliente relata atraso [1].",
            usage=SimpleNamespace(input_tokens=10, output_tokens=8),
        )
        openai_module.OpenAI = llm
        dotenv_module = ModuleType("dotenv")
        dotenv_module.load_dotenv = lambda *args, **kwargs: None

        with (
            patch.dict(sys.modules, {"openai": openai_module, "dotenv": dotenv_module}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-placeholder"}),
            patch("src.rag.answer_reviews.search_reviews", return_value=[documento]),
        ):
            result = answer_question("O que houve com a entrega?")

        source = result["sources"][0]
        self.assertEqual(source["cosine_distance"], 0.22)
        self.assertEqual(source["cosine_similarity"], 0.78)
        self.assertEqual(source["metadata"]["delivery_delay_days"], 3)
        self.assertEqual(source["reference"], "[1]")
        self.assertEqual(result["usage"], {"input_tokens": 10, "output_tokens": 8})


if __name__ == "__main__":
    unittest.main()
