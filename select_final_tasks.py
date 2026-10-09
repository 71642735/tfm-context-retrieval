import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset


DATASET_NAME = "Contextbench/ContextBench"
SEED = 42
TARGET_TASKS = 50
MAX_TASKS_PER_REPO = 5

OUTPUT_DIR = Path("results")
OUTPUT_FILE = OUTPUT_DIR / "final_tasks.csv"


def main() -> None:
    # Cargar ContextBench.
    dataset = load_dataset(DATASET_NAME)["train"]

    # Quedarnos únicamente con tareas Python.
    python_tasks = [
        task
        for task in dataset
        if task["language"].lower() == "python"
    ]

    # Agrupar las tareas por repositorio.
    tasks_by_repo = defaultdict(list)

    for task in python_tasks:
        tasks_by_repo[task["repo"]].append(task)

    # Orden estable antes de aplicar aleatoriedad.
    for repository in tasks_by_repo:
        tasks_by_repo[repository] = sorted(
            tasks_by_repo[repository],
            key=lambda task: task["original_inst_id"],
        )

    repositories = sorted(tasks_by_repo.keys())

    rng = random.Random(SEED)

    # Barajamos reproduciblemente las tareas dentro de cada repositorio.
    shuffled_tasks_by_repo = {}

    for repository in repositories:
        repository_tasks = tasks_by_repo[repository].copy()
        rng.shuffle(repository_tasks)
        shuffled_tasks_by_repo[repository] = repository_tasks

    # También barajamos reproduciblemente el orden de los repositorios.
    repository_order = repositories.copy()
    rng.shuffle(repository_order)

    selected_tasks = []

    # Selección por rondas:
    # primera tarea de cada repo, después segunda, etc.
    for round_index in range(MAX_TASKS_PER_REPO):
        for repository in repository_order:
            repository_tasks = shuffled_tasks_by_repo[repository]

            if round_index >= len(repository_tasks):
                continue

            selected_tasks.append(
                repository_tasks[round_index]
            )

            if len(selected_tasks) == TARGET_TASKS:
                break

        if len(selected_tasks) == TARGET_TASKS:
            break

    if len(selected_tasks) != TARGET_TASKS:
        raise RuntimeError(
            f"No se pudieron seleccionar {TARGET_TASKS} tareas "
            f"con un máximo de {MAX_TASKS_PER_REPO} por repositorio. "
            f"Solo se seleccionaron {len(selected_tasks)}."
        )

    # Comprobar programáticamente el límite por repositorio.
    repo_counts = Counter(
        task["repo"]
        for task in selected_tasks
    )

    if max(repo_counts.values()) > MAX_TASKS_PER_REPO:
        raise RuntimeError(
            "La selección supera el máximo de tareas por repositorio."
        )

    # Guardar selección.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fieldnames = [
            "original_inst_id",
            "repo",
            "repo_url",
            "base_commit",
            "language",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for task in selected_tasks:
            writer.writerow(
                {
                    "original_inst_id": task["original_inst_id"],
                    "repo": task["repo"],
                    "repo_url": task["repo_url"],
                    "base_commit": task["base_commit"],
                    "language": task["language"],
                }
            )

    # Mostrar resumen.
    print("=== MUESTRA EXPERIMENTAL FINAL ===")
    print(f"Seed: {SEED}")
    print(f"Tareas objetivo: {TARGET_TASKS}")
    print(
        f"Máximo por repositorio: "
        f"{MAX_TASKS_PER_REPO}"
    )
    print(
        f"Tareas Python disponibles: "
        f"{len(python_tasks)}"
    )
    print(
        f"Repositorios Python disponibles: "
        f"{len(repositories)}"
    )
    print(
        f"Tareas seleccionadas: "
        f"{len(selected_tasks)}"
    )
    print(
        f"Repositorios representados: "
        f"{len(repo_counts)}"
    )

    print("\n=== DISTRIBUCIÓN POR REPOSITORIO ===")

    for repository, count in sorted(
        repo_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(
            f"{repository:<45} {count}"
        )

    print("\n=== TAREAS SELECCIONADAS ===")

    for index, task in enumerate(
        selected_tasks,
        start=1,
    ):
        print(
            f"{index:>2}. "
            f"{task['original_inst_id']} "
            f"[{task['repo']}]"
        )

    print(
        f"\nSelección guardada en: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()