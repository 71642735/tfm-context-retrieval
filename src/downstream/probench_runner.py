import argparse
import json
import subprocess
import sys
from pathlib import Path

from datasets import load_dataset


PROBENCH_DATASET = "ScaleAI/SWE-bench_Pro"
PROBENCH_CONFIG = "v1"

PROBENCH_ORIGINAL_LOCAL_WRITE = '''\
        with open(dst, "w") as f:
            f.write(content)
'''

PROBENCH_WINDOWS_LOCAL_WRITE = '''\
        with open(dst, "w", newline="\\n") as f:
            f.write(content)
'''


def ensure_local_workspace_lf(evaluator_path: Path) -> None:
    """
    Ensure that SWE-bench Pro writes local workspace files using LF endings.

    On Windows, the official evaluator opens workspace files in text mode
    without specifying newline behavior. Python therefore converts LF to
    CRLF before the workspace is mounted inside the Linux container.
    """
    evaluator_source = evaluator_path.read_text(encoding="utf-8")

    if PROBENCH_WINDOWS_LOCAL_WRITE in evaluator_source:
        print("[probench] LF workspace compatibility already applied")
        return

    if PROBENCH_ORIGINAL_LOCAL_WRITE not in evaluator_source:
        raise RuntimeError(
            "Could not apply SWE-bench Pro LF compatibility adaptation: "
            "expected write_files_local implementation was not found."
        )

    adapted_source = evaluator_source.replace(
        PROBENCH_ORIGINAL_LOCAL_WRITE,
        PROBENCH_WINDOWS_LOCAL_WRITE,
        1,
    )

    evaluator_path.write_text(
        adapted_source,
        encoding="utf-8",
        newline="\n",
    )

    print("[probench] applied LF workspace compatibility adaptation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--patch-path", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--probench-root", required=True)
    args = parser.parse_args()

    instance_id = args.instance_id
    patch_path = Path(args.patch_path).resolve()
    work_dir = Path(args.work_dir).resolve()
    probench_root = Path(args.probench_root).resolve()

    work_dir.mkdir(parents=True, exist_ok=True)

    dataset_csv = work_dir / "dataset.csv"
    predictions_json = work_dir / "predictions.json"
    results_dir = work_dir / "results"

    results_dir.mkdir(parents=True, exist_ok=True)

    evaluator_path = probench_root / "swe_bench_pro_eval.py"
    scripts_dir = probench_root / "run_scripts"

    if not evaluator_path.exists():
        raise RuntimeError(
            f"SWE-bench Pro evaluator not found: {evaluator_path}"
        )

    if not scripts_dir.exists():
        raise RuntimeError(
            f"SWE-bench Pro scripts directory not found: {scripts_dir}"
        )

    ensure_local_workspace_lf(evaluator_path)

    dataset = load_dataset(
        PROBENCH_DATASET,
        PROBENCH_CONFIG,
        split="test",
    )

    matches = dataset.filter(
        lambda row: row["instance_id"] == instance_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one SWE-bench Pro instance for {instance_id}, "
            f"found {len(matches)}"
        )

    matches.to_pandas().to_csv(dataset_csv, index=False)

    patch = patch_path.read_text(encoding="utf-8")

    predictions_json.write_text(
        json.dumps(
            [
                {
                    "instance_id": instance_id,
                    "patch": patch,
                    "prefix": "tfm",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[probench] instance_id={instance_id}")
    print(f"[probench] dataset={dataset_csv}")
    print(f"[probench] prediction={predictions_json}")
    print(f"[probench] evaluator={evaluator_path}")

    command = [
        sys.executable,
        str(evaluator_path.resolve()),
        "--raw_sample_path", str(dataset_csv.resolve()),
        "--patch_path", str(predictions_json.resolve()),
        "--output_dir", str(results_dir.resolve()),
        "--dockerhub_username", "jefzda",
        "--scripts_dir", str(scripts_dir.resolve()),
        "--use_local_docker",
        "--num_workers", "1",
        "--redo",
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(probench_root),
    )

    if process.stdout:
        print(process.stdout)

    if process.stderr:
        print(process.stderr, file=sys.stderr)

    if process.returncode != 0:
        raise RuntimeError(
            f"SWE-bench Pro evaluator exited with code "
            f"{process.returncode}"
        )

    combined_output = process.stdout + "\n" + process.stderr

    infrastructure_markers = (
        "generated an exception:",
        "returned None",
    )

    if any(marker in combined_output for marker in infrastructure_markers):
        raise RuntimeError(
            "SWE-bench Pro evaluator reported an infrastructure "
            "exception instead of a valid experimental result."
        )

    result_file = results_dir / "eval_results.json"

    if not result_file.exists():
        raise RuntimeError(
            f"SWE-bench Pro did not produce expected result: "
            f"{result_file}"
        )

    results = json.loads(
        result_file.read_text(encoding="utf-8")
    )

    if instance_id not in results:
        raise RuntimeError(
            f"SWE-bench Pro result does not contain {instance_id}"
        )

    resolved = bool(results[instance_id])

    print(
        "TFM_PROBENCH_RESULT="
        + json.dumps(
            {
                "instance_id": instance_id,
                "resolved": resolved,
                "result_file": str(result_file),
            }
        )
    )


if __name__ == "__main__":
    main()