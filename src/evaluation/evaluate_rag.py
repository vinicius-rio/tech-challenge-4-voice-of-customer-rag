"""Avaliação reproduzível do RAG Olist com checagens automáticas limitadas.

Na raiz do projeto:
    python -m src.evaluation.evaluate_rag --dry-run
    python -m src.evaluation.evaluate_rag --limit 3
    python -m src.evaluation.evaluate_rag

A execução real utiliza embeddings e um LLM via API OpenAI (há cobrança).
O relatório é salvo em data/processed/, que deve permanecer no .gitignore.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.rag.answer_reviews import DEFAULT_MODEL, answer_question

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "src" / "evaluation" / "rag_evaluation_cases.json"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "rag_evaluation_report.json"
EXPECTED_BEHAVIORS = {"grounded_answer", "acknowledge_uncertainty", "abstain"}

# Indicadores linguísticos conservadores: servem para triagem, não para
# comprovar fundamentação semântica, ausência de alucinações ou precisão.
UNCERTAINTY_PATTERNS = (
    r"\bnao encontrei evidencias?\b",
    r"\bevidencias? insuficientes\b",
    r"\bnao (?:ha|existem) evidencias?\b",
    r"\bnao (?:e|foi|seria) possivel\b",
    r"\bnao (?:consigo|conseguimos|podemos) (?:determinar|identificar|concluir)\b",
    r"\bnao (?:permite|permitem|fornece|fornecem)\b",
    r"\bnao ha (?:dados|informacoes) suficientes\b",
    r"\bsem (?:dados|evidencias|informacoes) suficientes\b",
)


def normalize(text: str) -> str:
    """Remove acentos apenas para fazer correspondência das expressões."""
    base = unicodedata.normalize("NFKD", text.lower())
    base = "".join(char for char in base if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", base).strip()


def detects_uncertainty(answer: str) -> bool:
    normalized = normalize(answer)
    return any(re.search(pattern, normalized) for pattern in UNCERTAINTY_PATTERNS)


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de casos não encontrado: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("O arquivo de avaliação deve ser uma lista JSON não vazia.")

    seen_ids: set[str] = set()
    for number, case in enumerate(raw, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Caso {number}: esperado objeto JSON.")
        case_id = case.get("id")
        question = case.get("question")
        expected = case.get("expected_behavior")
        top_k = case.get("top_k", 5)
        delayed_only = case.get("delayed_only", False)
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"Caso {number}: id obrigatório.")
        if case_id in seen_ids:
            raise ValueError(f"ID duplicado: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Caso {case_id}: question deve ser texto não vazio.")
        if expected not in EXPECTED_BEHAVIORS:
            raise ValueError(f"Caso {case_id}: expected_behavior inválido: {expected!r}")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError(f"Caso {case_id}: top_k deve estar entre 1 e 100.")
        if not isinstance(delayed_only, bool):
            raise ValueError(f"Caso {case_id}: delayed_only deve ser booleano.")
    return raw


def check_result(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Checagens determinísticas e heurísticas (não são avaliação humana)."""
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    citations = [int(value) for value in re.findall(r"\[(\d+)\]", answer)]
    valid_citations = all(1 <= ref <= len(sources) for ref in citations)
    sources_valid = all(
        source.get("reference") == f"[{number}]" and bool(source.get("document_id"))
        for number, source in enumerate(sources, start=1)
    )
    abstention_heuristic = detects_uncertainty(answer)
    expected = case["expected_behavior"]

    checks: dict[str, bool] = {
        "nonempty_answer": bool(answer.strip()),
        "sources_well_formed": sources_valid,
        "citations_in_range": valid_citations,
    }
    if expected == "grounded_answer":
        checks["has_retrieved_sources"] = bool(sources)
        checks["cites_at_least_one_source"] = bool(citations)
        checks["not_an_abstention_heuristic"] = not abstention_heuristic
    elif expected in {"acknowledge_uncertainty", "abstain"}:
        checks["uncertainty_expression_detected_heuristic"] = abstention_heuristic

    return {
        "automatic_checks": checks,
        "automatic_passed": all(checks.values()),
        "cited_reference_numbers": sorted(set(citations)),
        "uncertainty_expression_detected": abstention_heuristic,
        "manual_review": {
            "status": "pending",
            "faithfulness": None,
            "question_relevance": None,
            "notes": "Verificar se cada afirmação é sustentada pelas fontes; regex não prova fidelidade.",
        },
    }


def evaluate_cases(
    cases: list[dict[str, Any]], model: str, output: Path
) -> dict[str, Any]:
    results = []
    for number, case in enumerate(cases, start=1):
        print(f"[{number}/{len(cases)}] {case['id']}: {case['question']}", flush=True)
        item: dict[str, Any] = {
            "case_id": case["id"],
            "question": case["question"],
            "expected_behavior": case["expected_behavior"],
            "top_k": case.get("top_k", 5),
            "delayed_only": case.get("delayed_only", False),
        }
        try:
            rag_result = answer_question(
                question=case["question"],
                top_k=case.get("top_k", 5),
                delayed_only=case.get("delayed_only", False),
                model=model,
            )
            item.update(check_result(case, rag_result))
            item.update({
                "answer": rag_result["answer"],
                "sources": rag_result.get("sources") or [],
                "model": rag_result.get("model"),
                "usage": rag_result.get("usage"),
                "error": None,
            })
            label = "PASSOU" if item["automatic_passed"] else "REVISAR"
            print(f"    Checagens automáticas: {label}", flush=True)
        except Exception as exc:
            item.update({
                "automatic_checks": {},
                "automatic_passed": False,
                "cited_reference_numbers": [],
                "uncertainty_expression_detected": None,
                "manual_review": {"status": "pending", "faithfulness": None, "question_relevance": None},
                "answer": None,
                "sources": [],
                "model": None,
                "usage": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"    ERRO: {item['error']}", flush=True)
        results.append(item)

    input_tokens = sum((row.get("usage") or {}).get("input_tokens", 0) for row in results)
    output_tokens = sum((row.get("usage") or {}).get("output_tokens", 0) for row in results)
    summary = {
        "total_cases": len(results),
        "automatic_passed": sum(row["automatic_passed"] for row in results),
        "automatic_failed_or_error": sum(not row["automatic_passed"] for row in results),
        "errors": sum(row["error"] is not None for row in results),
        "manual_review_pending": len(results),
        "generation_input_tokens": input_tokens,
        "generation_output_tokens": output_tokens,
        "note": "Verificações automáticas são regras/heurísticas; não equivalem à acurácia ou faithfulness do RAG.",
    }
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "summary": summary,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nAVALIAÇÃO CONCLUÍDA")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Relatório: {output}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Arquivo JSON de perguntas")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Saída JSON do relatório")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo OpenAI para a geração")
    parser.add_argument("--limit", type=int, help="Executar apenas os primeiros N casos")
    parser.add_argument("--dry-run", action="store_true", help="Validar os casos sem consultar APIs")
    args = parser.parse_args()

    try:
        cases = load_cases(args.cases)
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit precisa ser maior que zero.")
            cases = cases[: args.limit]
        if args.dry_run:
            print(f"MODO DE SIMULAÇÃO: {len(cases)} casos validados; nenhuma chamada à API.")
            for case in cases:
                print(f"- {case['id']} ({case['expected_behavior']}): {case['question']}")
            return
        report = evaluate_cases(cases, model=args.model, output=args.output)
        if report["summary"]["errors"]:
            parser.exit(status=1, message="Alguns casos falharam na execução; confira o relatório.\n")
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.exit(status=1, message=f"ERRO: {exc}\n")


if __name__ == "__main__":
    main()
