import json
import sys
from pathlib import Path

# ContextBench está clonado en external/ContextBench,
# pero no está instalado como paquete en el entorno.
# Añadimos su raíz al path de Python antes de importarlo.
CONTEXTBENCH_ROOT = Path("external/ContextBench").resolve()

sys.path.insert(
    0,
    str(CONTEXTBENCH_ROOT),
)

from datasets import load_dataset

from src.chunking import chunk_python_repository
from src.evaluation.retrieval_metrics import evaluate_retrieval
from src.retrieval.semantic import SemanticRetriever


REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"
TASK_ID = "astropy__astropy-12907"

CACHE_PATH = Path(
    "cache/astropy-d16bfe05-semantic.pt"
)

TOP_K_VALUES = [5, 10, 20]


def main() -> None:
    print("=== EVALUACIÓN RECUPERACIÓN SEMÁNTICA ===")

    # 1. Cargamos la tarea piloto de ContextBench.
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
    gold_context = json.loads(task["gold_context"])

    print(f"Task: {TASK_ID}")

    # 2. Generamos exactamente los mismos chunks
    # utilizados por BM25 y por el índice semántico.
    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks: {len(chunks)}")

    # 3. Cargamos UniXcoder y el índice ya generado.
    retriever = SemanticRetriever()

    print("\nCargando índice semántico...")

    embeddings = retriever.load_embeddings(
        path=CACHE_PATH,
        repository=REPOSITORY,
        commit=COMMIT,
        expected_num_chunks=len(chunks),
    )

    print(f"Índice cargado: {embeddings.shape}")

    # 4. Recuperamos una sola vez el Top-20.
    #
    # Top-5 y Top-10 son simplemente prefijos de este ranking,
    # por lo que no necesitamos repetir la búsqueda.
    results = retriever.search(
        query=query,
        chunks=chunks,
        chunk_embeddings=embeddings,
        top_k=max(TOP_K_VALUES),
    )

    print("\n=== EVALUACIÓN SEMÁNTICA ===")
    print(
        f"{'K':<5}"
        f"{'Nivel':<12}"
        f"{'Coverage':>10}"
        f"{'Precision':>12}"
        f"{'F1':>10}"
    )
    print("-" * 49)

    # 5. Evaluamos exactamente los mismos K que en BM25.
    for k in TOP_K_VALUES:
        retrieved_chunks = [
            result.chunk
            for result in results[:k]
        ]

        metrics = evaluate_retrieval(
            predicted_chunks=retrieved_chunks,
            gold_context=gold_context,
        )

        for level in ("file", "line"):
            level_metrics = metrics[level]

            print(
                f"{k:<5}"
                f"{level:<12}"
                f"{level_metrics['coverage']:>10.4f}"
                f"{level_metrics['precision']:>12.4f}"
                f"{level_metrics['f1']:>10.4f}"
            )


if __name__ == "__main__":
    main()