import json
import re
import argparse

from rank_bm25 import BM25Okapi

from src.chunking import Chunk, chunk_python_repository
from src.contextbench import load_task
from src.evaluation.retrieval_metrics import evaluate_retrieval
from src.repo_manager import prepare_repository


TOP_K = 20
EVALUATION_K_VALUES = (5, 10, 20)


def chunk_to_text(chunk: Chunk) -> str:
    """
    Convierte un chunk en el texto que será indexado por BM25.

    Incluimos:
    - ruta del fichero
    - nombre del símbolo
    - código fuente
    """
    return (
        f"{chunk.file_path}\n"
        f"{chunk.symbol}\n"
        f"{chunk.code}"
    )


def tokenize(text: str) -> list[str]:
    """
    Tokenización léxica sencilla y reproducible.
    """
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def print_evaluation(
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
    repo_root,
) -> None:
    """
    Evalúa BM25 para distintos valores de K
    a nivel de fichero y línea.
    """
    print("\n=== EVALUACIÓN BM25 ===")

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

def parse_args():
    """
    Lee los argumentos recibidos desde la línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description="Ejecuta BM25 sobre una tarea de ContextBench."
    )

    parser.add_argument(
        "task_id",
        help="original_inst_id de la tarea de ContextBench",
    )

    return parser.parse_args()

def main():
    # 1. Cargar la tarea de ContextBench.
    args = parse_args()
    task = load_task(args.task_id)  

    query = task["problem_statement"]
    gold_context = json.loads(task["gold_context"])

    repository = task["repo"]

    # 2. Preparar automáticamente el repositorio
    #    en el base_commit indicado por ContextBench.
    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=task["base_commit"],
    )

    print(f"\nTarea: {task['original_inst_id']}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {task['base_commit']}")
    print(f"Ruta local: {repo_root}")

    # 3. Construir los mismos chunks que utilizará BM25.
    print("\nConstruyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks indexados: {len(chunks)}")

    # 4. Construir el corpus léxico para BM25.
    documents = [
        tokenize(chunk_to_text(chunk))
        for chunk in chunks
    ]

    print("Construyendo índice BM25...")

    bm25 = BM25Okapi(documents)

    # 5. Recuperar chunks utilizando únicamente
    #    el problem_statement como consulta.
    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)

    ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: scores[index],
        reverse=True,
    )

    ranked_chunks = [
        chunks[index]
        for index in ranked_indices
    ]

    print(f"\n=== BM25 TOP-{TOP_K} ===")

    for rank, index in enumerate(
        ranked_indices[:TOP_K],
        start=1,
    ):
        chunk = chunks[index]

        print(
            f"{rank:2}. "
            f"score={scores[index]:.4f} | "
            f"{chunk.file_path}:"
            f"{chunk.start_line}-{chunk.end_line} | "
            f"{chunk.symbol}"
        )

    # 6. El gold_context aparece únicamente aquí,
    #    después de haber realizado la recuperación.
    print_evaluation(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()