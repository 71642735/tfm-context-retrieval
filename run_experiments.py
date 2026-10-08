import json

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


def main() -> None:
    task_id = "astropy__astropy-12907"

    rows = run_task(task_id)

    print("\n=== RESULTADOS ESTRUCTURADOS ===")

    for row in rows:
        print(row)


if __name__ == "__main__":
    main()