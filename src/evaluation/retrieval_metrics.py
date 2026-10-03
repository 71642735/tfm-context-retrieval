from collections import defaultdict

from src.chunking import Chunk


LineInterval = tuple[int, int]
LineMap = dict[str, list[LineInterval]]


def merge_line_intervals(
    intervals: list[LineInterval],
) -> list[LineInterval]:
    """
    Fusiona intervalos de líneas solapados o adyacentes.

    Ejemplo:
        [(10, 20), (15, 25), (30, 35)]
        ->
        [(10, 25), (30, 35)]
    """

    if not intervals:
        return []

    sorted_intervals = sorted(intervals)

    merged = [sorted_intervals[0]]

    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end + 1:
            merged[-1] = (
                last_start,
                max(last_end, end),
            )
        else:
            merged.append((start, end))

    return merged


def build_gold_line_map(
    gold_context: list[dict],
) -> LineMap:
    """
    Convierte el gold context de ContextBench
    en intervalos de líneas agrupados por fichero.
    """

    intervals_by_file = defaultdict(list)

    for span in gold_context:
        intervals_by_file[span["file"]].append(
            (
                span["start_line"],
                span["end_line"],
            )
        )

    return {
        file_path: merge_line_intervals(intervals)
        for file_path, intervals in intervals_by_file.items()
    }


def build_predicted_line_map(
    chunks: list[Chunk],
) -> LineMap:
    """
    Convierte los chunks recuperados
    en intervalos de líneas agrupados por fichero.
    """

    intervals_by_file = defaultdict(list)

    for chunk in chunks:
        intervals_by_file[chunk.file_path].append(
            (
                chunk.start_line,
                chunk.end_line,
            )
        )

    return {
        file_path: merge_line_intervals(intervals)
        for file_path, intervals in intervals_by_file.items()
    }


def count_lines(
    line_map: LineMap,
) -> int:
    """
    Cuenta el número total de líneas representadas
    por un conjunto de intervalos.
    """

    total = 0

    for intervals in line_map.values():
        for start, end in intervals:
            total += end - start + 1

    return total


def count_intersection_lines(
    predicted: LineMap,
    gold: LineMap,
) -> int:
    """
    Cuenta cuántas líneas recuperadas
    coinciden con las líneas del gold context.
    """

    total = 0

    common_files = predicted.keys() & gold.keys()

    for file_path in common_files:
        predicted_intervals = predicted[file_path]
        gold_intervals = gold[file_path]

        for pred_start, pred_end in predicted_intervals:
            for gold_start, gold_end in gold_intervals:
                start = max(pred_start, gold_start)
                end = min(pred_end, gold_end)

                if start <= end:
                    total += end - start + 1

    return total


def coverage_precision(
    predicted_size: int,
    gold_size: int,
    intersection_size: int,
) -> tuple[float, float]:
    """
    Calcula Coverage y Precision.
    """

    coverage = (
        intersection_size / gold_size
        if gold_size > 0
        else 1.0
    )

    precision = (
        intersection_size / predicted_size
        if predicted_size > 0
        else 1.0
    )

    return coverage, precision


def f1_score(
    coverage: float,
    precision: float,
) -> float:
    """
    Calcula F1 a partir de Coverage y Precision.
    """

    if coverage + precision == 0:
        return 0.0

    return (
        2
        * coverage
        * precision
        / (coverage + precision)
    )


def evaluate_retrieval(
    predicted_chunks: list[Chunk],
    gold_context: list[dict],
) -> dict:
    """
    Evalúa una recuperación a nivel de fichero
    y a nivel de líneas.
    """

    # ---------- File-level ----------

    predicted_files = {
        chunk.file_path
        for chunk in predicted_chunks
    }

    gold_files = {
        span["file"]
        for span in gold_context
    }

    common_files = predicted_files & gold_files

    file_coverage, file_precision = coverage_precision(
        predicted_size=len(predicted_files),
        gold_size=len(gold_files),
        intersection_size=len(common_files),
    )

    # ---------- Line-level ----------

    predicted_lines = build_predicted_line_map(
        predicted_chunks
    )

    gold_lines = build_gold_line_map(
        gold_context
    )

    predicted_line_count = count_lines(
        predicted_lines
    )

    gold_line_count = count_lines(
        gold_lines
    )

    intersection_line_count = count_intersection_lines(
        predicted_lines,
        gold_lines,
    )

    line_coverage, line_precision = coverage_precision(
        predicted_size=predicted_line_count,
        gold_size=gold_line_count,
        intersection_size=intersection_line_count,
    )

    return {
        "file": {
            "coverage": file_coverage,
            "precision": file_precision,
            "f1": f1_score(
                file_coverage,
                file_precision,
            ),
        },
        "line": {
            "coverage": line_coverage,
            "precision": line_precision,
            "f1": f1_score(
                line_coverage,
                line_precision,
            ),
        },
    }