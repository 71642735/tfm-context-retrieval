from dataclasses import dataclass
from pathlib import Path

from src.chunking import Chunk, chunk_python_repository
from src.contextbench import load_task
from src.repo_manager import prepare_repository
from src.retrieval.bm25 import rank_bm25
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


TOP_K = 10
FUSION_DEPTH = 100


@dataclass
class RetrievalContext:
    task_id: str
    repository: str
    base_commit: str
    repo_root: Path
    problem_statement: str
    method: str
    chunks: list[Chunk]


def retrieve_context(
    task_id: str,
    method: str,
    semantic_retriever: SemanticRetriever | None = None,
) -> RetrievalContext:
    """
    Recupera el Top-K de chunks que se proporcionará al LLM.

    Métodos soportados:
    - bm25
    - semantic
    - hybrid
    """
    if method not in {"bm25", "semantic", "hybrid"}:
        raise ValueError(
            f"Método de recuperación no soportado: {method}"
        )

    task = load_task(task_id)

    repository = task["repo"]
    base_commit = task["base_commit"]
    query = task["problem_statement"]

    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    print(f"\nTarea: {task_id}")
    print(f"Repositorio: {repository}")
    print(f"Método: {method}")

    print("\nConstruyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks disponibles: {len(chunks)}")

    # BM25 se calcula siempre porque:
    # - BM25 lo necesita directamente.
    # - Hybrid necesita el ranking BM25 para RRF.
    # - Para semantic puro no sería necesario, pero mantener esta
    #   estructura simplifica temporalmente el flujo.
    bm25_ranked_chunks, _, _ = rank_bm25(
        chunks=chunks,
        query=query,
    )

    if method == "bm25":
        selected_chunks = bm25_ranked_chunks[:TOP_K]

    else:
        if semantic_retriever is None:
            semantic_retriever = SemanticRetriever()

        cache_path = semantic_cache_path(
            repository=repository,
            commit=base_commit,
        )

        if not cache_path.exists():
            raise FileNotFoundError(
                "No existe la caché semántica esperada para "
                f"{task_id}: {cache_path}"
            )

        print(f"Cargando caché semántica: {cache_path}")

        embeddings = semantic_retriever.load_or_build_embeddings(
            chunks=chunks,
            path=cache_path,
            repository=repository,
            commit=base_commit,
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

        if method == "semantic":
            selected_chunks = semantic_ranked_chunks[:TOP_K]

        else:
            hybrid_results = reciprocal_rank_fusion(
                bm25_chunks=bm25_ranked_chunks[:FUSION_DEPTH],
                semantic_chunks=semantic_ranked_chunks[:FUSION_DEPTH],
            )

            selected_chunks = [
                result.chunk
                for result in hybrid_results[:TOP_K]
            ]

    if len(selected_chunks) != TOP_K:
        raise ValueError(
            f"Se esperaban {TOP_K} chunks, "
            f"pero se obtuvieron {len(selected_chunks)}."
        )

    return RetrievalContext(
        task_id=task_id,
        repository=repository,
        base_commit=base_commit,
        repo_root=repo_root,
        problem_statement=query,
        method=method,
        chunks=selected_chunks,
    )