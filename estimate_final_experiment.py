import csv
from pathlib import Path

from src.chunking import chunk_python_repository
from src.repo_manager import prepare_repository
from src.retrieval.semantic import semantic_cache_path


TASKS_FILE = Path("results/final_tasks.csv")
OUTPUT_FILE = Path("results/final_experiment_estimate.csv")


def main() -> None:
    with TASKS_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        tasks = list(csv.DictReader(file))

    print("=== ESTIMACIÓN DEL EXPERIMENTO FINAL ===")
    print(f"Tareas: {len(tasks)}")
    print()

    results = []

    total_chunks = 0
    cached_chunks = 0
    pending_chunks = 0
    cached_states = 0
    pending_states = 0

    for index, task in enumerate(tasks, start=1):
        task_id = task["original_inst_id"]
        repository = task["repo"]
        repo_url = task["repo_url"]
        base_commit = task["base_commit"]

        print("=" * 70)
        print(f"[{index}/{len(tasks)}] {task_id}")
        print(f"Repo: {repository}")
        print(f"Commit: {base_commit[:12]}")

        repo_root = prepare_repository(
            repository=repository,
            repo_url=repo_url,
            base_commit=base_commit,
        )

        print("Generando chunks...")

        chunks = chunk_python_repository(
            repository=repository,
            repo_root=repo_root,
        )

        num_chunks = len(chunks)

        cache_path = semantic_cache_path(
            repository,
            base_commit,
        )

        cache_exists = cache_path.exists()

        total_chunks += num_chunks

        if cache_exists:
            cached_states += 1
            cached_chunks += num_chunks
        else:
            pending_states += 1
            pending_chunks += num_chunks

        results.append(
            {
                "task_id": task_id,
                "repo": repository,
                "base_commit": base_commit,
                "num_chunks": num_chunks,
                "semantic_cache": str(cache_exists),
                "cache_path": str(cache_path),
            }
        )

        print(f"Chunks: {num_chunks:,}")
        print(
            "Caché semántica: "
            + ("SÍ" if cache_exists else "NO")
        )
        print()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        fieldnames = [
            "task_id",
            "repo",
            "base_commit",
            "num_chunks",
            "semantic_cache",
            "cache_path",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    print()
    print("=== RESUMEN ===")
    print(f"Tareas analizadas: {len(results)}")
    print(f"Estados repo+commit: {len(results)}")
    print(f"Estados con caché: {cached_states}")
    print(f"Estados pendientes: {pending_states}")
    print(f"Chunks totales: {total_chunks:,}")
    print(f"Chunks ya cacheados: {cached_chunks:,}")
    print(f"Chunks pendientes: {pending_chunks:,}")
    print()
    print(
        f"Detalle guardado en: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()