import time

import torch
from transformers import AutoModel, AutoTokenizer

from src.chunking import chunk_python_repository

from pathlib import Path

MODEL_NAME = "microsoft/unixcoder-base"
REPO_ROOT = Path("repos/astropy")
REPOSITORY = "astropy/astropy"
NUM_CHUNKS = 100
BATCH_SIZE = 8


def chunk_to_text(chunk) -> str:
    return f"{chunk.file_path}\n{chunk.symbol}\n{chunk.code}"


print("Generando chunks...")
chunks = chunk_python_repository(REPOSITORY, REPO_ROOT)

sample = chunks[:NUM_CHUNKS]

print(f"Chunks totales: {len(chunks)}")
print(f"Chunks usados en benchmark: {len(sample)}")

print("Cargando tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

print("Cargando modelo...")
model = AutoModel.from_pretrained(MODEL_NAME)
model.eval()

texts = [chunk_to_text(chunk) for chunk in sample]

print("Generando embeddings...")
start = time.perf_counter()

all_embeddings = []

for start_idx in range(0, len(texts), BATCH_SIZE):
    batch = texts[start_idx:start_idx + BATCH_SIZE]

    inputs = tokenizer(
        batch,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = model(**inputs)

    mask = inputs["attention_mask"].unsqueeze(-1)

    embeddings = (outputs.last_hidden_state * mask).sum(dim=1)
    embeddings = embeddings / mask.sum(dim=1)

    embeddings = torch.nn.functional.normalize(
        embeddings,
        p=2,
        dim=1,
    )

    all_embeddings.append(embeddings.cpu())

elapsed = time.perf_counter() - start

embeddings = torch.cat(all_embeddings)

print()
print("=== BENCHMARK EMBEDDINGS ===")
print(f"Chunks procesados: {len(sample)}")
print(f"Dimensión embedding: {embeddings.shape[1]}")
print(f"Tiempo total: {elapsed:.2f} s")
print(f"Tiempo por chunk: {elapsed / len(sample):.3f} s")

estimated = elapsed / len(sample) * len(chunks)

print(
    f"Estimación corpus completo ({len(chunks)} chunks): "
    f"{estimated / 60:.1f} min"
)