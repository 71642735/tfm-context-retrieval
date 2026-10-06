import re
import sys
from pathlib import Path

from datasets import load_dataset
from rank_bm25 import BM25Okapi


# ContextBench es necesario indirectamente al importar
# algunos módulos de evaluación utilizados por bm25.py.
CONTEXTBENCH_ROOT = Path(
    "external/ContextBench"
).resolve()

sys.path.insert(
    0,
    str(CONTEXTBENCH_ROOT),
)


from src.chunking import (
    Chunk,
    chunk_python_repository,
)
from src.retrieval.hybrid import (
    reciprocal_rank_fusion,
)
from src.retrieval.semantic import (
    SemanticRetriever,
)


REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"
TASK_ID = "astropy__astropy-12907"

CACHE_PATH = Path(
    "cache/astropy-d16bfe05-semantic.pt"
)

FUSION_DEPTH = 100
TOP_K = 20


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


def main() -> None:
    print(
        "=== RECUPERACIÓN HÍBRIDA "
        "BM25 + SEMÁNTICA ==="
    )

    # 1. Cargamos el issue.
    dataset = load_dataset(
        "Contextbench/ContextBench",
        split="train",
    )

    task = next(
        item
        for item in dataset
        if item["original_inst_id"] == TASK_ID
    )

    query = task["problem_statement"]

    print(f"Task: {TASK_ID}")

    # 2. Mismos chunks para ambos métodos.
    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
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
        for index
        in bm25_ranked_indices[:FUSION_DEPTH]
    ]

    print(
        f"Resultados BM25 para fusión: "
        f"{len(bm25_chunks)}"
    )

    # -------------------------------------------------
    # SEMÁNTICO
    # -------------------------------------------------

    semantic_retriever = SemanticRetriever()

    print("\nCargando índice semántico...")

    embeddings = semantic_retriever.load_embeddings(
        path=CACHE_PATH,
        repository=REPOSITORY,
        commit=COMMIT,
        expected_num_chunks=len(chunks),
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

    print("\n=== TOP 20 HÍBRIDO RRF ===")

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


if __name__ == "__main__":
    main()