import re
from pathlib import Path

from datasets import load_dataset
from rank_bm25 import BM25Okapi

from src.chunking import Chunk, chunk_python_repository


DATASET_NAME = "Contextbench/ContextBench"
TARGET_TASK = "astropy__astropy-12907"

REPOSITORY = "astropy/astropy"
REPO_ROOT = Path("repos/astropy")

TOP_K = 20


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


def main():
    # 1. Cargar la tarea
    task = load_task()

    # La consulta de recuperación es exclusivamente
    # el problem_statement de ContextBench.
    query = task["problem_statement"]

    # 2. Construir el corpus
    print("Construyendo corpus de chunks...")

    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks indexados: {len(chunks)}")

    # 3. Preparar los documentos para BM25
    documents = [
        tokenize(chunk_to_text(chunk))
        for chunk in chunks
    ]

    # 4. Construir BM25
    print("Construyendo índice BM25...")

    bm25 = BM25Okapi(documents)

    # 5. Tokenizar la consulta
    query_tokens = tokenize(query)

    # 6. Calcular puntuaciones BM25
    scores = bm25.get_scores(query_tokens)

    # 7. Obtener los TOP-K chunks
    ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: scores[index],
        reverse=True,
    )[:TOP_K]

    # 8. Mostrar ranking
    print(f"\n=== BM25 TOP-{TOP_K} ===")

    for rank, index in enumerate(ranked_indices, start=1):
        chunk = chunks[index]

        print(
            f"{rank:2}. "
            f"score={scores[index]:.4f} | "
            f"{chunk.file_path}:"
            f"{chunk.start_line}-{chunk.end_line} | "
            f"{chunk.symbol}"
        )


if __name__ == "__main__":
    main()