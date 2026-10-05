from pathlib import Path

from datasets import load_dataset

from src.chunking import chunk_python_repository
from src.retrieval.semantic import SemanticRetriever


REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
COMMIT = "d16bfe05a744909de4b27f5875fe0d4ed41ce607"
TASK_ID = "astropy__astropy-12907"

CACHE_PATH = Path("cache/astropy-test-100.pt")


# 1. Cargamos el issue real de ContextBench.
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


# 2. Generamos los chunks reales de Astropy.
chunks = chunk_python_repository(
    repository=REPOSITORY,
    repo_root=REPO_ROOT,
)

sample_chunks = chunks[:100]

print(f"Chunks totales: {len(chunks)}")
print(f"Chunks usados en la prueba: {len(sample_chunks)}")


# 3. Cargamos UniXcoder.
retriever = SemanticRetriever()


# 4. Generamos los embeddings.
print("\nGenerando embeddings...")

embeddings = retriever.index(
    sample_chunks,
    batch_size=8,
)

print(f"Shape generada: {embeddings.shape}")


# 5. Guardamos embeddings + metadatos.
retriever.save_embeddings(
    embeddings=embeddings,
    path=CACHE_PATH,
    repository=REPOSITORY,
    commit=COMMIT,
)

print(f"Embeddings guardados en: {CACHE_PATH}")


# 6. Cargamos la caché validando sus metadatos.
loaded_embeddings = retriever.load_embeddings(
    path=CACHE_PATH,
    repository=REPOSITORY,
    commit=COMMIT,
    expected_num_chunks=len(sample_chunks),
)

print(f"Shape cargada: {loaded_embeddings.shape}")
print("Metadatos de caché validados correctamente.")


# 7. Hacemos la búsqueda con los embeddings cargados.
results = retriever.search(
    query=query,
    chunks=sample_chunks,
    chunk_embeddings=loaded_embeddings,
    top_k=10,
)


print("\n=== TOP 10 SEMÁNTICO DESDE CACHÉ ===")

for rank, result in enumerate(results, start=1):
    chunk = result.chunk

    print(
        f"{rank:2}. "
        f"{chunk.file_path} | "
        f"{chunk.symbol} | "
        f"{chunk.start_line}-{chunk.end_line} | "
        f"score={result.score:.4f}"
    )