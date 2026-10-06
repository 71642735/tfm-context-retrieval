import json
import re
import sys
from pathlib import Path

from datasets import load_dataset
from rank_bm25 import BM25Okapi


# ContextBench debe estar disponible antes de importar
# nuestro módulo de evaluación.
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
from src.evaluation.retrieval_metrics import (
    evaluate_retrieval,
)
from src.retrieval.hybrid import (
    reciprocal_rank_fusion,
)
from src.retrieval.semantic import (
    SemanticRetriever,
)


DATASET_NAME = "Contextbench/ContextBench"
TASK_ID = "astropy__astropy-12907"

REPOSITORY = "astropy/astropy"
REPO_ROOT = Path("repos/astropy")
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"

CACHE_PATH = Path(
    "cache/astropy-d16bfe05-semantic.pt"
)

FUSION_DEPTH = 100
EVALUATION_K_VALUES = (5, 10, 20)


def chunk_to_text(chunk: Chunk) -> str:
    """
    Misma representación utilizada en BM25.
    """
    return (
        f"{chunk.file_path}\n"
        f"{chunk.symbol}\n"
        f"{chunk.code}"
    )


def tokenize(text: str) -> list[str]:
    """
    Misma tokenización utilizada en BM25.
    """
    return re.findall(
        r"[A-Za-z0-9_]+",
        text.lower(),
    )


def main() -> None:
    print("=== EVALUACIÓN HÍBRIDA RRF ===")

    # -------------------------------------------------
    # 1. Tarea y gold de ContextBench
    # -------------------------------------------------

    dataset = load_dataset(
        DATASET_NAME,
        split="train",
    )

    task = next(
        item
        for item in dataset
        if item["original_inst_id"] == TASK_ID
    )

    query = task["problem_statement"]
    gold_context = json.loads(
        task["gold_context"]
    )

    # -------------------------------------------------
    # 2. Corpus común
    # -------------------------------------------------

    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks: {len(chunks)}")

    # -------------------------------------------------
    # 3. Ranking BM25
    # -------------------------------------------------

    print("Generando ranking BM25...")

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

    # -------------------------------------------------
    # 4. Ranking semántico
    # -------------------------------------------------

    semantic_retriever = SemanticRetriever()

    print("Cargando índice semántico...")

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

    # -------------------------------------------------
    # 5. Fusión RRF
    # -------------------------------------------------

    hybrid_results = reciprocal_rank_fusion(
        bm25_chunks=bm25_chunks,
        semantic_chunks=semantic_chunks,
    )

    ranked_chunks = [
        result.chunk
        for result in hybrid_results
    ]

    # -------------------------------------------------
    # 6. Evaluación
    # -------------------------------------------------

    print("\n=== EVALUACIÓN HÍBRIDA RRF ===")

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
            repo_root=REPO_ROOT,
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


if __name__ == "__main__":
    main()