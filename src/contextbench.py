from datasets import load_dataset


DATASET_NAME = "Contextbench/ContextBench"


def load_task(task_id: str) -> dict:
    """
    Carga una tarea concreta de ContextBench a partir de su original_inst_id.
    """
    dataset = load_dataset(DATASET_NAME)
    tasks = dataset["train"]

    matches = tasks.filter(
        lambda task: task["original_inst_id"] == task_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Esperábamos encontrar exactamente una tarea para "
            f"{task_id}, pero encontramos {len(matches)}"
        )

    return matches[0]