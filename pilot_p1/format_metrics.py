"""Metricas de formato de una respuesta (fase 3A), independientes del parser y del normalizador.

Tres cosas distintas que nunca se mezclan:
* **vallas externas**: lineas de valla Markdown (``` al empezar la linea, ignorando sangrado) que envuelven o acompanan
  la respuesta, es decir, fuera del contenido de cualquier edicion;
* **vallas internas**: secuencias ``` dentro del contenido de una edicion (SEARCH/REPLACE) o, en un diff, dentro de las
  lineas de contenido de un hunk (`+`, `-` o espacio);
* **parseabilidad real**: lo que dice el parser existente (solo tiene sentido para E1).

Ademas se registra la **union** (``fences_union_present`` = externas o internas) y, por trazabilidad, la metrica original del
protocolo congelado (``original_metric_a_present``: alguna linea de la respuesta que, sin sangrado, empieza por ```). La union
cubre la metrica original (son iguales siempre que las vallas esten al principio de linea) y puede ser mayor solo si hay
secuencias ``` a mitad de linea dentro del contenido de una edicion o precedidas por el prefijo de una linea de diff.

Este modulo solo LEE el texto: no lo modifica ni invoca al parser para detectar vallas. El recorrido por bloques usa
unicamente los marcadores de linea del formato (igualdad exacta, ignorando espacios y tabuladores finales).
"""
from __future__ import annotations

from typing import Dict, Optional

from .edit_format import EditFormatError, MARK_REPLACE, MARK_SEARCH, normalize_newlines, parse_edits

FENCE = "```"


def _is_fence_line(line: str) -> bool:
    return line.lstrip(" \t").startswith(FENCE)


def _is_diff_content(line: str) -> bool:
    """Linea de contenido de un hunk (+, - o espacio inicial), no cabecera ni marcador de hunk."""
    if line.startswith(("+++ ", "--- ", "@@")):
        return False
    return line[:1] in ("+", "-", " ")


def fence_metrics(response: str, arm: str) -> Dict[str, object]:
    """``arm``: ``"E1"`` (bloques SEARCH/REPLACE) u ``"O1"`` (diff unificado)."""
    if arm not in ("E1", "O1"):
        raise ValueError(f"brazo desconocido: {arm!r}")
    lines = normalize_newlines(response).split("\n")
    external = inner = inner_seq = 0
    in_block = False
    for ln in lines:
        marker = ln.rstrip(" \t")
        if arm == "E1":
            if not in_block:
                if marker == MARK_SEARCH:
                    in_block = True
                elif _is_fence_line(ln):
                    external += 1
            else:
                if marker == MARK_REPLACE:
                    in_block = False
                elif FENCE in ln:
                    inner_seq += ln.count(FENCE)
                    inner += _is_fence_line(ln)
        else:
            if _is_fence_line(ln) and not _is_diff_content(ln):
                external += 1
            elif _is_diff_content(ln) and FENCE in ln:
                inner_seq += ln.count(FENCE)
                inner += 1
    original_a = any(_is_fence_line(ln) for ln in lines)
    nonblank = [ln for ln in lines if ln.strip()]
    wraps = bool(nonblank) and _is_fence_line(nonblank[0]) and _is_fence_line(nonblank[-1]) and len(nonblank) > 1
    return {
        "external_fence_lines": external,
        "external_fences_present": external > 0,
        "wraps_response": wraps,
        "inner_fence_lines": inner,
        "inner_fence_sequences": inner_seq,
        "inner_fences_present": inner_seq > 0,
        "fences_union_present": external > 0 or inner_seq > 0,
        "original_metric_a_present": original_a,
    }


def parseability(response: str, arm: str) -> Dict[str, Optional[object]]:
    """Parseabilidad real con el parser existente (solo E1). No modifica la respuesta."""
    if arm != "E1":
        return {"applicable": False, "parseable": None, "blocks": None, "error": None}
    try:
        blocks = parse_edits(response)
    except EditFormatError as e:
        return {"applicable": True, "parseable": False, "blocks": 0, "error": e.message}
    return {"applicable": True, "parseable": True, "blocks": len(blocks), "error": None}


def format_metrics(response: str, arm: str) -> Dict[str, object]:
    out = {"arm": arm}
    out.update(fence_metrics(response, arm))
    out["parse"] = parseability(response, arm)
    out["fences_and_parseable"] = bool(out["external_fences_present"] and out["parse"]["parseable"])
    return out
