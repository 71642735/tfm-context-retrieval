from pathlib import Path

from google import genai

from src.chunking import chunk_python_repository
from src.contextbench import load_task
from src.repo_manager import prepare_repository
from src.retrieval.bm25 import rank_bm25


TASK_ID = "pytest-dev__pytest-5809"
TOP_K = 10
MODEL = "gemini-3.5-flash-lite"

OUTPUT_PATH = Path("pilot-bm25.patch")


def build_prompt(
    problem_statement: str,
    retrieved_chunks,
) -> str:
    context_parts = []

    for rank, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(
            "\n".join(
                [
                    f"--- Chunk {rank} ---",
                    f"File: {chunk.file_path}",
                    f"Lines: {chunk.start_line}-{chunk.end_line}",
                    f"Symbol: {chunk.symbol}",
                    "",
                    chunk.code,
                ]
            )
        )

    retrieved_context = "\n\n".join(context_parts)

    return f"""You are fixing an issue in a Python repository.

ISSUE:
{problem_statement}

RETRIEVED CONTEXT:
{retrieved_context}

INSTRUCTIONS:
- Use only the issue description and the retrieved context above.
- Do not assume access to any other repository files.
- Produce the minimal code change needed to resolve the issue.
- Return only a unified diff patch.
- Do not use Markdown code fences.
- Do not include explanations before or after the patch.
"""


def main() -> None:
    task = load_task(TASK_ID)

    repository = task["repo"]
    base_commit = task["base_commit"]
    problem_statement = task["problem_statement"]

    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    ranked_chunks, _, _ = rank_bm25(
        chunks=chunks,
        query=problem_statement,
    )

    retrieved_chunks = ranked_chunks[:TOP_K]

    prompt = build_prompt(
        problem_statement=problem_statement,
        retrieved_chunks=retrieved_chunks,
    )

    print(
        f"Generando patch con {MODEL} "
        f"para {TASK_ID} usando BM25 Top-{TOP_K}..."
    )

    client = genai.Client()

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    patch = response.text

    if not patch or not patch.strip():
        raise RuntimeError(
            "Gemini no devolvió contenido de texto."
        )

    OUTPUT_PATH.write_text(
        patch.strip() + "\n",
        encoding="utf-8",
    )

    print(f"Patch guardado en: {OUTPUT_PATH}")
    print()
    print("=== PATCH GENERADO ===")
    print(patch)


if __name__ == "__main__":
    main()