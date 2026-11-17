"""Testes offline do RAG: python -m unittest discover -s tests -v.

Busca, dotenv e OpenAI sao simulados: nao ha acesso a rede nem cobranca.
"""

import json
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from src.rag.answer_reviews import answer_question, build_context


DOCUMENTO = {
    "document_id": "review_1__order_1",
    "text": "O produto chegou quebrado.",
    "metadata": {
        "review_id": "review_1",
        "review_score": 1,
        "delivery_delay_days": -4,
        "order_status": "delivered",
        "product_categories_json": '["telefonia"]',
    },
}


class TestRAGGeneration(unittest.TestCase):
    def setUp(self):
        # Modulos artificiais garantem que o teste nem importe a API real.
        openai_mock_module = ModuleType("openai")
        self.openai_class = MagicMock(name="OpenAI")
        openai_mock_module.OpenAI = self.openai_class

        dotenv_mock_module = ModuleType("dotenv")
        dotenv_mock_module.load_dotenv = lambda *args, **kwargs: None

        modules_patch = patch.dict(sys.modules, {
            "openai": openai_mock_module,
            "dotenv": dotenv_mock_module,
        })
        env_patch = patch.dict(os.environ, {"OPENAI_API_KEY": "fake-unit-test-key"})
        modules_patch.start()
        env_patch.start()
        self.addCleanup(modules_patch.stop)
        self.addCleanup(env_patch.stop)

    def test_contexto_preserva_evidencia_e_metadados(self):
        contexto = json.loads(build_context([DOCUMENTO]))
        self.assertEqual(len(contexto), 1)
        self.assertEqual(contexto[0]["referencia"], "[1]")
        self.assertEqual(contexto[0]["document_id"], "review_1__order_1")
        self.assertEqual(contexto[0]["comentario"], "O produto chegou quebrado.")
        self.assertEqual(contexto[0]["atraso_em_dias"], -4)
        self.assertEqual(contexto[0]["nota"], 1)

    def test_rejeita_pergunta_vazia(self):
        with self.assertRaisesRegex(ValueError, "pergunta"):
            answer_question("  ")

    @patch("src.rag.answer_reviews.search_reviews", return_value=[])
    def test_sem_documentos_nao_chama_modelo(self, busca_mock):
        resultado = answer_question("Pergunta sem resultados")
        self.assertEqual(resultado["sources"], [])
        self.assertIsNone(resultado["model"])
        self.assertIn("Não encontrei", resultado["answer"])
        busca_mock.assert_called_once()
        self.openai_class.assert_not_called()

    @patch("src.rag.answer_reviews.search_reviews", return_value=[DOCUMENTO])
    def test_resposta_com_citacao_preserva_rastreabilidade(self, busca_mock):
        resposta_fake = SimpleNamespace(
            output_text="Uma avaliação relata produto quebrado [1].",
            usage=SimpleNamespace(input_tokens=100, output_tokens=15),
        )
        self.openai_class.return_value.responses.create.return_value = resposta_fake

        resultado = answer_question("Há reclamações de produtos quebrados?")
        self.assertEqual(len(resultado["sources"]), 1)
        self.assertEqual(resultado["sources"][0]["reference"], "[1]")
        self.assertEqual(resultado["sources"][0]["document_id"], DOCUMENTO["document_id"])
        self.assertIn("[1]", resultado["answer"])
        self.assertEqual(resultado["usage"], {"input_tokens": 100, "output_tokens": 15})
        self.openai_class.return_value.responses.create.assert_called_once()
        busca_mock.assert_called_once()

    @patch("src.rag.answer_reviews.search_reviews", return_value=[DOCUMENTO])
    def test_rejeita_citacao_inexistente(self, _busca_mock):
        resposta_fake = SimpleNamespace(
            output_text="O produto chegou quebrado [2].",
            usage=None,
        )
        self.openai_class.return_value.responses.create.return_value = resposta_fake

        with self.assertRaisesRegex(RuntimeError, "referência fora"):
            answer_question("O que ocorreu com o produto?")


if __name__ == "__main__":
    unittest.main()
