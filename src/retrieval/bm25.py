import json
import re
from pathlib import Path

from datasets import load_dataset
from rank_bm25 import BM25Okapi

from src.chunking import Chunk, chunk_python_repository
from src.evaluation.retrieval_metrics import evaluate_retrieval


DATASET_NAME = "Contextbench/ContextBench"
TARGET_TASK = "astropy__astropy-12907"

REPOSITORY = "astropy/astropy"
REPO_ROOT = Path("repos/astropy")

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


def load_task():
    """
    Carga de ContextBench la tarea seleccionada para el piloto.
    """
    dataset = load_dataset(DATASET_NAME)
    tasks = dataset["train"]

    matches = tasks.filter(
        lambda task: task["original_inst_id"] == TARGET_TASK
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Esperábamos encontrar exactamente una tarea, "
            f"pero encontramos {len(matches)}"
        )

    return matches[0]


def print_evaluation(
    ranked_chunks: list[Chunk],
    gold_context: list[dict],
) -> None:
    """
    Evalúa BM25 para distintos valores de K
    a nivel de fichero, símbolo y línea.
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


def main():
    task = load_task()
    query = task["problem_statement"]
    gold_context = json.loads(task["gold_context"])

    print("Construyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks indexados: {len(chunks)}")

    documents = [
        tokenize(chunk_to_text(chunk))
        for chunk in chunks
    ]

    print("Construyendo índice BM25...")

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

    print_evaluation(
        ranked_chunks=ranked_chunks,
        gold_context=gold_context,
    )


if __name__ == "__main__":
    main()