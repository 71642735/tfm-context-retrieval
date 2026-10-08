from src.chunking import chunk_python_repository
from src.contextbench import load_task
from src.repo_manager import prepare_repository
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


TASK_ID = "django__django-12663"


def main() -> None:
    task = load_task(TASK_ID)

    repo_path = prepare_repository(
        repository=task["repo"],
        repo_url=task["repo_url"],
        base_commit=task["base_commit"],
    )

    chunks = chunk_python_repository(
        repository=task["repo"],
        repo_root=repo_path,
    )

    retriever = SemanticRetriever()

    cache_path = semantic_cache_path(
        task["repo"],
        task["base_commit"],
    )

    embeddings = retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=task["repo"],
        commit=task["base_commit"],
        batch_size=8,
    )

    # Elegimos un chunk aproximadamente en mitad del corpus,
    # para no seleccionar manualmente uno "favorable".
    target_index = len(chunks) // 2
    target_chunk = chunks[target_index]

    # Utilizamos exactamente la misma representación textual
    # que usamos al construir los embeddings del corpus.
    query = (
        f"{target_chunk.file_path}\n"
        f"{target_chunk.symbol}\n"
        f"{target_chunk.code}"
    )

    results = retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=10,
    )

    print("\nChunk utilizado como consulta:")
    print(f"Index: {target_index}")
    print(f"File: {target_chunk.file_path}")
    print(f"Symbol: {target_chunk.symbol}")
    print(
        f"Lines: "
        f"{target_chunk.start_line}-{target_chunk.end_line}"
    )

    print("\nTop-10 recuperación semántica:")

    target_rank = None

    for rank, result in enumerate(results, start=1):
        chunk = result.chunk

        is_target = (
            chunk.file_path == target_chunk.file_path
            and chunk.symbol == target_chunk.symbol
            and chunk.start_line == target_chunk.start_line
            and chunk.end_line == target_chunk.end_line
        )

        marker = " <-- TARGET" if is_target else ""

        print(
            f"{rank:>2}. "
            f"score={result.score:.6f} "
            f"{chunk.file_path} "
            f"{chunk.symbol} "
            f"{chunk.start_line}-{chunk.end_line}"
            f"{marker}"
        )

        if is_target:
            target_rank = rank

    print("\nResultado del sanity check:")

    if target_rank is None:
        print("TARGET NO APARECE EN TOP-10")
    else:
        print(f"TARGET recuperado en rank={target_rank}")


if __name__ == "__main__":
    main()