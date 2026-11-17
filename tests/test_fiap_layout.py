"""Verificações de regressão v1.6 (não substituem teste visual no navegador)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestFiapLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.css = (ROOT / "assets" / "fiap.css").read_text(encoding="utf-8")

    def test_paineis_laterais_iguais_e_com_scroll(self):
        self.assertIn('st.container(height=825, border=False, key="controls")', self.app)
        self.assertIn('st.container(height=825, border=False, key="inspector")', self.app)
        self.assertRegex(self.css, r"\.st-key-controls\s*,\s*\.st-key-inspector\s*\{")
        self.assertIn("overflow-y:auto!important;", self.css)

    def test_celular_sem_regra_de_altura_fixa_que_colapsou_o_layout(self):
        # A regressão veio de sobrescrever height/max-height do phone_shell.
        # O CSS antigo, que aparecia corretamente, só usa min-height.
        for match in re.finditer(r"\.st-key-phone_shell\s*\{([^{}]*)\}", self.css):
            style = match.group(1)
            self.assertIsNone(re.search(r"(?<![\w-])height\s*:", style))
            self.assertIsNone(re.search(r"max-height\s*:", style))
            self.assertNotIn("display:flex", style.replace(" ", ""))
        self.assertIn('st.container(key="phone_shell")', self.app)

    def test_sugestoes_apenas_dentro_do_celular(self):
        left = self.app.split("with left:", 1)[1].split("with center:", 1)[0]
        center = self.app.split("with center:", 1)[1].split("with right:", 1)[0]
        self.assertNotIn("enumerate(QUESTIONS", left)
        self.assertIn("enumerate(QUESTIONS", center)
        self.assertIn("with st.container(height=535, border=False, key=\"phone_chat\"):", center)
        self.assertIn('st.chat_input(', center)

    def test_nao_hacks_nos_blocos_internos_do_streamlit(self):
        self.assertNotIn('display:flex!important;flex-direction:column', self.css.replace(' ', ''))
        self.assertNotIn('height:100%!important;', self.css.replace(' ', ''))


if __name__ == "__main__":
    unittest.main()
