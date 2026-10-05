import torch

from src.retrieval.semantic import SemanticRetriever


retriever = SemanticRetriever()

texts = [
    "calculate the separability matrix of a compound model",
    "def _separable(transform): return transform",
]

embeddings = retriever.encode(texts)

print("Shape:", embeddings.shape)
print("Similitud:", torch.matmul(embeddings[0], embeddings[1]).item())