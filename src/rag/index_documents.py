"""Indexa documentos JSONL da Olist no ChromaDB usando embeddings OpenAI.

A execução padrão indexa APENAS 10 documentos para testes.

Na raiz do repositório:
    python src/rag/index_documents.py --dry-run
    python src/rag/index_documents.py                  # apenas 10 documentos
    python src/rag/index_documents.py --all            # base completa; só depois de validar

O script não usa o mecanismo de embeddings automático do Chroma: sempre
fornece os vetores gerados explicitamente com text-embedding-3-small.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "olist_reviews_documents.jsonl"
DB_DIR = ROOT / "storage" / "chroma"
REPORT = ROOT / "data" / "processed" / "vector_index_report.json"
COLLECTION = "olist_reviews_openai_v1"
MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
PRICE_PER_MILLION_TOKENS_USD = 0.02  # estimativa; verificar tabela vigente


def read_documents(path: Path, max_docs: int | None):
    if not path.is_file():
        raise FileNotFoundError(f"JSONL não encontrado: {path}")
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, 1):
            if max_docs is not None and line_number > max_docs:
                break
            doc = json.loads(raw_line)
            meta = doc["metadata"]
            identifier = doc["document_id"]
            text = doc["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Linha {line_number}: documento sem texto")
            if identifier != f"{meta['review_id']}__{meta['order_id']}":
                raise ValueError(f"Linha {line_number}: identificador inconsistente")
            yield doc


def batches(iterator, size: int):
    batch = []
    for obj in iterator:
        batch.append(obj)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chroma_metadata(doc: dict) -> dict:
    """Chroma recebe valores escalares; arrays ficam como JSON serializado."""
    original = doc["metadata"]
    categories = original.get("product_categories") or []
    if not isinstance(categories, list):
        raise ValueError(f"Categorias inválidas no documento {doc['document_id']}")

    metadata = {
        "review_id": original["review_id"],
        "order_id": original["order_id"],
        "review_score": int(original["review_score"]),
        "review_creation_date": original["review_creation_date"],
        "text_type": original["text_type"],
        "embedding_model": MODEL,
        "text_sha256": sha(doc["text"]),
        "product_categories_json": json.dumps(categories, ensure_ascii=False),
        "category_count": len(categories),
    }
    if len(categories) == 1:
        metadata["single_product_category"] = categories[0]

    for key in ("order_status", "order_purchase_date", "delivery_delay_days", "quantity_items"):
        value = original.get(key)
        if value is not None:  # Chroma pode rejeitar valores nulos
            metadata[key] = value
    return metadata


def save_report(report: dict):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, REPORT)


def index(max_docs: int | None, batch_size: int, dry_run: bool):
    if batch_size < 1 or batch_size > 256:
        raise ValueError("--batch-size deve ficar entre 1 e 256")

    docs = read_documents(INPUT, max_docs)
    if dry_run:
        print("MODO DE SIMULAÇÃO: nenhuma requisição, cobrança ou alteração no ChromaDB")
        count = 0
        ids = set()
        for batch in batches(docs, batch_size):
            for doc in batch:
                did = doc["document_id"]
                if did in ids:
                    raise ValueError(f"document_id repetido: {did}")
                ids.add(did)
                chroma_metadata(doc)
                count += 1
        print(f"Documentos locais validados: {count:,}")
        return

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY ausente. Confira {ROOT / '.env'}")

    from openai import OpenAI
    import chromadb

    openai_client = OpenAI(max_retries=3, timeout=90.0)
    chroma_client = chromadb.PersistentClient(path=str(DB_DIR))
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    if collection.metadata and collection.metadata.get("hnsw:space") not in (None, "cosine"):
        raise RuntimeError("A coleção existente não utiliza a distância de cosseno")

    if collection.count():
        sample = collection.get(limit=1, include=["embeddings", "metadatas"])
        existing_meta = sample["metadatas"][0] or {}
        if existing_meta.get("embedding_model") not in (None, MODEL):
            raise RuntimeError("Coleção contém embeddings de outro modelo")
        if len(sample["embeddings"][0]) != VECTOR_SIZE:
            raise RuntimeError("Coleção tem dimensão vetorial diferente de 1536")

    report = {
        "model": MODEL, "collection": COLLECTION,
        "source": str(INPUT.relative_to(ROOT)),
        "requested_limit": max_docs if max_docs is not None else "all",
        "read_in_this_run": 0,
        "indexed_in_this_run": 0,
        "skipped_existing": 0,
        "tokens_in_this_run": 0,
        "estimated_cost_usd_in_this_run": 0.0,
        "collection_count": collection.count(),
    }
    seen = set()

    try:
        for number, batch in enumerate(batches(docs, batch_size), 1):
            ids = [d["document_id"] for d in batch]
            for did in ids:
                if did in seen:
                    raise ValueError(f"ID repetido no arquivo de entrada: {did}")
                seen.add(did)
            report["read_in_this_run"] += len(batch)

            current = collection.get(ids=ids, include=["metadatas"])
            current_by_id = dict(zip(current["ids"], current["metadatas"]))
            pending = []
            for doc in batch:
                did = doc["document_id"]
                existing = current_by_id.get(did)
                if existing is not None:
                    new_hash = sha(doc["text"])
                    if existing.get("text_sha256") != new_hash:
                        raise RuntimeError(f"Texto mudou para ID já indexado: {did}. Revise a coleção.")
                    if existing.get("embedding_model") != MODEL:
                        raise RuntimeError(f"Modelo diferente no documento existente: {did}")
                    report["skipped_existing"] += 1
                    continue
                pending.append(doc)

            if pending:
                texts = [d["text"] for d in pending]
                response = openai_client.embeddings.create(model=MODEL, input=texts)
                embeddings_by_index = {item.index: item.embedding for item in response.data}
                if set(embeddings_by_index) != set(range(len(pending))):
                    raise RuntimeError("API retornou índices de embeddings incompletos")
                vectors = [embeddings_by_index[i] for i in range(len(pending))]
                if any(len(vector) != VECTOR_SIZE for vector in vectors):
                    raise RuntimeError("Dimensão de embedding inesperada")

                collection.upsert(
                    ids=[d["document_id"] for d in pending],
                    documents=texts,
                    embeddings=vectors,
                    metadatas=[chroma_metadata(d) for d in pending],
                )
                report["indexed_in_this_run"] += len(pending)
                report["tokens_in_this_run"] += response.usage.total_tokens

            report["collection_count"] = collection.count()
            report["estimated_cost_usd_in_this_run"] = round(
                report["tokens_in_this_run"] * PRICE_PER_MILLION_TOKENS_USD / 1_000_000, 8
            )
            save_report(report)
            print(
                f"Lote {number}: lidos={len(batch)}, novos={len(pending)}, "
                f"total_no_chroma={report['collection_count']:,}, "
                f"tokens_acumulados={report['tokens_in_this_run']:,}"
            )
    finally:
        save_report(report)

    print("\nINDEXAÇÃO CONCLUÍDA")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--limit", type=int, default=10, help="Limite de documentos (padrão: 10)")
    mode.add_argument("--all", action="store_true", help="Indexar todos os documentos elegíveis")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true", help="Validar sem API nem banco vetorial")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit deve ser positivo")
    index(None if args.all else args.limit, args.batch_size, args.dry_run)


if __name__ == "__main__":
    main()
