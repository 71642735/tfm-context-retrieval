from pathlib import Path

from datasets import load_dataset

from src.chunking import chunk_python_repository
from src.retrieval.semantic import SemanticRetriever


REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"
TASK_ID = "astropy__astropy-12907"

CACHE_PATH = Path(
    "cache/astropy-d16bfe05-semantic.pt"
)


def main() -> None:
    print("=== RECUPERACIÓN SEMÁNTICA ===")

    # 1. Cargamos el issue real de ContextBench.
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

    # 2. Generamos exactamente los mismos chunks
    # utilizados para construir el índice.
    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks: {len(chunks)}")

    # 3. Cargamos UniXcoder.
    retriever = SemanticRetriever()

    # 4. Cargamos los embeddings ya calculados.
    print("\nCargando índice semántico...")

    embeddings = retriever.load_embeddings(
        path=CACHE_PATH,
        repository=REPOSITORY,
        commit=COMMIT,
        expected_num_chunks=len(chunks),
    )

    print(f"Índice cargado: {embeddings.shape}")

    # 5. Generamos únicamente el embedding del issue
    # y lo comparamos con todo el corpus.
    print("\nRealizando búsqueda...")

    results = retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=20,
    )

    # 6. Mostramos el ranking.
    print("\n=== TOP 20 SEMÁNTICO ===")

    for rank, result in enumerate(results, start=1):
        chunk = result.chunk

        print(
            f"{rank:2}. "
            f"{chunk.file_path} | "
            f"{chunk.symbol} | "
            f"{chunk.start_line}-{chunk.end_line} | "
            f"score={result.score:.4f}"
        )


if __name__ == "__main__":
    main()