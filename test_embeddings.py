import torch
from transformers import AutoTokenizer, AutoModel

MODEL_NAME = "microsoft/unixcoder-base"

print("Cargando tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

print("Cargando modelo...")
model = AutoModel.from_pretrained(MODEL_NAME)

texts = [
    "how to implement quick sort in Python?",
    """
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + [pivot] + quick_sort(right)
""",
    """
def bubble_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr) - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
""",
]

inputs = tokenizer(
    texts,
    padding=True,
    truncation=True,
    max_length=512,
    return_tensors="pt",
)

with torch.no_grad():
    outputs = model(**inputs)

# Creamos un vector por texto haciendo la media
# de los embeddings de sus tokens.
mask = inputs["attention_mask"].unsqueeze(-1)
embeddings = (outputs.last_hidden_state * mask).sum(dim=1)
embeddings = embeddings / mask.sum(dim=1)

# Normalizamos para poder comparar con producto escalar,
# equivalente aquí a similitud coseno.
embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

quick_similarity = torch.dot(embeddings[0], embeddings[1]).item()
bubble_similarity = torch.dot(embeddings[0], embeddings[2]).item()

print("Similitud con quick_sort:", quick_similarity)
print("Similitud con bubble_sort:", bubble_similarity)