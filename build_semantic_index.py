from pathlib import Path

from src.chunking import chunk_python_repository
from src.retrieval.semantic import SemanticRetriever


REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"

CACHE_PATH = Path(
    "cache/astropy-d16bfe05-semantic.pt"
)


def main() -> None:
    print("=== GENERACIÓN DEL ÍNDICE SEMÁNTICO ===")
    print(f"Repositorio: {REPOSITORY}")
    print(f"Commit: {COMMIT}")

    # 1. Generamos exactamente los mismos chunks
    # que utilizamos en BM25.
    print("\nGenerando chunks...")

    chunks = chunk_python_repository(
        repository=REPOSITORY,
        repo_root=REPO_ROOT,
    )

    print(f"Chunks encontrados: {len(chunks)}")

    # 2. Cargamos UniXcoder.
    retriever = SemanticRetriever()

    # 3. Generamos un embedding para cada chunk.
    print("\nGenerando embeddings del corpus...")
    print("Este proceso puede tardar aproximadamente 2 horas.\n")

    embeddings = retriever.index(
        chunks,
        batch_size=8,
    )

    print("\nEmbeddings generados.")
    print(f"Shape: {embeddings.shape}")

    # 4. Guardamos embeddings + metadatos.
    retriever.save_embeddings(
        embeddings=embeddings,
        path=CACHE_PATH,
        repository=REPOSITORY,
        commit=COMMIT,
    )

    print(f"\nÍndice guardado en: {CACHE_PATH}")
    print("=== ÍNDICE SEMÁNTICO COMPLETADO ===")


if __name__ == "__main__":
    main()