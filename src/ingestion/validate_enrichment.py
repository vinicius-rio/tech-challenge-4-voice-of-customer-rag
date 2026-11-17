"""Valida a ingestão enriquecida da Olist diretamente contra os CSVs originais.

Não exige um backup da versão pré-enriquecimento.
Execute na raiz do repositório:
    python src/ingestion/validate_enrichment.py
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
JSONL = OUT / "olist_reviews_documents.jsonl"
REPORT = OUT / "ingestion_report.json"
BASELINE = OUT / "olist_reviews_documents_pre_enrichment.jsonl"

NEW_FIELDS = (
    "order_status", "order_purchase_date", "delivery_delay_days",
    "product_categories", "quantity_items",
)


def rows(filename):
    with (RAW / filename).open(encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def as_date(value):
    return datetime.fromisoformat(value).date() if value and value.strip() else None


def iso(value):
    d = as_date(value)
    return d.isoformat() if d is not None else None


def validate():
    print("Preparando referências dos CSVs originais...")
    products = {r["product_id"]: r["product_category_name"] or None
                for r in rows("olist_products_dataset.csv")}
    quantities = Counter()
    categories = defaultdict(set)
    for r in rows("olist_order_items_dataset.csv"):
        oid = r["order_id"]
        quantities[oid] += 1
        category = products.get(r["product_id"])
        if category:
            categories[oid].add(category)

    orders = {}
    for r in rows("olist_orders_dataset.csv"):
        delivered = as_date(r["order_delivered_customer_date"])
        estimated = as_date(r["order_estimated_delivery_date"])
        orders[r["order_id"]] = {
            "order_status": r["order_status"] or None,
            "order_purchase_date": iso(r["order_purchase_timestamp"]),
            "delivery_delay_days": (delivered - estimated).days
            if delivered is not None and estimated is not None else None,
        }

    counts = Counter()
    ids = set()
    examples = {}
    with JSONL.open(encoding="utf-8") as generated:
        generated_lines = iter(generated)
        for source_line, r in enumerate(rows("olist_order_reviews_dataset.csv"), start=2):
            counts["total_rows"] += 1
            title, message = clean(r["review_comment_title"]), clean(r["review_comment_message"])
            if title and message:
                expected_text = f"Título: {title}\nComentário: {message}"
                kind = "title_and_message"
            elif message:
                expected_text, kind = message, "message_only"
            elif title:
                expected_text, kind = f"Título: {title}", "title_only"
            else:
                counts["excluded_no_text"] += 1
                continue

            raw_line = next(generated_lines, None)
            if raw_line is None:
                raise AssertionError(f"JSONL terminou antes da avaliação na linha {source_line}")
            doc = json.loads(raw_line)
            oid = r["order_id"]
            expected_id = f"{r['review_id']}__{oid}"
            assert doc["document_id"] == expected_id, f"ID incorreto na linha {source_line}"
            assert expected_id not in ids, f"ID duplicado na linha {source_line}"
            ids.add(expected_id)
            assert doc["text"] == expected_text, f"Texto alterado na linha {source_line}"
            assert set(doc) == {"document_id", "text", "metadata"}, f"Estrutura inválida na linha {source_line}"

            expected_meta = {
                "review_id": r["review_id"],
                "order_id": oid,
                "review_score": int(r["review_score"]),
                "review_creation_date": iso(r["review_creation_date"]),
                "text_type": kind,
                **orders.get(oid, {
                    "order_status": None, "order_purchase_date": None,
                    "delivery_delay_days": None,
                }),
                "product_categories": sorted(categories[oid]) or None,
                "quantity_items": quantities.get(oid) or None,
            }
            assert doc["metadata"] == expected_meta, f"Metadados divergentes na linha {source_line}"
            counts["documents_created"] += 1
            counts[f"type_{kind}"] += 1
            counts[f"score_{r['review_score']}"] += 1
            for field in NEW_FIELDS:
                if expected_meta[field] is not None:
                    counts[f"{field}_available"] += 1
            if len(examples) < 3:
                examples.setdefault(kind, doc)
        assert next(generated_lines, None) is None, "JSONL contém registros excedentes"

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for field in ("total_rows", "documents_created", "excluded_no_text"):
        assert report[field] == counts[field], f"Relatório divergente: {field}"
    for kind in ("title_and_message", "message_only", "title_only"):
        assert report["text_types"][kind] == counts[f"type_{kind}"], f"Tipo divergente: {kind}"
    for score in range(1, 6):
        assert report["documents_by_score"][str(score)] == counts[f"score_{score}"], f"Nota divergente: {score}"
    for report_name, field in (
        ("documents_without_order", "order_status"),
        ("documents_without_items", "quantity_items"),
        ("documents_without_category", "product_categories"),
        ("documents_without_delivery_delay", "delivery_delay_days"),
    ):
        # Orders may exist without a status; the dataset Olist always populates order_status.
        actual_missing = counts["documents_created"] - counts[f"{field}_available"]
        assert report["metadata_coverage"][report_name] == actual_missing, f"Cobertura divergente: {report_name}"

    # Backups antigos, se existirem, são comparados adicionalmente.
    baseline_checked = False
    if BASELINE.is_file():
        with BASELINE.open(encoding="utf-8") as old_file, JSONL.open(encoding="utf-8") as new_file:
            for n, pair in enumerate(zip_longest(old_file, new_file), 1):
                old_line, new_line = pair
                assert old_line is not None and new_line is not None, f"Backup com tamanho divergente: {n}"
                old, new = json.loads(old_line), json.loads(new_line)
                assert old["document_id"] == new["document_id"], f"ID alterado: {n}"
                assert old["text"] == new["text"], f"Texto alterado: {n}"
                for key, value in old["metadata"].items():
                    assert new["metadata"].get(key) == value, f"Metadado original alterado: {key}, linha {n}"
            baseline_checked = True

    print("\nVALIDAÇÃO APROVADA")
    print(f"Documentos validados contra o CSV: {counts['documents_created']:,}")
    print(f"IDs únicos e textos preservados: {len(ids):,}")
    print(f"Registros sem texto excluídos: {counts['excluded_no_text']:,}")
    print("Relatório de ingestão: consistente")
    print("Comparação com backup: " + ("aprovada" if baseline_checked else "dispensada (backup inexistente)"))
    print("Cobertura dos metadados:")
    for field in NEW_FIELDS:
        print(f"  {field}: {counts[f'{field}_available']:,} disponíveis")
    print("\nExemplos de documentos:")
    for kind, doc in examples.items():
        print(f"\n--- {kind} ---")
        print(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    validate()
