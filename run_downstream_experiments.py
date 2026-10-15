import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.downstream.evaluation import (
    EvaluationResult,
    evaluate_patch,
)
from src.downstream.generation import (
    GenerationResult,
    generate_patch,
)
from src.retrieval.semantic import SemanticRetriever


TASKS_PATH = Path("results") / "final_tasks.csv"
RESULTS_PATH = Path("results") / "downstream_results.jsonl"

RETRIEVAL_METHODS = (
    "bm25",
    "semantic",
    "hybrid",
)

FINAL_STATUSES = {
    "resolved",
    "not_resolved",
    "invalid_patch",
}


@dataclass
class GenerationMetadata:
    """
    Metadatos necesarios cuando reutilizamos una generación
    existente sin volver a llamar al LLM.
    """
    prompt_path: Path
    result_path: Path
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int


def load_task_ids() -> list[str]:
    """
    Carga exactamente las tareas de la muestra final congelada.
    """
    with TASKS_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        task_ids = [
            row["original_inst_id"]
            for row in reader
        ]

    if len(task_ids) != 50:
        raise RuntimeError(
            "Se esperaban exactamente 50 tareas "
            f"congeladas, pero se encontraron {len(task_ids)}."
        )

    if len(set(task_ids)) != len(task_ids):
        raise RuntimeError(
            "La muestra final contiene task IDs duplicados."
        )

    return task_ids


def load_latest_results() -> dict[tuple[str, str], dict]:
    """
    Lee los resultados existentes.

    Si una condición aparece varias veces por reintentos de
    infraestructura, conserva el último registro.
    """
    latest = {}

    if not RESULTS_PATH.exists():
        return latest

    with RESULTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            result = json.loads(line)

            key = (
                result["task_id"],
                result["retrieval_method"],
            )

            latest[key] = result

    return latest


def is_final_result(
    result: dict | None,
) -> bool:
    """
    Indica si una condición ya tiene un resultado experimental
    definitivo y, por tanto, no debe repetirse.
    """
    if result is None:
        return False

    return result.get("status") in FINAL_STATUSES


def load_existing_generation(
    task_id: str,
    retrieval_method: str,
) -> GenerationMetadata | None:
    """
    Recupera los metadatos de una generación ya realizada.

    Solo se considera reutilizable si existen tanto el patch
    como el result.json de la generación.
    """
    output_dir = (
        Path("logs")
        / "downstream"
        / task_id
        / retrieval_method
    )

    prompt_path = output_dir / "prompt.txt"
    patch_path = output_dir / "patch.diff"
    result_path = output_dir / "result.json"

    if not patch_path.exists() or not result_path.exists():
        return None

    with result_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return GenerationMetadata(
        prompt_path=prompt_path,
        result_path=result_path,
        input_tokens=int(data.get("input_tokens", 0)),
        output_tokens=int(data.get("output_tokens", 0)),
        thinking_tokens=int(data.get("thinking_tokens", 0)),
        total_tokens=int(data.get("total_tokens", 0)),
    )


def append_result(
    generation: GenerationResult | GenerationMetadata | None,
    evaluation: EvaluationResult,
) -> None:
    """
    Guarda inmediatamente un resultado en formato JSON Lines.

    JSONL permite añadir una condición por línea sin reescribir
    todo el fichero.
    """
    RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "task_id": evaluation.task_id,
        "retrieval_method": evaluation.retrieval_method,
        "status": evaluation.status,
        "resolved": evaluation.resolved,
        "infrastructure_failure": (
            evaluation.infrastructure_failure
        ),
        "detail": evaluation.detail,
        "patch_path": str(evaluation.patch_path),
    }

    if generation is not None:
        record.update(
            {
                "input_tokens": generation.input_tokens,
                "output_tokens": generation.output_tokens,
                "thinking_tokens": generation.thinking_tokens,
                "total_tokens": generation.total_tokens,
                "prompt_path": str(generation.prompt_path),
                "generation_result_path": str(
                    generation.result_path
                ),
            }
        )

    with RESULTS_PATH.open(
        "a",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


def build_infrastructure_result(
    task_id: str,
    retrieval_method: str,
    detail: str,
) -> EvaluationResult:
    """
    Construye un resultado de infraestructura para fallos que
    ocurren antes de que evaluate_patch() pueda devolver uno.
    """
    patch_path = (
        Path("logs")
        / "downstream"
        / task_id
        / retrieval_method
        / "patch.diff"
    )

    return EvaluationResult(
        task_id=task_id,
        retrieval_method=retrieval_method,
        status="infrastructure_error",
        resolved=None,
        patch_path=patch_path,
        infrastructure_failure=True,
        detail=detail,
    )


def run_condition(
    task_id: str,
    retrieval_method: str,
    semantic_retriever: SemanticRetriever | None,
) -> EvaluationResult:
    """
    Ejecuta una condición downstream preservando Pass@1.

    Si ya existe una generación válida de un intento anterior,
    reutiliza exactamente ese patch y reintenta únicamente la
    evaluación.
    """
    output_dir = (
        Path("logs")
        / "downstream"
        / task_id
        / retrieval_method
    )

    patch_path = output_dir / "patch.diff"

    generation = None

    try:
        existing_generation = load_existing_generation(
            task_id=task_id,
            retrieval_method=retrieval_method,
        )

        if existing_generation is not None:
            generation = existing_generation

            print(
                "Generación existente detectada. "
                "Se reutiliza el patch para preservar Pass@1."
            )

            evaluation = evaluate_patch(
                task_id=task_id,
                patch_path=patch_path,
                retrieval_method=retrieval_method,
            )

        else:
            generation = generate_patch(
                task_id=task_id,
                retrieval_method=retrieval_method,
                semantic_retriever=semantic_retriever,
            )

            evaluation = evaluate_patch(
                task_id=task_id,
                patch_path=generation.patch_path,
                retrieval_method=retrieval_method,
            )

    except Exception as exc:
        evaluation = build_infrastructure_result(
            task_id=task_id,
            retrieval_method=retrieval_method,
            detail=(
                f"{type(exc).__name__}: {exc}"
            ),
        )

        print()
        print(
            "Estado: infrastructure_error "
            f"({evaluation.detail})"
        )

    append_result(
        generation=generation,
        evaluation=evaluation,
    )

    return evaluation

def parse_args() -> argparse.Namespace:
    """
    Argumentos operativos del ejecutor.

    --limit permite validar el orquestador ejecutando únicamente
    un número limitado de condiciones. No modifica la muestra
    experimental ni el protocolo definitivo.
    """
    parser = argparse.ArgumentParser(
        description="Ejecuta el experimento downstream."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Número máximo de condiciones a recorrer. "
            "Uso exclusivo para pruebas del orquestador."
        ),
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser mayor que cero.")

    return args
    
def main() -> None:
    args = parse_args()
    """
    Ejecuta las 150 condiciones downstream de forma reanudable.
    """
    if not sys.flags.utf8_mode:
        raise RuntimeError(
            "La evaluación downstream requiere Python en "
            "modo UTF-8. Ejecuta el script con:\n"
            "python -X utf8 run_downstream_experiments.py"
        )

    task_ids = load_task_ids()
    previous_results = load_latest_results()

    total_conditions = (
        len(task_ids) * len(RETRIEVAL_METHODS)
    )

    print("=== EXPERIMENTO DOWNSTREAM ===")
    print(f"Tareas:       {len(task_ids)}")
    print(
        "Métodos:      "
        + ", ".join(RETRIEVAL_METHODS)
    )
    print(f"Condiciones:  {total_conditions}")
    print(f"Resultados:   {RESULTS_PATH}")

    semantic_retriever = SemanticRetriever()

    condition_number = 0
    completed = 0

    for task_id in task_ids:
        if (
            args.limit is not None
            and condition_number >= args.limit
        ):
            break         
        for retrieval_method in RETRIEVAL_METHODS:
            if (
                args.limit is not None
                and condition_number >= args.limit
            ):
                break

            condition_number += 1

            key = (
                task_id,
                retrieval_method,
            )

            previous = previous_results.get(key)

            print()
            print("=" * 70)
            print(
                f"CONDICIÓN "
                f"{condition_number}/{total_conditions}"
            )
            print(f"Tarea:  {task_id}")
            print(f"Método: {retrieval_method}")
            print("=" * 70)

            if is_final_result(previous):
                completed += 1

                print(
                    "Omitida: ya existe resultado "
                    f"definitivo ({previous['status']})."
                )
                continue

            evaluation = run_condition(
                task_id=task_id,
                retrieval_method=retrieval_method,
                semantic_retriever=semantic_retriever,
            )

            if evaluation.status in FINAL_STATUSES:
                completed += 1

            print()
            print(
                "Resultado de la condición: "
                f"{evaluation.status}"
            )

    print()
    print("=== RESUMEN DE EJECUCIÓN ===")
    print(
        f"Condiciones definitivas: "
        f"{completed}/{total_conditions}"
    )

    if completed == total_conditions:
        print(
            "Experimento downstream completo."
        )
    else:
        print(
            "Quedan condiciones sin resultado definitivo. "
            "Puede ejecutarse de nuevo el mismo script para "
            "reintentar únicamente los fallos de infraestructura."
        )


if __name__ == "__main__":
    main()