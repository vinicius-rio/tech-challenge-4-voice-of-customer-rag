"""Busca semântica nas avaliações da Olist indexadas no ChromaDB.

Execute a partir da raiz do repositório, com o ambiente virtual ativado:

    python src/rag/search_reviews.py --query "Reclamações de atraso na entrega"
    python src/rag/search_reviews.py --query "Reclamações de atraso na entrega" --delayed-only
    python src/rag/search_reviews.py --query "Produto veio quebrado" --top-k 3 --json

O embedding da pergunta usa a API da OpenAI (há consumo de tokens).
Os documentos existentes não são indexados novamente por este script.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DB_DIR = ROOT / "storage" / "chroma"
COLLECTION = "olist_reviews_openai_v1"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def search_reviews(
    question: str,
    top_k: int = 5,
    delayed_only: bool = False,
) -> list[dict[str, Any]]:
    """Recupera os documentos mais próximos da pergunta.

    delayed_only=True restringe a busca aos pedidos com
    delivery_delay_days > 0, ou seja, entregues depois da data estimada.

    Retorna distância de cosseno e 1 - distância como medida de similaridade.
    A similaridade NÃO representa probabilidade nem certeza de relevância.
    """
    question = question.strip()
    if not question:
        raise ValueError("A pergunta não pode estar vazia.")
    if not 1 <= top_k <= 100:
        raise ValueError("top_k deve ficar entre 1 e 100.")
    if not DB_DIR.is_dir():
        raise FileNotFoundError(f"Banco ChromaDB não encontrado: {DB_DIR}")

    import chromadb
    from dotenv import load_dotenv
    from openai import OpenAI

    chroma = chromadb.PersistentClient(path=str(DB_DIR))
    try:
        collection = chroma.get_collection(name=COLLECTION)
    except Exception as exc:
        raise RuntimeError(
            f"Coleção '{COLLECTION}' não encontrada no ChromaDB em {DB_DIR}"
        ) from exc

    count = collection.count()
    if count == 0:
        raise RuntimeError(f"A coleção '{COLLECTION}' ainda está vazia.")

    # Mesmo modelo e espaço vetorial do indexador (index_documents.py).
    sample = collection.get(limit=1, include=["metadatas"])
    sample_meta = (sample["metadatas"] or [{}])[0] or {}
    model_in_db = sample_meta.get("embedding_model")
    if model_in_db != EMBEDDING_MODEL:
        raise RuntimeError(
            f"Modelo incompatível: coleção={model_in_db!r}, "
            f"consulta={EMBEDDING_MODEL!r}."
        )
    space = (collection.metadata or {}).get("hnsw:space")
    if space not in (None, "cosine"):
        raise RuntimeError(f"A coleção usa distância '{space}', não 'cosine'.")

    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY ausente. Confira {ROOT / '.env'}")

    openai_client = OpenAI(max_retries=3, timeout=60.0)
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=question,
    )
    vector = response.data[0].embedding
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Dimensão inesperada: {len(vector)} (esperada: {EMBEDDING_DIMENSIONS})."
        )

    where = {"delivery_delay_days": {"$gt": 0}} if delayed_only else None
    query_result = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, count),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    rows: list[dict[str, Any]] = []
    ids = query_result["ids"][0]
    texts = query_result["documents"][0]
    metadatas = query_result["metadatas"][0]
    distances = query_result["distances"][0]
    for document_id, text, metadata, distance in zip(
        ids, texts, metadatas, distances, strict=True
    ):
        distance = float(distance)
        rows.append(
            {
                "document_id": document_id,
                "text": text,
                "metadata": metadata or {},
                "cosine_distance": distance,
                "cosine_similarity": 1 - distance,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Pergunta para a busca semântica")
    parser.add_argument("--top-k", type=int, default=5, help="Máximo de resultados (1 a 100)")
    parser.add_argument(
        "--delayed-only",
        action="store_true",
        help="Incluir apenas pedidos com delivery_delay_days > 0",
    )
    parser.add_argument("--json", action="store_true", help="Exibir resultado em formato JSON")
    args = parser.parse_args()

    try:
        results = search_reviews(args.query, args.top_k, args.delayed_only)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        parser.exit(status=1, message=f"ERRO: {exc}\n")

    if args.json:
        print(
            json.dumps(
                {
                    "question": args.query,
                    "delayed_only": args.delayed_only,
                    "result_count": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print("\nBUSCA SEMÂNTICA — OLIST")
    print(f"Pergunta: {args.query}")
    print(f"Filtro de atraso: {'ativado (> 0 dias)' if args.delayed_only else 'desativado'}")
    print(f"Documentos recuperados: {len(results)}")

    for i, row in enumerate(results, 1):
        metadata = row["metadata"]
        print("\n" + "=" * 65)
        print(f"RESULTADO {i}")
        print(f"Similaridade de cosseno: {row['cosine_similarity']:.4f}")
        print(f"Distância de cosseno: {row['cosine_distance']:.4f}")
        print(f"Document ID: {row['document_id']}")
        print(f"Review ID: {metadata.get('review_id')}")
        print(f"Nota: {metadata.get('review_score')}")
        print(f"Atraso em dias: {metadata.get('delivery_delay_days')}")
        print(f"Status: {metadata.get('order_status')}")
        print(f"Comentário: {row['text']}")


if __name__ == "__main__":
    main()
