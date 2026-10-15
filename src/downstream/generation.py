import json
import time

from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import errors, types

from src.chunking import Chunk
from src.downstream.retrieval import (
    TOP_K,
    RetrievalContext,
    retrieve_context,
)
from src.retrieval.semantic import SemanticRetriever


MODEL = "gemini-3.5-flash-lite"
MAX_OUTPUT_TOKENS = 4096
THINKING_LEVEL = "minimal"

OUTPUT_ROOT = Path("logs") / "downstream"

MAX_API_ATTEMPTS = 3
RETRYABLE_API_CODES = {429, 503}



@dataclass
class GenerationResult:
    task_id: str
    retrieval_method: str
    prompt_path: Path
    patch_path: Path
    result_path: Path
    patch: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int


def build_prompt(
    problem_statement: str,
    retrieved_chunks: list[Chunk],
) -> str:
    """
    Construye el prompt fijo utilizado en la evaluación downstream.
    """
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


def build_prompt_from_context(
    context: RetrievalContext,
) -> str:
    """
    Construye el prompt a partir del contexto recuperado.
    """
    return build_prompt(
        problem_statement=context.problem_statement,
        retrieved_chunks=context.chunks,
    )

def generate_with_retry(
    client: genai.Client,
    prompt: str,
):
    """
    Realiza una única generación experimental.

    Los errores temporales 429 y 503 pueden reintentarse porque
    no han producido una generación evaluable.

    Una vez obtenida una respuesta del modelo, no se vuelve a
    generar aunque posteriormente el patch resulte inválido.
    """
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=THINKING_LEVEL,
                    ),
                ),
            )

        except errors.APIError as exc:
            retryable = exc.code in RETRYABLE_API_CODES
            last_attempt = attempt == MAX_API_ATTEMPTS

            if not retryable or last_attempt:
                raise

            wait_seconds = 10 * attempt

            print(
                f"Gemini devolvió HTTP {exc.code}. "
                f"Reintentando en {wait_seconds} s "
                f"({attempt}/{MAX_API_ATTEMPTS})..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Se alcanzó un estado inesperado durante la generación."
    )

def generate_from_context(
    context: RetrievalContext,
) -> GenerationResult:
    """
    Envía al LLM el contexto ya recuperado y conserva
    los artefactos y metadatos de la generación.
    """
    prompt = build_prompt_from_context(context)

    output_dir = (
        OUTPUT_ROOT
        / context.task_id
        / context.method
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(
        prompt,
        encoding="utf-8",
    )

    print(
        f"Generando patch con {MODEL} "
        f"para {context.task_id} usando "
        f"{context.method.upper()} Top-{TOP_K}..."
    )

    client = genai.Client()

    response = generate_with_retry(
        client=client,
        prompt=prompt,
    )

    patch = response.text

    if not patch or not patch.strip():
        raise RuntimeError(
            "Gemini no devolvió contenido de texto."
        )

    patch = patch.strip() + "\n"

    patch_path = output_dir / "patch.diff"
    patch_path.write_text(
        patch,
        encoding="utf-8",
    )

    usage = response.usage_metadata

    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    thinking_tokens = usage.thoughts_token_count or 0
    total_tokens = usage.total_token_count or 0

    result = {
        "task_id": context.task_id,
        "repository": context.repository,
        "base_commit": context.base_commit,
        "retrieval_method": context.method,
        "k": TOP_K,
        "model": MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "thinking_level": THINKING_LEVEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "total_tokens": total_tokens,
    }

    result_path = output_dir / "result.json"
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

    return GenerationResult(
        task_id=context.task_id,
        retrieval_method=context.method,
        prompt_path=prompt_path,
        patch_path=patch_path,
        result_path=result_path,
        patch=patch,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        total_tokens=total_tokens,
    )


def generate_patch(
    task_id: str,
    retrieval_method: str,
    semantic_retriever: SemanticRetriever | None = None,
) -> GenerationResult:
    """
    Ejecuta retrieval y una única generación para una condición.
    """
    context = retrieve_context(
        task_id=task_id,
        method=retrieval_method,
        semantic_retriever=semantic_retriever,
    )

    return generate_from_context(context)