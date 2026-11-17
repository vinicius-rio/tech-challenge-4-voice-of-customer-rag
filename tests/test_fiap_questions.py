"""Regressões de layout e comportamento das sugestões no celular."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPhoneSuggestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.css = (ROOT / "assets" / "fiap.css").read_text(encoding="utf-8")
        tree = ast.parse(cls.app)
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "QUESTIONS" for t in node.targets)
        )
        cls.questions = ast.literal_eval(assignment.value)

    def test_tres_perguntas_completas(self):
        self.assertEqual(len(self.questions), 3)
        self.assertTrue(all(isinstance(q, str) and q.endswith("?") for q in self.questions))
        self.assertTrue(all(len(q) >= 40 for q in self.questions))

    def test_botoes_usam_pergunta_integral(self):
        self.assertIn('f"{i:02d}  {suggested_question}"', self.app)
        self.assertIn('process_question(suggested_question)', self.app)

    def test_titulo_no_mesmo_bloco_de_boas_vindas(self):
        start = self.app.index('if not st.session_state.turns:')
        end = self.app.index('for i, suggested_question in enumerate(QUESTIONS, 1):', start)
        segment = self.app[start:end]
        self.assertEqual(segment.count('st.markdown('), 1)
        self.assertIn('phone-suggestions-title', segment)
        self.assertIn('chat-welcome', segment)

    def test_espacamento_reservado_para_titulo_e_botoes(self):
        self.assertIn('min-height:42px!important;', self.css)
        self.assertIn('padding-top:7px!important;', self.css)
        self.assertIn('min-height:52px!important;', self.css)
        self.assertNotIn('height:100%!important;', self.css)


if __name__ == '__main__':
    unittest.main()
