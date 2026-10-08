import argparse
import json

from src.chunking import chunk_python_repository
from src.contextbench import load_task
from src.evaluation.retrieval_metrics import evaluate_retrieval
from src.repo_manager import prepare_repository
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


TOP_K = 20
EVALUATION_K_VALUES = (5, 10, 20)


def parse_args():
    """
    Lee la tarea de ContextBench desde la línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta recuperación semántica "
            "sobre una tarea de ContextBench."
        )
    )

    parser.add_argument(
        "task_id",
        help="original_inst_id de la tarea de ContextBench",
    )

    return parser.parse_args()


def print_evaluation(
    ranked_chunks,
    gold_context: list[dict],
    repo_root,
) -> None:
    """
    Evalúa la recuperación semántica para distintos valores de K
    a nivel de fichero y línea.
    """
    print("\n=== EVALUACIÓN SEMÁNTICA ===")

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

    print("=== RECUPERACIÓN SEMÁNTICA ===")

    # 1. Cargar la tarea de ContextBench.
    task = load_task(args.task_id)

    repository = task["repo"]
    base_commit = task["base_commit"]
    query = task["problem_statement"]
    gold_context = json.loads(task["gold_context"])

    # 2. Preparar automáticamente el repositorio
    # en el commit exacto indicado por ContextBench.
    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    print(f"\nTarea: {task['original_inst_id']}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {base_commit}")
    print(f"Ruta local: {repo_root}")

    # 3. Generar exactamente los mismos chunks
    # utilizados por las demás estrategias.
    print("\nConstruyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks)}")

    # 4. Determinar la caché correspondiente
    # al repositorio y commit.
    cache_path = semantic_cache_path(
        repository=repository,
        commit=base_commit,
    )

    print(f"Caché semántica: {cache_path}")

    # 5. Cargar UniXcoder.
    retriever = SemanticRetriever()

    # 6. Cargar el índice si existe o construirlo
    # automáticamente si todavía no existe.
    embeddings = retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=repository,
        commit=base_commit,
        batch_size=8,
    )

    print(f"Índice disponible: {embeddings.shape}")

    # 7. Generar el embedding del issue y realizar
    # la recuperación semántica.
    print("\nRealizando búsqueda...")

    results = retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=TOP_K,
    )

    # 8. Mostrar el ranking.
    print(f"\n=== TOP {TOP_K} SEMÁNTICO ===")

    for rank, result in enumerate(results, start=1):
        chunk = result.chunk

        print(
            f"{rank:2}. "
            f"{chunk.file_path} | "
            f"{chunk.symbol} | "
            f"{chunk.start_line}-{chunk.end_line} | "
            f"score={result.score:.4f}"
        )

    # 9. Evaluar el ranking utilizando el gold únicamente
    # después de haber realizado la recuperación.
    ranked_chunks = [
        result.chunk
        for result in results
    ]

    print_evaluation(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()