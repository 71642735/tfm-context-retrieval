from __future__ import annotations
from statistics import median

import argparse
import csv
import json
from src.contextbench import DATASET_NAME
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from datasets import load_dataset


RESULTS_PATH = Path("results/downstream_results.jsonl")
FINAL_TASKS_PATH = Path("results/final_tasks.csv")
FINAL_RETRIEVAL_RESULTS_PATH = Path("results/final_retrieval_results.csv")

DEFINITIVE_STATUSES = {
    "invalid_patch",
    "not_resolved",
    "resolved",
}


def load_results(path: Path) -> list[dict[str, Any]]:
    """Carga todos los registros históricos del JSONL."""
    rows: list[dict[str, Any]] = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def load_final_task_ids(path: Path) -> set[str]:
    """Carga los IDs pertenecientes a la muestra final congelada."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["original_inst_id"] for row in reader}


def load_source_by_task() -> dict[str, str]:
    """
    Construye el mapa original_inst_id -> source a partir de ContextBench.

    ContextBench aporta la etiqueta source; final_tasks.csv sigue siendo
    quien determina qué tareas pertenecen a la muestra final congelada.
    """
    dataset = load_dataset(DATASET_NAME)
    tasks = dataset["train"]

    return {
        row["original_inst_id"]: row["source"]
        for row in tasks
    }


def get_task_id(row: dict[str, Any]) -> str | None:
    """Obtiene el identificador de tarea independientemente del nombre del campo."""
    return (
        row.get("task_id")
        or row.get("instance_id")
        or row.get("original_inst_id")
    )


def get_method(row: dict[str, Any]) -> str | None:
    """Obtiene el método de recuperación."""
    return row.get("retrieval_method") or row.get("method")


def filter_final_sample(
    rows: list[dict[str, Any]],
    final_task_ids: set[str],
) -> list[dict[str, Any]]:
    """Descarta pilotos y cualquier tarea ajena a la muestra final congelada."""
    return [
        row
        for row in rows
        if get_task_id(row) in final_task_ids
    ]


def filter_source(
    rows: list[dict[str, Any]],
    source_by_task: dict[str, str],
    source: str | None,
) -> list[dict[str, Any]]:
    """Filtra por fuente cuando se solicita."""
    if source is None:
        return rows

    return [
        row
        for row in rows
        if source_by_task.get(get_task_id(row)) == source
    ]


def select_definitive_results(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Conserva un único resultado definitivo por (tarea, método).

    Los infrastructure_error permanecen en el historial, pero no cuentan
    como resultados experimentales definitivos.
    """
    final: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        task_id = get_task_id(row)
        method = get_method(row)
        status = row.get("status")

        if task_id is None or method is None:
            continue

        if status in DEFINITIVE_STATUSES:
            final[(task_id, method)] = row

    return final


def print_summary(
    historical_rows: list[dict[str, Any]],
    final: dict[tuple[str, str], dict[str, Any]],
    source: str | None,
) -> None:
    """Imprime el resumen agregado."""
    statuses = Counter(row.get("status") for row in final.values())

    by_method: dict[str, Counter] = defaultdict(Counter)
    for (_, method), row in final.items():
        by_method[method][row.get("status")] += 1

    label = source if source is not None else "muestra final disponible"

    print(f"=== RESUMEN DOWNSTREAM: {label} ===")
    print(f"Registros históricos: {len(historical_rows)}")
    print(f"Condiciones definitivas: {len(final)}")
    print()

    print("POR ESTADO")
    print(dict(statuses))
    print()

    print("POR MÉTODO")
    for method in ("bm25", "semantic", "hybrid"):
        print(method, dict(by_method[method]))

    print()
    print(
        "Tareas únicas:",
        len({task_id for task_id, _ in final}),
    )
    print("Resolved:", statuses.get("resolved", 0))


def analyze_invalid_patches(
    final: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Clasifica los invalid_patch según contengan o no un diff reconocible."""
    counts = Counter()
    missing_files = 0

    for (task_id, method), row in final.items():
        if row.get("status") != "invalid_patch":
            continue

        patch_path = (
            Path("logs")
            / "downstream"
            / task_id
            / method
            / "patch.diff"
        )

        if not patch_path.exists():
            missing_files += 1
            continue

        text = patch_path.read_text(encoding="utf-8", errors="replace")

        has_diff = (
            "diff --git " in text
            or ("--- " in text and "+++ " in text and "@@" in text)
        )

        if has_diff:
            counts["has_diff"] += 1
        else:
            counts["no_diff"] += 1

    print()
    print("AUDITORÍA INVALID_PATCH")
    print(f"Sin diff reconocible: {counts['no_diff']}")
    print(f"Con diff reconocible: {counts['has_diff']}")
    print(f"Artefactos no encontrados: {missing_files}")


def analyze_recognizable_diffs(
    final: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Analiza la estructura de los invalid_patch que contienen un diff."""
    counts = Counter()

    for (task_id, method), row in final.items():
        if row.get("status") != "invalid_patch":
            continue

        patch_path = (
            Path("logs")
            / "downstream"
            / task_id
            / method
            / "patch.diff"
        )

        if not patch_path.exists():
            continue

        text = patch_path.read_text(encoding="utf-8", errors="replace")

        has_diff_git = "diff --git " in text
        has_file_headers = "--- " in text and "+++ " in text
        has_hunk = "@@" in text

        recognizable = has_diff_git or (has_file_headers and has_hunk)

        if not recognizable:
            continue

        if has_diff_git and has_file_headers and has_hunk:
            counts["complete_structure"] += 1
        elif has_file_headers and has_hunk:
            counts["unified_diff_without_git_header"] += 1
        else:
            counts["partial_or_malformed_structure"] += 1

    print()
    print("ESTRUCTURA DE DIFFS RECONOCIBLES")
    print(f"Estructura completa: {counts['complete_structure']}")
    print(
        "Unified diff sin cabecera git:",
        counts["unified_diff_without_git_header"],
    )
    print(
        "Estructura parcial/malformada:",
        counts["partial_or_malformed_structure"],
    )


def analyze_retrieval_vs_downstream(
    final: dict[tuple[str, str], dict[str, Any]],
    retrieval_path: Path,
) -> None:
    """
    Cruza la calidad de retrieval en K=10 con el resultado downstream.

    El análisis es descriptivo. Compara las métricas de recuperación entre
    invalid_patch, not_resolved y resolved, y entre patches aplicables y
    no aplicables.
    """
    retrieval: dict[tuple[str, str], dict[str, dict[str, float]]] = {}

    with retrieval_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if int(row["k"]) != 10:
                continue

            key = (row["task_id"], row["method"])
            level = row["level"]

            retrieval.setdefault(key, {})[level] = {
                "coverage": float(row["coverage"]),
                "precision": float(row["precision"]),
                "f1": float(row["f1"]),
            }

    joined: list[dict[str, Any]] = []

    for key, downstream_row in final.items():
        task_id, method = key
        metrics = retrieval.get(key)

        if metrics is None:
            raise RuntimeError(
                f"No hay resultados de retrieval K=10 para {task_id} / {method}"
            )

        if "file" not in metrics or "line" not in metrics:
            raise RuntimeError(
                f"Faltan niveles file/line para {task_id} / {method}"
            )

        status = downstream_row["status"]

        joined.append(
            {
                "task_id": task_id,
                "method": method,
                "status": status,
                "applicable": status in {"not_resolved", "resolved"},
                "file_coverage": metrics["file"]["coverage"],
                "file_precision": metrics["file"]["precision"],
                "file_f1": metrics["file"]["f1"],
                "line_coverage": metrics["line"]["coverage"],
                "line_precision": metrics["line"]["precision"],
                "line_f1": metrics["line"]["f1"],
            }
        )

    if len(joined) != 150:
        raise RuntimeError(
            f"Se esperaban 150 condiciones cruzadas y se obtuvieron {len(joined)}"
        )

    metric_names = (
        "file_coverage",
        "file_precision",
        "file_f1",
        "line_coverage",
        "line_precision",
        "line_f1",
    )

    def print_group(label: str, rows: list[dict[str, Any]]) -> None:
        print()
        print(f"{label} (n={len(rows)})")

        for metric in metric_names:
            values = [row[metric] for row in rows]
            mean = sum(values) / len(values)
            median_value = median(values)

            print(
                f"  {metric}: "
                f"mean={mean:.4f} "
                f"median={median_value:.4f}"
            )

    print()
    print("=== RETRIEVAL K=10 VS DOWNSTREAM ===")
    print(f"Condiciones cruzadas: {len(joined)}")

    for status in ("invalid_patch", "not_resolved", "resolved"):
        group = [row for row in joined if row["status"] == status]
        print_group(status, group)

    non_applicable = [
        row for row in joined
        if not row["applicable"]
    ]
    applicable = [
        row for row in joined
        if row["applicable"]
    ]

    print()
    print("=== APLICABILIDAD DEL PATCH ===")
    print_group("No aplicable", non_applicable)
    print_group("Aplicable", applicable)

    print()
    print("=== CASOS RESOLVED ===")

    for row in joined:
        if row["status"] != "resolved":
            continue

        print(
            row["task_id"],
            row["method"],
            f"file_f1={row['file_f1']:.4f}",
            f"line_f1={row['line_f1']:.4f}",
            f"file_coverage={row['file_coverage']:.4f}",
            f"line_coverage={row['line_coverage']:.4f}",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=("Verified", "Pro", "Poly"),
        default=None,
        help="Limita el resumen a una fuente de ContextBench.",
    )
    args = parser.parse_args()

    rows = load_results(RESULTS_PATH)
    final_task_ids = load_final_task_ids(FINAL_TASKS_PATH)
    source_by_task = load_source_by_task()

    rows = filter_final_sample(rows, final_task_ids)
    rows = filter_source(rows, source_by_task, args.source)

    final = select_definitive_results(rows)

    print_summary(rows, final, args.source)

    analyze_invalid_patches(final)

    analyze_recognizable_diffs(final)

    if args.source is None:
        analyze_retrieval_vs_downstream(
            final,
            FINAL_RETRIEVAL_RESULTS_PATH,
        )


if __name__ == "__main__":
    main()