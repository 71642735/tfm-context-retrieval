import argparse
import json

from src.chunking import chunk_python_repository
from src.contextbench import load_task
from src.repo_manager import prepare_repository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    args = parser.parse_args()

    task = load_task(args.task_id)

    repository = task["repo"]
    base_commit = task["base_commit"]

    repo_root = prepare_repository(
        repository=repository,
        repo_url=task["repo_url"],
        base_commit=base_commit,
    )

    print()
    print("=== COBERTURA MÁXIMA DEL GOLD ===")
    print(f"Tarea: {args.task_id}")
    print(f"Repositorio: {repository}")
    print(f"Base commit: {base_commit}")
    print()

    print("Construyendo corpus de chunks...")
    chunks = chunk_python_repository(
        repository=repository,
        repo_root=repo_root,
    )

    print(f"Chunks: {len(chunks)}")
    print()

    gold_context = json.loads(task["gold_context"])

    total_gold_lines = set()
    covered_gold_lines = set()

    print("=== GOLD CONTEXT ===")

    for gold in gold_context:
        file_path = gold["file"]
        start_line = gold["start_line"]
        end_line = gold["end_line"]

        gold_lines = {
            (file_path, line)
            for line in range(start_line, end_line + 1)
        }

        total_gold_lines.update(gold_lines)

        matching_chunks = [
            chunk
            for chunk in chunks
            if chunk.file_path == file_path
            and chunk.end_line >= start_line
            and chunk.start_line <= end_line
        ]

        span_covered_lines = set()

        for chunk in matching_chunks:
            overlap_start = max(start_line, chunk.start_line)
            overlap_end = min(end_line, chunk.end_line)

            for line in range(overlap_start, overlap_end + 1):
                span_covered_lines.add((file_path, line))

        covered_gold_lines.update(span_covered_lines)

        print(
            f"{file_path}:{start_line}-{end_line}"
            f" -> chunks={len(matching_chunks)}"
            f" -> líneas cubiertas={len(span_covered_lines)}/{len(gold_lines)}"
        )

    print()
    print("=== RESUMEN ===")

    total = len(total_gold_lines)
    covered = len(covered_gold_lines)

    coverage = covered / total if total else 0.0

    gold_files = {
        file_path
        for file_path, _ in total_gold_lines
    }

    chunk_files = {
        chunk.file_path
        for chunk in chunks
    }

    covered_files = gold_files & chunk_files

    print(f"Ficheros gold: {len(gold_files)}")
    print(
        f"Ficheros gold presentes en corpus: "
        f"{len(covered_files)}/{len(gold_files)}"
    )
    print(f"Líneas gold distintas: {total}")
    print(f"Líneas gold cubiertas por algún chunk: {covered}")
    print(f"Cobertura máxima posible: {coverage:.4f}")


if __name__ == "__main__":
    main()