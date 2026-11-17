"""Testes de regressão do drill-down de fontes RAG (sem dependências externas)."""

import unittest

from ui_inspector import (
    category_names,
    delivery_text,
    document_short_id,
    metric_text,
    render_source_card,
)


class TestRAGInspector(unittest.TestCase):
    def test_categoria_json_nao_mostra_entidade_html(self):
        source = {
            "text": "oi",
            "document_id": "abc__def",
            "review_score": 5,
            "cosine_distance": 0.2439,
            "cosine_similarity": 0.7561,
            "metadata": {
                "order_status": "delivered",
                "product_categories_json": '["col_stuff"]',
                "delivery_delay_days": -15,
            },
        }
        html = render_source_card(source)
        self.assertIn('>col_stuff</span>', html)
        self.assertNotIn('&quot;col_stuff&quot;', html)
        self.assertIn('15 dias antes da previsão', html)
        self.assertIn('Entregue', html)
        self.assertIn('0.7561', html)
        self.assertIn('0.2439', html)

    def test_campo_de_categorias_aceita_lista_ou_json(self):
        self.assertEqual(category_names('["livros", "casa"]'), ['livros', 'casa'])
        self.assertEqual(category_names(['livros', 'casa']), ['livros', 'casa'])
        self.assertEqual(category_names(None), [])
        self.assertEqual(category_names('livros'), ['livros'])

    def test_evidencias_sem_html_injetavel(self):
        source = {
            "document_id": 'id" onmouseover="alert(1)',
            "text": '<script>alert(1)</script>',
            "metadata": {"product_categories_json": '["<img src=x onerror=alert(1)>"]'},
        }
        html = render_source_card(source)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img src=x', html)
        self.assertIn('&quot; onmouseover=&quot;', html)

    def test_atraso_versus_antecipacao(self):
        self.assertEqual(delivery_text(3), '3 dias após a previsão')
        self.assertEqual(delivery_text(-15), '15 dias antes da previsão')
        self.assertEqual(delivery_text(0), 'Na data prevista')
        self.assertEqual(delivery_text(None), 'Sem informação')

    def test_metricas_sem_fabricacao_e_id_truncado(self):
        self.assertEqual(metric_text(0.7561), '0.7561')
        self.assertEqual(metric_text(None), 'N/D')
        self.assertEqual(metric_text(float('nan')), 'N/D')
        self.assertIn('…', document_short_id('z' * 100))


if __name__ == '__main__':
    unittest.main()
