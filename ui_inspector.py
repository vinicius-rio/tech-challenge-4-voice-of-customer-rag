"""Renderização segura das evidências no painel RAG Inspector.

As métricas pertencem à recuperação vetorial, não à qualidade factual da resposta.
Funções puras: não dependem do Streamlit nem de chamadas externas.
"""

from __future__ import annotations

import html
import json
import math
from typing import Any


STATUS_PT = {
    "delivered": "Entregue",
    "processing": "Em processamento",
    "shipped": "Enviado",
    "canceled": "Cancelado",
    "approved": "Aprovado",
    "invoiced": "Faturado",
    "unavailable": "Indisponível",
    "created": "Criado",
}


def safe(value: Any) -> str:
    """Escapa qualquer valor externo antes da inserção no HTML."""
    return html.escape(str(value if value is not None else "—"), quote=True)


def metric_text(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "N/D"
    return f"{value:.4f}"


def category_names(value: Any) -> list[str]:
    """Converte o campo JSON do ChromaDB em nomes legíveis, sem HTML escapado."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = [value]
    if isinstance(value, dict):
        value = list(value.keys())
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    return [str(item).strip() for item in value if item is not None and str(item).strip()]


def delivery_text(days: Any) -> str:
    if days is None or days == "":
        return "Sem informação"
    try:
        value = float(days)
    except (TypeError, ValueError, OverflowError):
        return "Sem informação"
    if not math.isfinite(value):
        return "Sem informação"
    unit = "dia" if abs(value) == 1 else "dias"
    number = f"{abs(value):g}"
    if value > 0:
        return f"{number} {unit} após a previsão"
    if value < 0:
        return f"{number} {unit} antes da previsão"
    return "Na data prevista"


def score_text(score: Any) -> str:
    try:
        n = int(score)
    except (TypeError, ValueError, OverflowError):
        return "Não informada"
    return f"{n}/5" if 1 <= n <= 5 else "Não informada"


def document_short_id(document_id: Any) -> str:
    text = str(document_id or "")
    if len(text) <= 34:
        return text or "Não informado"
    return f"{text[:16]}…{text[-12:]}"


def render_source_card(source: dict[str, Any]) -> str:
    """Produz o corpo visual de uma fonte (com os dados escapados)."""
    md = source.get("metadata") or {}
    sim = metric_text(source.get("cosine_similarity"))
    dist = metric_text(source.get("cosine_distance"))
    score = source.get("review_score")
    if score is None:
        score = md.get("review_score")
    score_label = score_text(score)
    try:
        score_n = int(score)
    except (TypeError, ValueError, OverflowError):
        score_n = 0
    stars = ("★" * score_n + "☆" * (5 - score_n)) if 1 <= score_n <= 5 else "—"
    status_raw = str(md.get("order_status") or "")
    status_pt = STATUS_PT.get(status_raw.lower(), status_raw or "Sem informação")
    categories = category_names(md.get("product_categories_json"))
    cats_html = ("".join(f'<span class="source-chip">{safe(cat)}</span>' for cat in categories)
                 if categories else '<span class="source-empty">Não informada</span>')
    document_id = str(source.get("document_id") or "")
    comment = str(source.get("text") or "").strip() or "Sem comentário textual."
    return f"""
    <section class="source-detail">
      <div class="source-overline">COMENTÁRIO ORIGINAL</div>
      <blockquote class="source-quote">{safe(comment)}</blockquote>
      <div class="source-kpi-grid">
        <div class="source-kpi">
          <div class="source-kpi-label">SIMILARIDADE COSSENO</div>
          <div class="source-kpi-value source-kpi-highlight">{sim}</div>
        </div>
        <div class="source-kpi">
          <div class="source-kpi-label">DISTÂNCIA COSSENO</div>
          <div class="source-kpi-value">{dist}</div>
        </div>
      </div>
      <div class="source-info-grid">
        <div class="source-info">
          <span class="source-info-label">NOTA DA AVALIAÇÃO</span>
          <span class="source-stars" aria-label="{safe(score_label)}">{stars}</span>
          <strong>{safe(score_label)}</strong>
        </div>
        <div class="source-info">
          <span class="source-info-label">ENTREGA X PREVISÃO</span>
          <strong>{safe(delivery_text(md.get('delivery_delay_days')))}</strong>
        </div>
        <div class="source-info">
          <span class="source-info-label">STATUS DO PEDIDO</span>
          <strong title="{safe(status_raw)}">{safe(status_pt)}</strong>
        </div>
        <div class="source-info source-info-categories">
          <span class="source-info-label">CATEGORIA(S)</span>
          <div class="source-chips">{cats_html}</div>
        </div>
      </div>
      <div class="source-document">
        <span class="source-info-label">IDENTIFICADOR DO DOCUMENTO</span>
        <code title="{safe(document_id)}">{safe(document_short_id(document_id))}</code>
      </div>
      <div class="source-footnote">Os metadados podem representar o estado final do pedido e divergir do relato do cliente.</div>
    </section>"""
