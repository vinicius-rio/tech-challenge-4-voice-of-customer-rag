"""Amplia o retorno das fontes do RAG sem alterar seu prompt ou fluxo de geração.

Uso (na raiz do repositório): python scripts/extend_rag_sources.py
"""
from pathlib import Path

path = Path('src/rag/answer_reviews.py')
if not path.is_file():
    raise SystemExit('ERRO: execute a partir da raiz do repositório.')

contents = path.read_text(encoding='utf-8')
needle = '                "review_score": (item.get("metadata") or {}).get("review_score"),'
additions = (
    '\n                "cosine_distance": item.get("cosine_distance"),'
    '\n                "cosine_similarity": item.get("cosine_similarity"),'
    '\n                "metadata": item.get("metadata") or {},'
)
if '"cosine_similarity": item.get("cosine_similarity")' in contents:
    print('Extensão já aplicada. Nenhuma alteração necessária.')
elif contents.count(needle) != 1:
    raise SystemExit('ERRO: contrato das fontes diferente do esperado. Arquivo não alterado.')
else:
    contents = contents.replace(needle, needle + additions, 1)
    path.write_text(contents, encoding='utf-8')
    print('Campos de distância, similaridade e metadados incluídos no retorno do RAG.')
