import json
from pathlib import Path

from google import genai
from google.genai import types

from src.chunking import chunk_python_repository
from src.contextbench import load_task
from src.repo_manager import prepare_repository
from src.retrieval.bm25 import rank_bm25


TASK_ID = "pytest-dev__pytest-5809"
RETRIEVAL_METHOD = "bm25"
TOP_K = 10
MODEL = "gemini-3.5-flash-lite"
MAX_OUTPUT_TOKENS = 4096
THINKING_LEVEL = "minimal"

OUTPUT_DIR = (
    Path("logs")
    / "downstream"
    / TASK_ID
    / RETRIEVAL_METHOD
)


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

    # Creamos la carpeta de esta ejecución.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Guardamos exactamente el prompt que enviaremos al LLM.
    prompt_path = OUTPUT_DIR / "prompt.txt"
    prompt_path.write_text(
        prompt,
        encoding="utf-8",
    )

    print(
        f"Generando patch con {MODEL} "
        f"para {TASK_ID} usando "
        f"{RETRIEVAL_METHOD.upper()} Top-{TOP_K}..."
    )

    client = genai.Client()

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(
                thinking_level=THINKING_LEVEL,
            ),
        ),
    )

    patch = response.text

    if not patch or not patch.strip():
        raise RuntimeError(
            "Gemini no devolvió contenido de texto."
        )

    # Guardamos exactamente el patch generado.
    patch_path = OUTPUT_DIR / "patch.diff"
    patch_path.write_text(
        patch.strip() + "\n",
        encoding="utf-8",
    )

    usage = response.usage_metadata

    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    thinking_tokens = usage.thoughts_token_count or 0
    total_tokens = usage.total_token_count or 0

    # Metadatos de la generación.
    result = {
        "task_id": TASK_ID,
        "repository": repository,
        "base_commit": base_commit,
        "retrieval_method": RETRIEVAL_METHOD,
        "k": TOP_K,
        "model": MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "thinking_level": THINKING_LEVEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "total_tokens": total_tokens,
    }

    result_path = OUTPUT_DIR / "result.json"
    result_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=== USO DE TOKENS ===")
    print(f"Input:    {input_tokens}")
    print(f"Output:   {output_tokens}")
    print(f"Thinking: {thinking_tokens}")
    print(f"Total:    {total_tokens}")

    print()
    print("=== ARTEFACTOS ===")
    print(f"Prompt:    {prompt_path}")
    print(f"Patch:     {patch_path}")
    print(f"Resultado: {result_path}")

    print()
    print("=== PATCH GENERADO ===")
    print(patch)


if __name__ == "__main__":
    main()