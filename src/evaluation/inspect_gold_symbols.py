import json
from pathlib import Path

from datasets import load_dataset

from contextbench.extractors import extract_def_set_in_spans
from contextbench.parsers.gold import Gold


DATASET_NAME = "Contextbench/ContextBench"
TARGET_TASK = "astropy__astropy-12907"
REPO_ROOT = Path("repos/astropy")


def main() -> None:
    dataset = load_dataset(DATASET_NAME)
    tasks = dataset["train"]

    matches = tasks.filter(
        lambda task: task["original_inst_id"] == TARGET_TASK
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one task, found {len(matches)}"
        )

    task = matches[0]

    gold_context = json.loads(task["gold_context"])

    gold = Gold(
        {
            "original_inst_id": task["original_inst_id"],
            "gold_ctx": gold_context,
        }
    )

    gold_spans = gold.byte_spans(str(REPO_ROOT))

    gold_symbols = extract_def_set_in_spans(
        gold_spans,
        str(REPO_ROOT),
    )

    print("=== GOLD SYMBOLS ===")

    for file_path, kind, start_byte, end_byte in sorted(gold_symbols):
        print(
            f"{file_path} | "
            f"{kind} | "
            f"bytes {start_byte}-{end_byte}"
        )

    print()
    print(f"Total gold symbols: {len(gold_symbols)}")


if __name__ == "__main__":
    main()