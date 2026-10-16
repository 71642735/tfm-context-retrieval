import argparse
import json
from pathlib import Path

from datasets import load_dataset
from poly_bench_evaluation.run_evaluation import evaluate_predictions


POLYBENCH_DATASET = "AmazonScience/SWE-PolyBench"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--patch-path", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    instance_id = args.instance_id
    patch_path = Path(args.patch_path).resolve()
    work_dir = Path(args.work_dir).resolve()

    work_dir.mkdir(parents=True, exist_ok=True)

    dataset_csv = work_dir / "dataset.csv"
    predictions_jsonl = work_dir / "predictions.jsonl"
    results_dir = work_dir / "results"
    repos_dir = work_dir / "repos"

    results_dir.mkdir(parents=True, exist_ok=True)
    repos_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(POLYBENCH_DATASET, split="test")

    matches = dataset.filter(
        lambda row: row["instance_id"] == instance_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one PolyBench instance for {instance_id}, "
            f"found {len(matches)}"
        )

    matches.to_pandas().to_csv(dataset_csv, index=False)

    patch = patch_path.read_text(encoding="utf-8")

    with predictions_jsonl.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "model_patch": patch,
                }
            )
            + "\n"
        )

    print(f"[polybench] instance_id={instance_id}")
    print(f"[polybench] dataset={dataset_csv}")
    print(f"[polybench] prediction={predictions_jsonl}")

    evaluate_predictions(
        dataset_path=str(dataset_csv),
        predictions_path=str(predictions_jsonl),
        result_path=str(results_dir),
        num_threads=1,
        evaluate_gold=False,
        repo_path=str(repos_dir),
        delete_image=False,
        skip_existing=False,
    )

    result_file = results_dir / f"{instance_id}_result.json"

    if not result_file.exists():
        raise RuntimeError(
            f"PolyBench did not produce expected result: {result_file}"
        )

    result = json.loads(result_file.read_text(encoding="utf-8"))

    print(
        "TFM_POLYBENCH_RESULT="
        + json.dumps(
            {
                "instance_id": instance_id,
                "resolved": bool(result["resolved"]),
                "result_file": str(result_file),
            }
        )
    )


if __name__ == "__main__":
    main()