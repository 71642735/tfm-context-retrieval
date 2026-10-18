from __future__ import annotations

from src.downstream.analysis import (
    load_results,
    load_final_task_ids,
    filter_final_sample,
    select_definitive_results,
)

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


RETRIEVAL_RESULTS_PATH = Path("results/final_retrieval_results.csv")
FIGURES_DIR = Path("results/figures")
DOWNSTREAM_RESULTS_PATH = Path("results/downstream_results.jsonl")
FINAL_TASKS_PATH = Path("results/final_tasks.csv")
METHOD_LABELS = {
    "bm25": "BM25",
    "semantic": "UniXcoder",
    "hybrid": "RRF",
}
TABLES_DIR = Path("results/tables")

def load_retrieval_results() -> pd.DataFrame:
    """Carga los resultados finales congelados de retrieval."""
    return pd.read_csv(RETRIEVAL_RESULTS_PATH)


def plot_retrieval_f1(df: pd.DataFrame) -> Path:
    """
    Genera la figura principal del F1 medio para las tres estrategias
    en K=5, K=10 y K=20.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    output_path = FIGURES_DIR / "retrieval-f1-by-k.png"

    aggregated = (
        df.groupby(["method", "k", "level"], as_index=False)["f1"]
        .mean()
    )

    fig, ax = plt.subplots(figsize=(9, 5.5))

    line_styles = {
        "file": "-",
        "line": "--",
    }

    markers = {
        "bm25": "o",
        "semantic": "s",
        "hybrid": "^",
    }

    for method in ("bm25", "semantic", "hybrid"):
        for level in ("file", "line"):
            subset = aggregated[
                (aggregated["method"] == method)
                & (aggregated["level"] == level)
            ].sort_values("k")

            level_label = {
                "file": "fichero",
                "line": "líneas",
            }[level]

            ax.plot(
                subset["k"],
                subset["f1"],
                marker=markers[method],
                linestyle=line_styles[level],
                label=f"{METHOD_LABELS[method]} — {level_label}",
            )

    ax.set_title("F1 medio de recuperación por estrategia y K")
    ax.set_xlabel("K (número de chunks recuperados)")
    ax.set_ylabel("F1 medio")
    ax.set_xticks([5, 10, 20])
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.25)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    return output_path


def plot_downstream_status() -> Path:
    """Genera el resultado downstream final por estrategia."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_results(DOWNSTREAM_RESULTS_PATH)
    final_task_ids = load_final_task_ids(FINAL_TASKS_PATH)
    rows = filter_final_sample(rows, final_task_ids)
    final = select_definitive_results(rows)

    if len(final) != 150:
        raise RuntimeError(
            f"Se esperaban 150 condiciones definitivas y se obtuvieron {len(final)}"
        )

    statuses = ("invalid_patch", "not_resolved", "resolved")
    methods = ("bm25", "semantic", "hybrid")

    counts = {
        method: {
            status: sum(
                1
                for (_, result_method), row in final.items()
                if result_method == method and row["status"] == status
            )
            for status in statuses
        }
        for method in methods
    }

    output_path = FIGURES_DIR / "downstream-status-by-method.png"

    fig, ax = plt.subplots(figsize=(8, 5.5))

    x = range(len(methods))
    bottom = [0] * len(methods)

    status_labels = {
        "invalid_patch": "Patch no aplicable",
        "not_resolved": "Aplicable, no resuelto",
        "resolved": "Resuelto",
    }

    for status in statuses:
        values = [counts[method][status] for method in methods]

        ax.bar(
            x,
            values,
            bottom=bottom,
            label=status_labels[status],
        )

        bottom = [
            previous + value
            for previous, value in zip(bottom, values)
        ]

    ax.set_title("Resultado downstream por estrategia de recuperación")
    ax.set_xlabel("Estrategia")
    ax.set_ylabel("Número de condiciones")
    ax.set_xticks(
        list(x),
        [METHOD_LABELS[method] for method in methods],
    )
    ax.set_ylim(0, 50)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    return output_path

def plot_retrieval_by_applicability() -> Path:
    """
    Compara la calidad media de retrieval a nivel de líneas en K=10
    entre condiciones con patch aplicable y no aplicable.
    """
    retrieval = load_retrieval_results()

    retrieval = retrieval[
        (retrieval["k"] == 10)
        & (retrieval["level"] == "line")
    ]

    rows = load_results(DOWNSTREAM_RESULTS_PATH)
    final_task_ids = load_final_task_ids(FINAL_TASKS_PATH)
    rows = filter_final_sample(rows, final_task_ids)
    final = select_definitive_results(rows)

    if len(final) != 150:
        raise RuntimeError(
            f"Se esperaban 150 condiciones definitivas y se obtuvieron {len(final)}"
        )

    joined_rows = []

    for _, retrieval_row in retrieval.iterrows():
        key = (
            retrieval_row["task_id"],
            retrieval_row["method"],
        )

        downstream_row = final.get(key)

        if downstream_row is None:
            raise RuntimeError(
                f"No hay resultado downstream para {key}"
            )

        status = downstream_row["status"]

        applicability = (
            "Aplicable"
            if status in {"not_resolved", "resolved"}
            else "No aplicable"
        )

        joined_rows.append(
            {
                "applicability": applicability,
                "coverage": retrieval_row["coverage"],
                "f1": retrieval_row["f1"],
            }
        )

    if len(joined_rows) != 150:
        raise RuntimeError(
            f"Se esperaban 150 condiciones cruzadas y se obtuvieron "
            f"{len(joined_rows)}"
        )

    joined = pd.DataFrame(joined_rows)

    aggregated = (
        joined.groupby("applicability")[["coverage", "f1"]]
        .mean()
    )

    categories = ["No aplicable", "Aplicable"]
    category_labels = ["No aplicable\n(n=141)", "Aplicable\n(n=9)"]

    coverage = [
        aggregated.loc[category, "coverage"]
        for category in categories
    ]
    f1 = [
        aggregated.loc[category, "f1"]
        for category in categories
    ]

    output_path = FIGURES_DIR / "retrieval-by-patch-applicability.png"

    fig, ax = plt.subplots(figsize=(7.5, 5.5))

    x = range(len(categories))
    width = 0.35

    ax.bar(
        [position - width / 2 for position in x],
        coverage,
        width,
        label="Coverage de líneas",
    )

    ax.bar(
        [position + width / 2 for position in x],
        f1,
        width,
        label="F1 de líneas",
    )

    ax.set_title("Calidad de recuperación según aplicabilidad del patch")
    ax.set_xlabel("Resultado de aplicabilidad")
    ax.set_ylabel("Media")
    ax.set_xticks(list(x), category_labels)
    ax.set_ylim(bottom=0)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    return output_path


def generate_retrieval_table(df: pd.DataFrame) -> Path:
    """Genera la tabla agregada de resultados de retrieval."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    table = (
        df.groupby(["method", "k", "level"], as_index=False)[
            ["coverage", "precision", "f1"]
        ]
        .mean()
    )

    table["method"] = table["method"].map(METHOD_LABELS)

    output_path = TABLES_DIR / "retrieval-summary.csv"
    table.to_csv(output_path, index=False, float_format="%.4f")

    return output_path


def generate_downstream_table() -> Path:
    """Genera la tabla final de resultados downstream por estrategia."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_results(DOWNSTREAM_RESULTS_PATH)
    final_task_ids = load_final_task_ids(FINAL_TASKS_PATH)
    rows = filter_final_sample(rows, final_task_ids)
    final = select_definitive_results(rows)

    if len(final) != 150:
        raise RuntimeError(
            f"Se esperaban 150 condiciones definitivas y se obtuvieron {len(final)}"
        )

    table_rows = []

    for method in ("bm25", "semantic", "hybrid"):
        method_rows = [
            row
            for (_, result_method), row in final.items()
            if result_method == method
        ]

        counts = {
            status: sum(
                row["status"] == status
                for row in method_rows
            )
            for status in ("invalid_patch", "not_resolved", "resolved")
        }

        total = len(method_rows)

        table_rows.append(
            {
                "method": METHOD_LABELS[method],
                "total": total,
                "invalid_patch": counts["invalid_patch"],
                "invalid_patch_pct": counts["invalid_patch"] / total * 100,
                "not_resolved": counts["not_resolved"],
                "not_resolved_pct": counts["not_resolved"] / total * 100,
                "resolved": counts["resolved"],
                "resolved_pct": counts["resolved"] / total * 100,
            }
        )

    table = pd.DataFrame(table_rows)

    output_path = TABLES_DIR / "downstream-summary.csv"
    table.to_csv(output_path, index=False, float_format="%.2f")

    return output_path


def generate_applicability_table() -> Path:
    """
    Genera la tabla de calidad de retrieval K=10 según aplicabilidad
    del patch, incluyendo media y mediana.
    """
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    retrieval = load_retrieval_results()
    retrieval = retrieval[retrieval["k"] == 10]

    rows = load_results(DOWNSTREAM_RESULTS_PATH)
    final_task_ids = load_final_task_ids(FINAL_TASKS_PATH)
    rows = filter_final_sample(rows, final_task_ids)
    final = select_definitive_results(rows)

    joined_rows = []

    for _, retrieval_row in retrieval.iterrows():
        key = (
            retrieval_row["task_id"],
            retrieval_row["method"],
        )

        downstream_row = final.get(key)

        if downstream_row is None:
            raise RuntimeError(
                f"No hay resultado downstream para {key}"
            )

        status = downstream_row["status"]

        joined_rows.append(
            {
                "applicability": (
                    "Aplicable"
                    if status in {"not_resolved", "resolved"}
                    else "No aplicable"
                ),
                "level": retrieval_row["level"],
                "coverage": retrieval_row["coverage"],
                "precision": retrieval_row["precision"],
                "f1": retrieval_row["f1"],
            }
        )

    joined = pd.DataFrame(joined_rows)

    table = (
        joined.groupby(["applicability", "level"])[
            ["coverage", "precision", "f1"]
        ]
        .agg(["mean", "median"])
        .round(4)
    )

    table.columns = [
        f"{metric}_{statistic}"
        for metric, statistic in table.columns
    ]

    table = table.reset_index()

    output_path = TABLES_DIR / "retrieval-by-applicability.csv"
    table.to_csv(output_path, index=False)

    return output_path

def plot_task_distribution_by_repository() -> Path:
    """Genera la distribución de las 50 tareas finales por repositorio."""
    tasks = pd.read_csv(FINAL_TASKS_PATH)

    if len(tasks) != 50:
        raise RuntimeError(
            f"Se esperaban 50 tareas finales y se obtuvieron {len(tasks)}"
        )

    counts = (
        tasks["repo"]
        .value_counts()
        .sort_values(ascending=True)
    )

    output_path = FIGURES_DIR / "task-distribution-by-repository.png"

    fig, ax = plt.subplots(figsize=(9, 7))

    ax.barh(
        counts.index,
        counts.values,
    )

    ax.set_title("Distribución de la muestra final por repositorio")
    ax.set_xlabel("Número de tareas")
    ax.set_ylabel("Repositorio")
    ax.set_xticks(range(0, int(counts.max()) + 1))

    for position, value in enumerate(counts.values):
        ax.text(
            value + 0.03,
            position,
            str(value),
            va="center",
        )

    ax.set_xlim(0, counts.max() + 0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    return output_path

def main() -> None:
    retrieval = load_retrieval_results()

    retrieval_figure = plot_retrieval_f1(retrieval)
    downstream_figure = plot_downstream_status()
    applicability_figure = plot_retrieval_by_applicability()
    repository_figure = plot_task_distribution_by_repository()

    retrieval_table = generate_retrieval_table(retrieval)
    downstream_table = generate_downstream_table()
    applicability_table = generate_applicability_table()

    print("Figuras generadas:")
    print(retrieval_figure)
    print(downstream_figure)
    print(applicability_figure)
    print(repository_figure)

    print()
    print("Tablas generadas:")
    print(retrieval_table)
    print(downstream_table)
    print(applicability_table)


if __name__ == "__main__":
    main()
