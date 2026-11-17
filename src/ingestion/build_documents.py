"""Constrói documentos JSONL enriquecidos a partir das avaliações da Olist.

Etapa 3.4 do Tech Challenge (FIAP): preserva os textos da ingestão
original e acrescenta metadados de pedidos, entregas e categorias.

Execução, a partir da raiz do repositório:
    python src/ingestion/build_documents.py

Os campos ausentes dos metadados são serializados como null. A cardinalidade
é mantida em uma avaliação textual por documento, identificada por
review_id + '__' + order_id.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW = PROJECT_ROOT / "data" / "raw"
PROCESSED = PROJECT_ROOT / "data" / "processed"

DEFAULT_INPUT = RAW / "olist_order_reviews_dataset.csv"
DEFAULT_ORDERS = RAW / "olist_orders_dataset.csv"
DEFAULT_ITEMS = RAW / "olist_order_items_dataset.csv"
DEFAULT_PRODUCTS = RAW / "olist_products_dataset.csv"
DEFAULT_OUTPUT = PROCESSED / "olist_reviews_documents.jsonl"
DEFAULT_REPORT = PROCESSED / "ingestion_report.json"

REQUIRED_REVIEWS = {
    "review_id", "order_id", "review_score", "review_comment_title",
    "review_comment_message", "review_creation_date",
}
REQUIRED_ORDERS = {
    "order_id", "order_status", "order_purchase_timestamp",
    "order_delivered_customer_date", "order_estimated_delivery_date",
}
REQUIRED_ITEMS = {"order_id", "product_id"}
REQUIRED_PRODUCTS = {"product_id", "product_category_name"}


def read_rows(path: Path, required: set[str]):
    """Abre um CSV e valida a presença das colunas obrigatórias."""
    if not path.is_file():
        raise FileNotFoundError(f"Dataset não encontrado: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes em {path.name}: {sorted(missing)}")
        yield from reader


def clean_text(value: str | None) -> str:
    """Normaliza espaços sem alterar acentos, caixa ou pontuação."""
    return re.sub(r"\s+", " ", value or "").strip()


def compose_text(title: str, message: str) -> tuple[str, str]:
    if title and message:
        return f"Título: {title}\nComentário: {message}", "title_and_message"
    if message:
        return message, "message_only"
    if title:
        return f"Título: {title}", "title_only"
    return "", "no_text"


def iso_date(value: str | None, *, field: str, required: bool = False) -> str | None:
    """Retorna data ISO (AAAA-MM-DD), sem transformar ausências em datas falsas."""
    raw = (value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"Data obrigatória ausente: {field}")
        return None
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"Data inválida em {field}: {raw!r}") from exc


def load_products(path: Path) -> dict[str, str | None]:
    """Mapa product_id -> categoria original (português), com chave única."""
    products: dict[str, str | None] = {}
    for row in read_rows(path, REQUIRED_PRODUCTS):
        product_id = (row["product_id"] or "").strip()
        if not product_id:
            raise ValueError(f"product_id vazio em {path.name}")
        if product_id in products:
            raise ValueError(f"product_id duplicado em {path.name}: {product_id}")
        products[product_id] = (row["product_category_name"] or "").strip() or None
    return products


def load_items(path: Path, products: dict[str, str | None]):
    """Agrega itens por order_id ANTES da junção com avaliações.

    Isso impede que pedidos com vários itens multipliquem documentos.
    """
    item_counts: Counter[str] = Counter()
    categories_by_order: dict[str, set[str]] = {}
    missing_product_refs = 0

    for row in read_rows(path, REQUIRED_ITEMS):
        order_id = (row["order_id"] or "").strip()
        product_id = (row["product_id"] or "").strip()
        if not order_id or not product_id:
            raise ValueError(f"order_id/product_id vazio em {path.name}")
        item_counts[order_id] += 1
        if product_id not in products:
            missing_product_refs += 1
        category = products.get(product_id)
        if category:
            categories_by_order.setdefault(order_id, set()).add(category)
    return item_counts, categories_by_order, missing_product_refs


def load_orders(path: Path) -> dict[str, dict]:
    """Uma linha por order_id; diferença em dias corridos, como na EDA."""
    orders: dict[str, dict] = {}
    for row in read_rows(path, REQUIRED_ORDERS):
        order_id = (row["order_id"] or "").strip()
        if not order_id:
            raise ValueError(f"order_id vazio em {path.name}")
        if order_id in orders:
            raise ValueError(f"order_id duplicado em {path.name}: {order_id}")

        purchase_date = iso_date(
            row["order_purchase_timestamp"], field="order_purchase_timestamp"
        )
        delivered_date = iso_date(
            row["order_delivered_customer_date"], field="order_delivered_customer_date"
        )
        estimated_date = iso_date(
            row["order_estimated_delivery_date"], field="order_estimated_delivery_date"
        )
        delay_days = None
        if delivered_date is not None and estimated_date is not None:
            delay_days = (
                datetime.fromisoformat(delivered_date).date()
                - datetime.fromisoformat(estimated_date).date()
            ).days

        orders[order_id] = {
            "order_status": (row["order_status"] or "").strip() or None,
            "order_purchase_date": purchase_date,
            "delivery_delay_days": delay_days,
        }
    return orders


def ingest(
    input_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    orders_path: Path = DEFAULT_ORDERS,
    items_path: Path = DEFAULT_ITEMS,
    products_path: Path = DEFAULT_PRODUCTS,
) -> dict:
    paths = [Path(p).resolve() for p in (
        input_path, orders_path, items_path, products_path, output_path, report_path
    )]
    input_path, orders_path, items_path, products_path, output_path, report_path = paths
    if len(set(paths)) != len(paths):
        raise ValueError("Entradas, JSONL e relatório devem apontar para arquivos diferentes")

    products = load_products(products_path)
    item_counts, categories_by_order, missing_product_refs = load_items(items_path, products)
    orders = load_orders(orders_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    counters: Counter[str] = Counter()
    scores: Counter[str] = Counter()
    ids_seen: set[str] = set()

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as destination:
            for row_number, row in enumerate(read_rows(input_path, REQUIRED_REVIEWS), start=2):
                counters["total_rows"] += 1
                review_id = (row["review_id"] or "").strip()
                order_id = (row["order_id"] or "").strip()
                if not review_id or not order_id:
                    raise ValueError(f"Linha {row_number}: review_id/order_id ausente")
                document_id = f"{review_id}__{order_id}"
                if document_id in ids_seen:
                    raise ValueError(f"Linha {row_number}: document_id duplicado: {document_id}")
                ids_seen.add(document_id)

                try:
                    score = int((row["review_score"] or "").strip())
                except ValueError as exc:
                    raise ValueError(f"Linha {row_number}: review_score inválido") from exc
                if score not in {1, 2, 3, 4, 5}:
                    raise ValueError(f"Linha {row_number}: nota fora do intervalo 1–5: {score}")

                title = clean_text(row["review_comment_title"])
                message = clean_text(row["review_comment_message"])
                text, text_type = compose_text(title, message)
                counters[text_type] += 1
                if not text:
                    counters["excluded_no_text"] += 1
                    continue

                order = orders.get(order_id)
                if order is None:
                    counters["documents_without_order"] += 1
                quantity = item_counts.get(order_id)
                if quantity is None:
                    counters["documents_without_items"] += 1
                categories = sorted(categories_by_order.get(order_id, set())) or None
                if categories is None:
                    counters["documents_without_category"] += 1
                delay = order["delivery_delay_days"] if order else None
                if delay is None:
                    counters["documents_without_delivery_delay"] += 1

                document = {
                    "document_id": document_id,
                    "text": text,
                    "metadata": {
                        "review_id": review_id,
                        "order_id": order_id,
                        "review_score": score,
                        "review_creation_date": iso_date(
                            row["review_creation_date"],
                            field=f"review_creation_date linha {row_number}",
                            required=True,
                        ),
                        "text_type": text_type,
                        "order_status": order["order_status"] if order else None,
                        "order_purchase_date": order["order_purchase_date"] if order else None,
                        "delivery_delay_days": delay,
                        "product_categories": categories,
                        "quantity_items": quantity,
                    },
                }
                destination.write(json.dumps(document, ensure_ascii=False) + "\n")
                counters["documents_created"] += 1
                scores[str(score)] += 1

        # O relatório também só é produzido após todos os documentos serem validados.
        assert counters["total_rows"] == counters["documents_created"] + counters["excluded_no_text"]
        report = {
            "source_files": {
                "reviews": input_path.name,
                "orders": orders_path.name,
                "items": items_path.name,
                "products": products_path.name,
            },
            "output_file": output_path.name,
            "total_rows": counters["total_rows"],
            "documents_created": counters["documents_created"],
            "excluded_no_text": counters["excluded_no_text"],
            "text_types": {
                name: counters[name] for name in (
                    "title_and_message", "message_only", "title_only"
                )
            },
            "documents_by_score": {str(score): scores[str(score)] for score in range(1, 6)},
            "metadata_coverage": {
                "documents_without_order": counters["documents_without_order"],
                "documents_without_items": counters["documents_without_items"],
                "documents_without_category": counters["documents_without_category"],
                "documents_without_delivery_delay": counters["documents_without_delivery_delay"],
            },
            "input_quality": {
                "orders_loaded": len(orders),
                "products_loaded": len(products),
                "orders_with_items": len(item_counts),
                "item_rows_with_unknown_product": missing_product_refs,
            },
            "document_id_rule": "review_id + '__' + order_id",
            "processing": "Espaços normalizados; texto original preservado quanto a acentos, caixa e pontuação; atraso em dias corridos; categorias agregadas por pedido",
        }
        # Evita relatório parcial em caso de falha; geração da saída é atômica.
        os.replace(temp_path, output_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV de avaliações")
    parser.add_argument("--orders", type=Path, default=DEFAULT_ORDERS, help="CSV de pedidos")
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS, help="CSV de itens dos pedidos")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS, help="CSV de produtos")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSONL gerado")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Relatório de auditoria")
    args = parser.parse_args()

    report = ingest(
        args.input, args.output, args.report,
        orders_path=args.orders, items_path=args.items, products_path=args.products,
    )
    print("INGESTÃO ENRIQUECIDA CONCLUÍDA")
    print(f"Avaliações lidas:       {report['total_rows']:,}")
    print(f"Documentos gerados:     {report['documents_created']:,}")
    print(f"Sem texto:              {report['excluded_no_text']:,}")
    print("Cobertura de metadados (ausências):")
    for name, count in report["metadata_coverage"].items():
        print(f"  {name}: {count:,}")
    print(f"JSONL: {args.output.resolve()}")
    print(f"Relatório: {args.report.resolve()}")


if __name__ == "__main__":
    main()
