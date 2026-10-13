import argparse
import json
import re

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


def rank_bm25(
    chunks: list[Chunk],
    query: str,
) -> tuple[list[Chunk], list[float], list[int]]:
    """
    Ordena los chunks mediante BM25 según su relevancia
    respecto a la consulta.

    Devuelve:
    - chunks ordenados por relevancia
    - scores BM25
    - índices ordenados
    """
    documents = [
        tokenize(chunk_to_text(chunk))
        for chunk in chunks
    ]

    bm25 = BM25Okapi(documents)

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

    return ranked_chunks, scores.tolist(), ranked_indices

def evaluate_at_k(
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
    repo_root,
) -> list[dict]:
    """
    Evalúa un ranking para los valores de K configurados.

    Devuelve una fila por cada combinación de:
    - K
    - nivel de evaluación (file/line)
    """
    results = []

    for k in EVALUATION_K_VALUES:
        metrics = evaluate_retrieval(
            predicted_chunks=ranked_chunks[:k],
            gold_context=gold_context,
            repo_root=repo_root,
        )

        for level in ("file", "line"):
            values = metrics[level]

            results.append(
                {
                    "k": k,
                    "level": level,
                    "coverage": values["coverage"],
                    "precision": values["precision"],
                    "f1": values["f1"],
                }
            )

    return results


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

    results = evaluate_at_k(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
        repo_root=repo_root,
    )

    for result in results:
        print(
            f"{result['k']:<5}"
            f"{result['level']:<10}"
            f"{result['coverage']:>12.4f}"
            f"{result['precision']:>12.4f}"
            f"{result['f1']:>10.4f}"
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

    # 4. Recuperar chunks mediante BM25 utilizando únicamente
    #    el problem_statement como consulta.
    print("Construyendo índice BM25...")

    ranked_chunks, scores, ranked_indices = rank_bm25(
        chunks=chunks,
        query=query,
    )

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

    # 5. El gold_context aparece únicamente aquí,
    #    después de haber realizado la recuperación.
    print_evaluation(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()