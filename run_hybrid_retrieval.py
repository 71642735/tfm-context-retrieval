import argparse
import json
import re

from rank_bm25 import BM25Okapi

from src.chunking import (
    Chunk,
    chunk_python_repository,
)
from src.contextbench import load_task
from src.evaluation.retrieval_metrics import evaluate_retrieval
from src.repo_manager import prepare_repository
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


FUSION_DEPTH = 100
TOP_K = 20
EVALUATION_K_VALUES = (5, 10, 20)


def parse_args():
    """
    Lee la tarea de ContextBench desde la línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta recuperación híbrida BM25 + semántica "
            "sobre una tarea de ContextBench."
        )
    )

    parser.add_argument(
        "task_id",
        help="original_inst_id de la tarea de ContextBench",
    )

    return parser.parse_args()


def chunk_to_text(chunk: Chunk) -> str:
    """
    Misma representación utilizada por BM25.
    """
    return (
        f"{chunk.file_path}\n"
        f"{chunk.symbol}\n"
        f"{chunk.code}"
    )


def tokenize(text: str) -> list[str]:
    """
    Misma tokenización utilizada por BM25.
    """
    return re.findall(
        r"[A-Za-z0-9_]+",
        text.lower(),
    )


def print_evaluation(
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
    repo_root,
) -> None:
    """
    Evalúa el ranking híbrido para K=5, 10 y 20.
    """
    print("\n=== EVALUACIÓN HÍBRIDA ===")

    print(
        f"{'K':<5}"
        f"{'Nivel':<10}"
        f"{'Coverage':>12}"
        f"{'Precision':>12}"
        f"{'F1':>10}"
    )

    print("-" * 49)

    for k in EVALUATION_K_VALUES:
        metrics = evaluate_retrieval(
            predicted_chunks=ranked_chunks[:k],
            gold_context=gold_context,
            repo_root=repo_root,
        )

        for level in ("file", "line"):
            values = metrics[level]

            print(
                f"{k:<5}"
                f"{level:<10}"
                f"{values['coverage']:>12.4f}"
                f"{values['precision']:>12.4f}"
                f"{values['f1']:>10.4f}"
            )


def main() -> None:
    args = parse_args()

    print(
        "=== RECUPERACIÓN HÍBRIDA "
        "BM25 + SEMÁNTICA ==="
    )

    # 1. Cargar dinámicamente la tarea.
    task = load_task(args.task_id)

    repository = task["repo"]
    base_commit = task["base_commit"]
    query = task["problem_statement"]
    gold_context = json.loads(task["gold_context"])

    # 2. Preparar el repositorio en el commit exacto.
    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    print(f"\nTarea: {task['original_inst_id']}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {base_commit}")
    print(f"Ruta local: {repo_root}")

    # 3. Crear una única colección de chunks.
    # BM25 y UniXcoder trabajan sobre exactamente
    # las mismas unidades de recuperación.
    print("\nConstruyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks)}")

    # -------------------------------------------------
    # BM25
    # -------------------------------------------------

    print("\nGenerando ranking BM25...")

    documents = [
        tokenize(chunk_to_text(chunk))
        for chunk in chunks
    ]

    bm25 = BM25Okapi(documents)

    query_tokens = tokenize(query)

    bm25_scores = bm25.get_scores(
        query_tokens
    )

    bm25_ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: bm25_scores[index],
        reverse=True,
    )

    bm25_chunks = [
        chunks[index]
        for index in bm25_ranked_indices[:FUSION_DEPTH]
    ]

    print(
        f"Resultados BM25 para fusión: "
        f"{len(bm25_chunks)}"
    )

    # -------------------------------------------------
    # SEMÁNTICO
    # -------------------------------------------------

    cache_path = semantic_cache_path(
        repository=repository,
        commit=base_commit,
    )

    print(f"\nCaché semántica: {cache_path}")

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

    semantic_chunks = [
        result.chunk
        for result in semantic_results
    ]

    print(
        f"Resultados semánticos para fusión: "
        f"{len(semantic_chunks)}"
    )

    # -------------------------------------------------
    # RRF
    # -------------------------------------------------

    hybrid_results = reciprocal_rank_fusion(
        bm25_chunks=bm25_chunks,
        semantic_chunks=semantic_chunks,
    )

    print(f"\n=== TOP {TOP_K} HÍBRIDO RRF ===")

    for rank, result in enumerate(
        hybrid_results[:TOP_K],
        start=1,
    ):
        chunk = result.chunk

        print(
            f"{rank:2}. "
            f"{chunk.file_path} | "
            f"{chunk.symbol} | "
            f"{chunk.start_line}-"
            f"{chunk.end_line} | "
            f"rrf={result.score:.6f}"
        )

    # -------------------------------------------------
    # EVALUACIÓN
    # -------------------------------------------------

    ranked_chunks = [
        result.chunk
        for result in hybrid_results[:TOP_K]
    ]

    print_evaluation(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()