"""Validación de reproducibilidad numérica de los resultados de recuperación.

Modos:
    python scripts/validate_reproducibility.py
    python scripts/validate_reproducibility.py --mode consolidated
    python scripts/validate_reproducibility.py --mode independent

En modo automático se prefieren las ejecuciones independientes cuando están
presentes todas; en caso contrario se valida el CSV consolidado conservado.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "results" / "final_retrieval_results.csv"
CONSOLIDATED = ROOT / "results" / "reproducibility_validation.csv"
RUNS = [
    ROOT / "reproduction_runs" / name / "results" / "final_retrieval_results.csv"
    for name in ("test_01", "test_02", "batch_18", "batch_07")
]
KEYS = ["task_id", "method", "k", "level"]
METRICS = ["coverage", "precision", "f1"]
TASK_COUNT = 20
ROW_COUNT = 360
ATOL = 1e-9
EXPECTED = {
    (method, k, level)
    for method in ("bm25", "semantic", "hybrid")
    for k in (5, 10, 20)
    for level in ("file", "line")
}


def read_csv(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"No existe el archivo: {path}")
    df = pd.read_csv(path)
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Columnas ausentes en {path}: {missing}")
    if df[KEYS].isna().any().any():
        raise ValueError(f"Identificadores ausentes en {path}")
    if df.duplicated(KEYS).any():
        raise ValueError(f"Combinaciones duplicadas en {path}")
    return df


def check_sample(df: pd.DataFrame) -> None:
    tasks = df["task_id"].nunique()
    if tasks != TASK_COUNT or len(df) != ROW_COUNT:
        raise ValueError(
            f"Muestra incorrecta: {tasks} tareas y {len(df)} filas; "
            f"se esperan {TASK_COUNT} y {ROW_COUNT}"
        )
    for task, group in df.groupby("task_id"):
        combinations = set(zip(group["method"], group["k"], group["level"]))
        if combinations != EXPECTED:
            raise ValueError(f"Combinaciones incompletas o inesperadas: {task}")


def compare_metric(left: pd.Series, right: pd.Series, label: str) -> None:
    a = pd.to_numeric(left, errors="coerce")
    b = pd.to_numeric(right, errors="coerce")
    if a.isna().any() or b.isna().any():
        raise ValueError(f"Valores ausentes o no numéricos en {label}")
    delta = (a - b).abs()
    differences = int((~np.isclose(a, b, rtol=0, atol=ATOL)).sum())
    print(f"{label:30s} diferencias={differences:3d}  máximo={delta.max():.12g}")
    if differences:
        raise ValueError(f"La comparación {label} presenta {differences} diferencias")


def match_original(consolidated: pd.DataFrame, original: pd.DataFrame) -> None:
    reference = original[KEYS + METRICS]
    merged = consolidated.merge(
        reference,
        on=KEYS,
        how="left",
        validate="one_to_one",
        indicator=True,
        suffixes=("", "_reference"),
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError("Hay combinaciones sin correspondencia en los resultados originales")
    for metric in METRICS:
        compare_metric(
            merged[f"{metric}_original"],
            merged[metric],
            f"{metric}: evidencia/original",
        )


def validate_consolidated(original: pd.DataFrame) -> None:
    columns = KEYS + [f"{m}_{suffix}" for suffix in ("original", "reproduced") for m in METRICS]
    evidence = read_csv(CONSOLIDATED, columns)
    check_sample(evidence)
    match_original(evidence, original)
    for metric in METRICS:
        compare_metric(
            evidence[f"{metric}_reproduced"],
            evidence[f"{metric}_original"],
            f"{metric}: reproducido/original",
        )
    print(f"Evidencia verificada: {CONSOLIDATED}")


def validate_independent(original: pd.DataFrame) -> None:
    reproduced = pd.concat(
        [read_csv(path, KEYS + METRICS) for path in RUNS],
        ignore_index=True,
    )
    if reproduced.duplicated(KEYS).any():
        raise ValueError("Existen combinaciones duplicadas entre ejecuciones")
    check_sample(reproduced)
    comparison = reproduced.merge(
        original[KEYS + METRICS],
        on=KEYS,
        how="left",
        validate="one_to_one",
        indicator=True,
        suffixes=("_reproduced", "_original"),
    )
    if not comparison["_merge"].eq("both").all():
        raise ValueError("Hay combinaciones sin correspondencia original")
    for metric in METRICS:
        compare_metric(
            comparison[f"{metric}_reproduced"],
            comparison[f"{metric}_original"],
            f"{metric}: ejecución/original",
        )
    evidence = comparison.drop(columns="_merge")
    if CONSOLIDATED.is_file():
        existing = read_csv(
            CONSOLIDATED,
            KEYS + [f"{m}_{suffix}" for suffix in ("original", "reproduced") for m in METRICS],
        )
        aligned = evidence.merge(existing, on=KEYS, how="outer", indicator=True,
                                 suffixes=("_run", "_saved"), validate="one_to_one")
        if not aligned["_merge"].eq("both").all():
            raise ValueError("La evidencia guardada no contiene las mismas combinaciones")
        for metric in METRICS:
            for suffix in ("original", "reproduced"):
                column = f"{metric}_{suffix}"
                compare_metric(aligned[f"{column}_run"], aligned[f"{column}_saved"],
                               f"{column}: ejecución/CSV")
        print("La evidencia consolidada existente también coincide")
    else:
        CONSOLIDATED.parent.mkdir(parents=True, exist_ok=True)
        evidence.to_csv(CONSOLIDATED, index=False)
        print(f"Evidencia generada: {CONSOLIDATED}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("auto", "independent", "consolidated"),
                        default="auto")
    args = parser.parse_args()
    original = read_csv(ORIGINAL, KEYS + METRICS)
    available_runs = [path.is_file() for path in RUNS]
    if args.mode == "auto":
        if all(available_runs):
            mode = "independent"
        elif any(available_runs):
            raise ValueError("Solo hay parte de las ejecuciones independientes; especifica --mode consolidated")
        else:
            mode = "consolidated"
    else:
        mode = args.mode
    print("=" * 65)
    print("VALIDACIÓN DE REPRODUCIBILIDAD EXPERIMENTAL")
    print(f"Modo: {mode}")
    print("=" * 65)
    if mode == "independent":
        validate_independent(original)
    else:
        validate_consolidated(original)
    print("=" * 65)
    print("RESULTADO: VALIDACIÓN SUPERADA")
    print(f"Tareas: {TASK_COUNT} | Combinaciones: {ROW_COUNT} | Diferencias: 0")
    print(f"Tolerancia absoluta: {ATOL}")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, pd.errors.ParserError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
