import random
from collections import defaultdict

from datasets import load_dataset


DATASET_NAME = "Contextbench/ContextBench"
SEED = 42
NUM_REPOSITORIES = 5


def main():
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

    # Generador pseudoaleatorio con semilla fija.
    rng = random.Random(SEED)

    # Ordenamos antes de seleccionar para que el resultado no dependa
    # del orden en el que ContextBench devuelva los repositorios.
    repositories = sorted(tasks_by_repo.keys())

    selected_repositories = rng.sample(
        repositories,
        NUM_REPOSITORIES,
    )

    # Seleccionar una tarea reproducible de cada repositorio.
    selected_tasks = []

    for repository in selected_repositories:
        repository_tasks = sorted(
            tasks_by_repo[repository],
            key=lambda task: task["original_inst_id"],
        )

        selected_task = rng.choice(repository_tasks)
        selected_tasks.append(selected_task)

    # Mostrar la selección.
    print("=== MINI-PILOTO ===")
    print(f"Seed: {SEED}")
    print(f"Tareas Python disponibles: {len(python_tasks)}")
    print(f"Repositorios Python disponibles: {len(repositories)}")
    print()

    for index, task in enumerate(selected_tasks, start=1):
        print(f"{index}. {task['original_inst_id']}")
        print(f"   Repo: {task['repo']}")
        print(f"   Commit: {task['base_commit']}")
        print()


if __name__ == "__main__":
    main()