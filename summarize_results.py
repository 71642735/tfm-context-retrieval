import csv
from collections import defaultdict
from pathlib import Path


RESULTS_FILE = Path("results/retrieval_results.csv")
SUMMARY_FILE = Path("results/retrieval_summary.csv")


def main() -> None:
    with RESULTS_FILE.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))

    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["method"],
            int(row["k"]),
            row["level"],
        )
        grouped[key].append(row)

    summary_rows = []

    print(
        f"{'Método':<10} "
        f"{'K':>3} "
        f"{'Nivel':<6} "
        f"{'Coverage':>10} "
        f"{'Precision':>10} "
        f"{'F1':>10}"
    )
    print("-" * 58)

    method_order = ["bm25", "semantic", "hybrid"]
    level_order = ["file", "line"]

    for method in method_order:
        for k in [5, 10, 20]:
            for level in level_order:
                group = grouped[(method, k, level)]

                if not group:
                    continue

                coverage = sum(
                    float(row["coverage"])
                    for row in group
                ) / len(group)

                precision = sum(
                    float(row["precision"])
                    for row in group
                ) / len(group)

                f1 = sum(
                    float(row["f1"])
                    for row in group
                ) / len(group)

                summary_row = {
                    "method": method,
                    "k": k,
                    "level": level,
                    "num_tasks": len(group),
                    "coverage": coverage,
                    "precision": precision,
                    "f1": f1,
                }

                summary_rows.append(summary_row)

                print(
                    f"{method:<10} "
                    f"{k:>3} "
                    f"{level:<6} "
                    f"{coverage:>10.4f} "
                    f"{precision:>10.4f} "
                    f"{f1:>10.4f}"
                )

    SUMMARY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SUMMARY_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fieldnames = [
            "method",
            "k",
            "level",
            "num_tasks",
            "coverage",
            "precision",
            "f1",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(summary_rows)

    print(
        f"\nResumen guardado en: {SUMMARY_FILE}"
    )


if __name__ == "__main__":
    main()