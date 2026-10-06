from dataclasses import dataclass

from src.chunking import Chunk


RRF_K = 60


@dataclass
class HybridResult:
    chunk: Chunk
    score: float


def chunk_key(
    chunk: Chunk,
) -> tuple[str, str, int, int]:
    """
    Identifica de forma única un chunk dentro del repositorio.
    """
    return (
        chunk.file_path,
        chunk.symbol,
        chunk.start_line,
        chunk.end_line,
    )


def reciprocal_rank_fusion(
    bm25_chunks: list[Chunk],
    semantic_chunks: list[Chunk],
    rrf_k: int = RRF_K,
) -> list[HybridResult]:
    """
    Fusiona un ranking BM25 y un ranking semántico
    mediante Reciprocal Rank Fusion (RRF).

    Ambos rankings contienen objetos Chunk ordenados
    de mayor a menor relevancia.
    """

    scores: dict[
        tuple[str, str, int, int],
        float,
    ] = {}

    chunks: dict[
        tuple[str, str, int, int],
        Chunk,
    ] = {}

    # Contribución del ranking BM25.
    for rank, chunk in enumerate(
        bm25_chunks,
        start=1,
    ):
        key = chunk_key(chunk)

        chunks[key] = chunk

        scores[key] = scores.get(
            key,
            0.0,
        ) + 1.0 / (rrf_k + rank)

    # Contribución del ranking semántico.
    for rank, chunk in enumerate(
        semantic_chunks,
        start=1,
    ):
        key = chunk_key(chunk)

        chunks[key] = chunk

        scores[key] = scores.get(
            key,
            0.0,
        ) + 1.0 / (rrf_k + rank)

    ranked_keys = sorted(
        scores,
        key=scores.get,
        reverse=True,
    )

    return [
        HybridResult(
            chunk=chunks[key],
            score=scores[key],
        )
        for key in ranked_keys
    ]