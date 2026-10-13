import argparse
import json

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
BATCH_SIZE = 8


def chunk_overlaps_gold(
    chunk: Chunk,
    gold_context: list[dict],
) -> bool:
    """
    Indica si un chunk solapa en líneas con alguna región gold
    del mismo fichero.
    """
    for gold in gold_context:
        if chunk.file_path != gold["file"]:
            continue

        gold_start = gold["start_line"]
        gold_end = gold["end_line"]

        overlaps = (
            chunk.start_line <= gold_end
            and chunk.end_line >= gold_start
        )

        if overlaps:
            return True

    return False


def print_ranking(
    method: str,
    results: list[tuple[Chunk, float]],
    gold_context: list[dict],
) -> None:
    print()
    print(f"=== {method.upper()} TOP-{TOP_K} ===")

    for rank, (chunk, score) in enumerate(
        results[:TOP_K],
        start=1,
    ):
        gold = (
            "YES"
            if chunk_overlaps_gold(chunk, gold_context)
            else "NO"
        )

        print(
            f"{rank:2}. "
            f"score={score:.6f} | "
            f"gold={gold:<3} | "
            f"{chunk.file_path}:"
            f"{chunk.start_line}-{chunk.end_line} | "
            f"{chunk.symbol}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspecciona los rankings BM25, UniXcoder y RRF "
            "para una tarea de ContextBench."
        )
    )

    parser.add_argument(
        "task_id",
        help="original_inst_id de la tarea de ContextBench",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    task = load_task(args.task_id)

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
    print(f"Tarea: {args.task_id}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {base_commit}")
    print("=" * 70)

    print("\nConstruyendo chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks):,}")

    # -------------------------------------------------
    # BM25
    # -------------------------------------------------

    print("\nReconstruyendo ranking BM25...")

    (
        bm25_ranked_chunks,
        bm25_scores,
        bm25_ranked_indices,
    ) = rank_bm25(
        chunks=chunks,
        query=query,
    )

    bm25_results = [
        (
            chunks[index],
            bm25_scores[index],
        )
        for index in bm25_ranked_indices
    ]

    # -------------------------------------------------
    # SEMÁNTICO
    # -------------------------------------------------

    print("\nCargando UniXcoder...")

    semantic_retriever = SemanticRetriever()

    cache_path = semantic_cache_path(
        repository=repository,
        commit=base_commit,
    )

    print(f"Caché semántica: {cache_path}")

    if not cache_path.exists():
        raise FileNotFoundError(
            "No existe la caché semántica esperada. "
            "Se cancela la inspección para evitar regenerar embeddings."
        )

    embeddings = semantic_retriever.load_embeddings(
        path=cache_path,
        repository=repository,
        commit=base_commit,
        expected_num_chunks=len(chunks),
    )

    print("Caché semántica cargada correctamente.")

    semantic_results_raw = semantic_retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=FUSION_DEPTH,
    )

    semantic_ranked_chunks = [
        result.chunk
        for result in semantic_results_raw
    ]

    semantic_results = [
        (
            result.chunk,
            result.score,
        )
        for result in semantic_results_raw
    ]

    # -------------------------------------------------
    # RRF
    # -------------------------------------------------

    print("\nReconstruyendo ranking RRF...")

    hybrid_results_raw = reciprocal_rank_fusion(
        bm25_chunks=bm25_ranked_chunks[:FUSION_DEPTH],
        semantic_chunks=semantic_ranked_chunks[:FUSION_DEPTH],
    )

    hybrid_results = [
        (
            result.chunk,
            result.score,
        )
        for result in hybrid_results_raw
    ]

    # -------------------------------------------------
    # MOSTRAR TOP-10
    # -------------------------------------------------

    print_ranking(
        method="BM25",
        results=bm25_results,
        gold_context=gold_context,
    )

    print_ranking(
        method="UniXcoder",
        results=semantic_results,
        gold_context=gold_context,
    )

    print_ranking(
        method="RRF",
        results=hybrid_results,
        gold_context=gold_context,
    )

    print()
    print("=== POSICIONES DE CHUNKS GOLD ===")

    methods = {
        "BM25": bm25_results[:FUSION_DEPTH],
        "UniXcoder": semantic_results[:FUSION_DEPTH],
        "RRF": hybrid_results,
    }

    gold_chunks = {}

    for method_results in methods.values():
        for chunk, _ in method_results:
            if chunk_overlaps_gold(chunk, gold_context):
                key = (
                    chunk.file_path,
                    chunk.symbol,
                    chunk.start_line,
                    chunk.end_line,
                )
                gold_chunks[key] = chunk

    for chunk in gold_chunks.values():
        print()
        print(
            f"{chunk.file_path}:"
            f"{chunk.start_line}-{chunk.end_line} | "
            f"{chunk.symbol}"
        )

        for method, method_results in methods.items():
            rank = next(
                (
                    index
                    for index, (candidate, _) in enumerate(
                        method_results,
                        start=1,
                    )
                    if (
                        candidate.file_path == chunk.file_path
                        and candidate.symbol == chunk.symbol
                        and candidate.start_line == chunk.start_line
                        and candidate.end_line == chunk.end_line
                    )
                ),
                None,
            )

            rank_text = str(rank) if rank is not None else ">100"
            print(f"  {method:<10}: rank {rank_text}")


if __name__ == "__main__":
    main()