import json

from datasets import load_dataset


DATASET_NAME = "Contextbench/ContextBench"
TARGET_TASK = "astropy__astropy-12907"


# Cargar ContextBench
dataset = load_dataset(DATASET_NAME)
tasks = dataset["train"]

# Localizar la tarea seleccionada para el piloto
matches = tasks.filter(
    lambda task: task["original_inst_id"] == TARGET_TASK
)

if len(matches) != 1:
    raise RuntimeError(
        f"Esperábamos encontrar exactamente una tarea, "
        f"pero encontramos {len(matches)}"
    )

task = matches[0]

# ContextBench almacena gold_context como una cadena JSON
gold_context = json.loads(task["gold_context"])


# Salida resumida para documentar el experimento
print("\n=== TAREA CONTEXTBENCH SELECCIONADA ===")
print(f"original_inst_id : {task['original_inst_id']}")
print(f"instance_id      : {task['instance_id']}")
print(f"repo             : {task['repo']}")
print(f"repo_url         : {task['repo_url']}")
print(f"language         : {task['language']}")
print(f"base_commit      : {task['base_commit']}")

print("\n=== GOLD CONTEXT ===")

for span in gold_context:
    print(
        f"{span['file']}  "
        f"[líneas {span['start_line']}-{span['end_line']}]"
    )