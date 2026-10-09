import time

from src.chunking import chunk_python_repository
from src.repo_manager import prepare_repository
from src.retrieval.semantic import (
    SemanticRetriever,
    semantic_cache_path,
)


REPOSITORY = "scikit-learn/scikit-learn"
REPO_URL = "https://github.com/scikit-learn/scikit-learn.git"
BASE_COMMIT = "586f4318ffcdfbd9a1093f35ad43e81983740b66"
BATCH_SIZE = 8

TOTAL_PENDING_CHUNKS = 567_285


def format_duration(seconds: float) -> str:
    hours = seconds / 3600

    if hours >= 1:
        return f"{hours:.2f} horas"

    minutes = seconds / 60
    return f"{minutes:.2f} minutos"


def main() -> None:
    print("=== BENCHMARK UNICODEXER ===")
    print(f"Repositorio: {REPOSITORY}")
    print(f"Commit: {BASE_COMMIT}")
    print(f"Batch size: {BATCH_SIZE}")
    print()

    repo_root = prepare_repository(
        repository=REPOSITORY,
        repo_url=REPO_URL,
        base_commit=BASE_COMMIT,
    )

    print("\nGenerando chunks...")

    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks):,}")

    cache_path = semantic_cache_path(
        REPOSITORY,
        BASE_COMMIT,
    )

    if cache_path.exists():
        raise RuntimeError(
            f"La caché ya existe: {cache_path}\n"
            "Este benchmark necesita un estado sin caché "
            "para medir el tiempo real de generación."
        )

    print(f"Caché: {cache_path}")
    print()
    print("Cargando UniXcoder...")

    retriever = SemanticRetriever()

    print()
    print("=== INICIO DEL CRONÓMETRO ===")

    start_time = time.perf_counter()

    embeddings = retriever.load_or_build_embeddings(
        chunks=chunks,
        path=cache_path,
        repository=REPOSITORY,
        commit=BASE_COMMIT,
        batch_size=BATCH_SIZE,
    )

    elapsed_seconds = time.perf_counter() - start_time

    chunks_per_second = len(chunks) / elapsed_seconds
    chunks_per_minute = chunks_per_second * 60

    estimated_total_seconds = (
        TOTAL_PENDING_CHUNKS / chunks_per_second
    )

    remaining_after_benchmark = max(
        TOTAL_PENDING_CHUNKS - len(chunks),
        0,
    )

    estimated_remaining_seconds = (
        remaining_after_benchmark / chunks_per_second
    )

    print()
    print("=== RESULTADO DEL BENCHMARK ===")
    print(f"Embeddings generados: {len(embeddings):,}")
    print(
        f"Tiempo: {elapsed_seconds:.2f} segundos "
        f"({format_duration(elapsed_seconds)})"
    )
    print(
        f"Velocidad: {chunks_per_second:.2f} chunks/segundo"
    )
    print(
        f"Velocidad: {chunks_per_minute:.2f} chunks/minuto"
    )

    print()
    print("=== PROYECCIÓN ===")
    print(
        f"Chunks pendientes iniciales: "
        f"{TOTAL_PENDING_CHUNKS:,}"
    )
    print(
        f"Tiempo estimado para todos: "
        f"{format_duration(estimated_total_seconds)}"
    )
    print(
        f"Chunks restantes después del benchmark: "
        f"{remaining_after_benchmark:,}"
    )
    print(
        f"Tiempo restante estimado: "
        f"{format_duration(estimated_remaining_seconds)}"
    )


if __name__ == "__main__":
    main()