from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from src.chunking import Chunk


MODEL_NAME = "microsoft/unixcoder-base"
ENCODING_MODE = "encoder-only"
MAX_LENGTH = 512


def semantic_cache_path(
    repository: str,
    commit: str,
) -> Path:
    repository_name = repository.replace("/", "__")

    return Path("cache") / (
        f"{repository_name}-{commit[:8]}-semantic.pt"
    )


def chunk_to_text(chunk: Chunk) -> str:
    return f"{chunk.file_path}\n{chunk.symbol}\n{chunk.code}"


@dataclass
class SemanticResult:
    chunk: Chunk
    score: float


class SemanticRetriever:
    def __init__(self) -> None:
        print(f"Cargando modelo semántico: {MODEL_NAME}")

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModel.from_pretrained(MODEL_NAME)
        self.model.eval()

    def encode(
        self,
        texts: list[str],
        batch_size: int = 8,
    ) -> torch.Tensor:
        all_embeddings = []

        for start_idx in range(0, len(texts), batch_size):
            batch = texts[start_idx:start_idx + batch_size]

            encoded_texts = []

            for text in batch:
                tokens = self.tokenizer.tokenize(text)

                # Reservamos 4 posiciones para:
                # [CLS] <encoder-only> [SEP] ... [SEP]
                tokens = tokens[: MAX_LENGTH - 4]

                tokens = [
                    self.tokenizer.cls_token,
                    f"<{ENCODING_MODE}>",
                    self.tokenizer.sep_token,
                ] + tokens + [
                    self.tokenizer.sep_token
                ]

                token_ids = self.tokenizer.convert_tokens_to_ids(tokens)
                encoded_texts.append(token_ids)

            max_length = max(len(ids) for ids in encoded_texts)

            padded_texts = [
                ids
                + [self.tokenizer.pad_token_id]
                * (max_length - len(ids))
                for ids in encoded_texts
            ]

            input_ids = torch.tensor(padded_texts)

            attention_mask = input_ids.ne(
                self.tokenizer.pad_token_id
            )

            with torch.no_grad():
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                )

            embeddings = (
                outputs.last_hidden_state
                * attention_mask.unsqueeze(-1)
            ).sum(dim=1)

            embeddings = embeddings / attention_mask.sum(
                dim=1
            ).unsqueeze(-1)

            embeddings = torch.nn.functional.normalize(
                embeddings,
                p=2,
                dim=1,
            )

            all_embeddings.append(embeddings.cpu())

            processed = min(
                start_idx + batch_size,
                len(texts),
            )

            if processed % 800 == 0 or processed == len(texts):
                print(
                    f"Embeddings procesados: "
                    f"{processed}/{len(texts)}"
                )

        return torch.cat(all_embeddings)

    def index(
        self,
        chunks: list[Chunk],
        batch_size: int = 8,
    ) -> torch.Tensor:
        chunk_texts = [
            chunk_to_text(chunk)
            for chunk in chunks
        ]

        return self.encode(
            chunk_texts,
            batch_size=batch_size,
        )

    def save_embeddings(
        self,
        embeddings: torch.Tensor,
        path: Path,
        repository: str,
        commit: str,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_data = {
            "repository": repository,
            "commit": commit,
            "model": MODEL_NAME,
            "encoding": ENCODING_MODE,
            "max_length": MAX_LENGTH,
            "num_chunks": len(embeddings),
            "embeddings": embeddings,
        }

        torch.save(cache_data, path)

    def load_embeddings(
        self,
        path: Path,
        repository: str,
        commit: str,
        expected_num_chunks: int,
    ) -> torch.Tensor:
        cache_data = torch.load(
            path,
            map_location="cpu",
            weights_only=True,
        )

        if cache_data["repository"] != repository:
            raise ValueError(
                "La caché pertenece a otro repositorio."
            )

        if cache_data["commit"] != commit:
            raise ValueError(
                "La caché pertenece a otro commit."
            )

        if cache_data["model"] != MODEL_NAME:
            raise ValueError(
                "La caché fue generada con otro modelo."
            )

        if cache_data["encoding"] != ENCODING_MODE:
            raise ValueError(
                "La caché utiliza otra estrategia de encoding."
            )

        if cache_data["max_length"] != MAX_LENGTH:
            raise ValueError(
                "La caché utiliza otra longitud máxima."
            )

        if cache_data["num_chunks"] != expected_num_chunks:
            raise ValueError(
                "La caché no contiene el número esperado de chunks."
            )

        return cache_data["embeddings"]

    def load_or_build_embeddings(
        self,
        chunks: list[Chunk],
        path: Path,
        repository: str,
        commit: str,
        batch_size: int = 8,
    ) -> torch.Tensor:
        """
        Carga los embeddings desde caché si existen.

        Si todavía no existe una caché para el repositorio y commit
        indicados, genera los embeddings y los guarda.
        """
        if path.exists():
            print(f"Cargando índice semántico desde: {path}")

            return self.load_embeddings(
                path=path,
                repository=repository,
                commit=commit,
                expected_num_chunks=len(chunks),
            )

        print("No existe índice semántico en caché.")
        print("Generando embeddings del corpus...")

        embeddings = self.index(
            chunks,
            batch_size=batch_size,
        )

        self.save_embeddings(
            embeddings=embeddings,
            path=path,
            repository=repository,
            commit=commit,
        )

        print(f"Índice semántico guardado en: {path}")

        return embeddings

    def search(
        self,
        query: str,
        chunks: list[Chunk],
        chunk_embeddings: torch.Tensor,
        top_k: int = 20,
    ) -> list[SemanticResult]:
        if len(chunks) != len(chunk_embeddings):
            raise ValueError(
                "El número de chunks y embeddings no coincide."
            )

        query_embedding = self.encode(
            [query],
            batch_size=1,
        )[0]

        scores = torch.matmul(
            chunk_embeddings,
            query_embedding,
        )

        ranked_indices = torch.argsort(
            scores,
            descending=True,
        )[:top_k]

        return [
            SemanticResult(
                chunk=chunks[index],
                score=scores[index].item(),
            )
            for index in ranked_indices.tolist()
        ]