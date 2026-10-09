import argparse
import csv
import json
import time
import traceback
from pathlib import Path

from src.chunking import Chunk, chunk_python_repository
from src.contextbench import load_task
from src.evaluation.retrieval_metrics import evaluate_retrieval
from src.repo_manager import prepare_repository
from src.retrieval.bm25 import rank_bm25
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


K_VALUES = (5, 10, 20)
FUSION_DEPTH = 100
BATCH_SIZE = 8

RESULTS_DIR = Path("results")
TASKS_FILE = RESULTS_DIR / "final_tasks.csv"
RESULTS_FILE = RESULTS_DIR / "final_retrieval_results.csv"
FAILURES_FILE = RESULTS_DIR / "final_retrieval_failures.csv"

FIELDNAMES = [
    "task_id",
    "method",
    "k",
    "level",
    "coverage",
    "precision",
    "f1",
]


def load_final_task_ids() -> list[str]:
    """
    Carga los identificadores de las tareas de la muestra final.
    """
    with TASKS_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    task_ids = [
        row["original_inst_id"]
        for row in rows
    ]

    if not task_ids:
        raise ValueError(
            f"No se encontraron tareas en {TASKS_FILE}"
        )

    if len(task_ids) != len(set(task_ids)):
        raise ValueError(
            "final_tasks.csv contiene task_id duplicados."
        )

    return task_ids


def load_existing_results() -> list[dict]:
    """
    Carga los resultados finales existentes, si los hay.
    """
    if not RESULTS_FILE.exists():
        return []

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def completed_task_ids(rows: list[dict]) -> set[str]:
    """
    Una tarea solo se considera completa si contiene exactamente
    las 18 combinaciones esperadas:

    3 métodos x 3 valores de K x 2 niveles.
    """
    expected = {
        (method, str(k), level)
        for method in ("bm25", "semantic", "hybrid")
        for k in K_VALUES
        for level in ("file", "line")
    }

    combinations_by_task: dict[
        str,
        set[tuple[str, str, str]],
    ] = {}

    for row in rows:
        task_id = row["task_id"]

        combinations_by_task.setdefault(
            task_id,
            set(),
        ).add(
            (
                row["method"],
                str(row["k"]),
                row["level"],
            )
        )

    return {
        task_id
        for task_id, combinations
        in combinations_by_task.items()
        if combinations == expected
    }


def remove_task_rows(
    rows: list[dict],
    task_id: str,
) -> list[dict]:
    """
    Elimina resultados parciales de una tarea antes de reintentarlo.
    """
    return [
        row
        for row in rows
        if row["task_id"] != task_id
    ]


def evaluate_ranking(
    task_id: str,
    method: str,
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
    repo_root: Path,
) -> list[dict]:
    """
    Evalúa un ranking para K=5, 10 y 20
    a nivel de fichero y de línea.
    """
    rows = []

    for k in K_VALUES:
        metrics = evaluate_retrieval(
            predicted_chunks=ranked_chunks[:k],
            gold_context=gold_context,
            repo_root=repo_root,
        )

        for level in ("file", "line"):
            values = metrics[level]

            rows.append(
                {
                    "task_id": task_id,
                    "method": method,
                    "k": k,
                    "level": level,
                    "coverage": values["coverage"],
                    "precision": values["precision"],
                    "f1": values["f1"],
                }
            )

    return rows


def run_task(
    task_id: str,
    semantic_retriever: SemanticRetriever,
) -> list[dict]:
    """
    Ejecuta BM25, recuperación semántica e híbrida
    sobre una tarea.
    """
    task = load_task(task_id)

    repository = task["repo"]
    base_commit = task["base_commit"]
    query = task["problem_statement"]
    gold_context = json.loads(task["gold_context"])

    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    print()
    print("=" * 70)
    print(f"Tarea: {task_id}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {base_commit}")
    print("=" * 70)

    # -------------------------------------------------
    # CHUNKING
    # -------------------------------------------------

    print("\nConstruyendo chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks):,}")

    rows = []

    # -------------------------------------------------
    # BM25
    # -------------------------------------------------

    print("\nEjecutando BM25...")

    bm25_ranked_chunks, _, _ = rank_bm25(
        chunks=chunks,
        query=query,
    )

    rows.extend(
        evaluate_ranking(
            task_id=task_id,
            method="bm25",
            ranked_chunks=bm25_ranked_chunks,
            gold_context=gold_context,
            repo_root=repo_root,
        )
    )

    # -------------------------------------------------
    # SEMÁNTICO
    # -------------------------------------------------

    print("\nEjecutando recuperación semántica...")

    cache_path = semantic_cache_path(
        repository=repository,
        commit=base_commit,
    )

    print(f"Caché semántica: {cache_path}")

    semantic_start = time.perf_counter()
    cache_existed = cache_path.exists()

    embeddings = semantic_retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=repository,
        commit=base_commit,
        batch_size=BATCH_SIZE,
    )

    semantic_elapsed = (
        time.perf_counter() - semantic_start
    )

    if cache_existed:
        print(
            "Índice semántico reutilizado desde caché "
            f"en {semantic_elapsed:.2f} s."
        )
    else:
        print(
            "Índice semántico generado y guardado "
            f"en {semantic_elapsed / 60:.2f} min."
        )

    semantic_results = semantic_retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=FUSION_DEPTH,
    )

    semantic_ranked_chunks = [
        result.chunk
        for result in semantic_results
    ]

    rows.extend(
        evaluate_ranking(
            task_id=task_id,
            method="semantic",
            ranked_chunks=semantic_ranked_chunks,
            gold_context=gold_context,
            repo_root=repo_root,
        )
    )

    # -------------------------------------------------
    # HÍBRIDO: RRF
    # -------------------------------------------------

    print("\nEjecutando recuperación híbrida...")

    hybrid_results = reciprocal_rank_fusion(
        bm25_chunks=bm25_ranked_chunks[:FUSION_DEPTH],
        semantic_chunks=semantic_ranked_chunks[:FUSION_DEPTH],
    )

    hybrid_ranked_chunks = [
        result.chunk
        for result in hybrid_results
    ]

    rows.extend(
        evaluate_ranking(
            task_id=task_id,
            method="hybrid",
            ranked_chunks=hybrid_ranked_chunks,
            gold_context=gold_context,
            repo_root=repo_root,
        )
    )

    return rows


def save_results(rows: list[dict]) -> None:
    """
    Guarda los resultados estructurados en CSV.
    """
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RESULTS_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()
        writer.writerows(rows)


def save_failure(
    task_id: str,
    error: Exception,
) -> None:
    """
    Registra un fallo sin eliminar los resultados
    de las tareas anteriores.
    """
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_exists = FAILURES_FILE.exists()

    with FAILURES_FILE.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "task_id",
                "error_type",
                "error_message",
            ],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "task_id": task_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )


def parse_args() -> argparse.Namespace:
    """
    Procesa los argumentos de línea de comandos.

    Sin --task se ejecuta la muestra final completa.
    Con --task se ejecuta únicamente esa tarea.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta el experimento final "
            "de recuperación."
        )
    )

    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help=(
            "Ejecuta únicamente una tarea concreta "
            "de la muestra final."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    all_task_ids = load_final_task_ids()

    if args.task is not None:
        if args.task not in all_task_ids:
            raise ValueError(
                f"La tarea {args.task!r} "
                "no pertenece a la muestra final."
            )

        task_ids = [args.task]
    else:
        task_ids = all_task_ids

    all_rows = load_existing_results()

    completed = completed_task_ids(all_rows)
    completed_selected = completed.intersection(task_ids)

    print("=" * 70)
    print("EXPERIMENTO FINAL DE RECUPERACIÓN")
    print(f"Tareas seleccionadas: {len(task_ids)}")
    print(
        f"Tareas ya completadas: "
        f"{len(completed_selected)}"
    )
    print(
        f"Tareas pendientes: "
        f"{len(task_ids) - len(completed_selected)}"
    )
    print(f"Resultados: {RESULTS_FILE}")
    print("=" * 70)

    if len(completed_selected) == len(task_ids):
        print("\nTodas las tareas ya están completadas.")
        return

    print("\nCargando UniXcoder una única vez...")
    semantic_retriever = SemanticRetriever()

    successful_this_run = 0
    failed_this_run = 0

    for index, task_id in enumerate(
        task_ids,
        start=1,
    ):
        if task_id in completed:
            print(
                f"\n[{index}/{len(task_ids)}] "
                f"OMITIDA (ya completada): {task_id}"
            )
            continue

        print()
        print("#" * 70)
        print(
            f"EXPERIMENTO FINAL {index}/"
            f"{len(task_ids)}"
        )
        print("#" * 70)

        # Si hubiera quedado una tarea parcial en el CSV,
        # eliminamos sus filas antes de reintentarlo.
        all_rows = remove_task_rows(
            all_rows,
            task_id,
        )
        save_results(all_rows)

        try:
            task_start = time.perf_counter()

            rows = run_task(
                task_id=task_id,
                semantic_retriever=semantic_retriever,
            )

            elapsed = (
                time.perf_counter() - task_start
            )

            if len(rows) != 18:
                raise ValueError(
                    f"La tarea produjo {len(rows)} filas; "
                    "se esperaban 18."
                )

            all_rows.extend(rows)
            save_results(all_rows)

            successful_this_run += 1

            print()
            print(f"Tarea completada: {task_id}")
            print(
                f"Duración total de la tarea: "
                f"{elapsed / 60:.2f} min."
            )
            print(
                f"Filas acumuladas: {len(all_rows)}"
            )

        except Exception as error:
            failed_this_run += 1

            print()
            print("!" * 70)
            print(f"ERROR EN TAREA: {task_id}")
            print(
                f"{type(error).__name__}: {error}"
            )
            print(
                "La ejecución continuará "
                "con la siguiente tarea."
            )
            print("!" * 70)

            traceback.print_exc()

            save_failure(
                task_id=task_id,
                error=error,
            )

    final_completed = completed_task_ids(all_rows)
    final_completed_selected = (
        final_completed.intersection(task_ids)
    )

    print()
    print("=" * 70)
    print("EJECUCIÓN FINALIZADA")
    print(f"Tareas seleccionadas: {len(task_ids)}")
    print(
        f"Tareas completas: "
        f"{len(final_completed_selected)}"
    )
    print(
        f"Completadas en esta ejecución: "
        f"{successful_this_run}"
    )
    print(
        f"Fallidas en esta ejecución: "
        f"{failed_this_run}"
    )
    print(f"Filas guardadas: {len(all_rows)}")
    print(f"Resultados: {RESULTS_FILE}")

    if FAILURES_FILE.exists():
        print(f"Registro de fallos: {FAILURES_FILE}")

    print("=" * 70)


if __name__ == "__main__":
    main()