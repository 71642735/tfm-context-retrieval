import json

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

    gold_context = json.loads(task["gold_context"])

    gold_files = {
        entry["file"]
        for entry in gold_context
    }

    print(f"Tarea: {TASK_ID}")
    print(f"Chunks: {len(chunks)}")
    print(f"Ficheros gold: {sorted(gold_files)}")

    retriever = SemanticRetriever()

    cache_path = semantic_cache_path(
        task["repo"],
        task["base_commit"],
    )

    print(f"Caché semántica: {cache_path}")

    embeddings = retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=task["repo"],
        commit=task["base_commit"],
        batch_size=8,
    )

    results = retriever.search(
        query=task["problem_statement"],
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=len(chunks),
    )

    print("\nPrimera aparición de cada fichero gold:")

    for gold_file in sorted(gold_files):
        first_result = None
        first_rank = None

        for rank, result in enumerate(results, start=1):
            if result.chunk.file_path == gold_file:
                first_rank = rank
                first_result = result
                break

        if first_result is None:
            print(f"{gold_file}: NO APARECE")
        else:
            print(
                f"{gold_file}: "
                f"rank={first_rank}, "
                f"score={first_result.score:.6f}, "
                f"symbol={first_result.chunk.symbol}, "
                f"lines={first_result.chunk.start_line}-"
                f"{first_result.chunk.end_line}"
            )


if __name__ == "__main__":
    main()