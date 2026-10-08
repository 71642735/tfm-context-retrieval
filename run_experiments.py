import json
import csv
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

RESULTS_DIR = Path("results")
RESULTS_FILE = RESULTS_DIR / "retrieval_results.csv"

MINI_PILOT_TASKS = [
    "django__django-12663",
    "Significant-Gravitas__AutoGPT-4652",
    "matplotlib__matplotlib-25479",
    "langchain-ai__langchain-6765",
    "scikit-learn__scikit-learn-25931",
]

def evaluate_ranking(
    task_id: str,
    method: str,
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
    repo_root,
) -> list[dict]:
    """
    Convierte la evaluación de un ranking en filas estructuradas.
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


def run_task(task_id: str) -> list[dict]:
    """
    Ejecuta BM25, semántico e híbrido sobre una tarea.
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

    print(f"Chunks: {len(chunks)}")

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

    semantic_retriever = SemanticRetriever()

    embeddings = semantic_retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=repository,
        commit=base_commit,
        batch_size=8,
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
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "task_id",
        "method",
        "k",
        "level",
        "coverage",
        "precision",
        "f1",
    ]

    with RESULTS_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResultados guardados en: {RESULTS_FILE}")


def main() -> None:
    all_rows = []

    for index, task_id in enumerate(
        MINI_PILOT_TASKS,
        start=1,
    ):
        print()
        print("#" * 70)
        print(
            f"MINI-PILOTO {index}/"
            f"{len(MINI_PILOT_TASKS)}"
        )
        print("#" * 70)

        rows = run_task(task_id)

        all_rows.extend(rows)

        # Guardamos después de cada tarea para no perder
        # resultados si una ejecución posterior falla.
        save_results(all_rows)

        print(
            f"\nTarea completada: {task_id}"
        )
        print(
            f"Filas acumuladas: {len(all_rows)}"
        )

    print()
    print("=" * 70)
    print("MINI-PILOTO COMPLETADO")
    print(f"Tareas: {len(MINI_PILOT_TASKS)}")
    print(f"Filas: {len(all_rows)}")
    print(f"CSV: {RESULTS_FILE}")
    print("=" * 70)

if __name__ == "__main__":
    main()