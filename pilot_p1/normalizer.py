"""Normalizador N de parches del brazo original (O1 -> O1n).

Unica correccion posible: anadir los prefijos ``a/`` (en ``---``) y ``b/`` (en ``+++``) cuando **todas** las
cabeceras de fichero del parche carecen de ellos y la correspondencia es inequivoca. No toca hunks, contenido,
numeros de linea, contadores ni finales de linea; cualquier duda deja el parche **sin cambios** con un estado
explicito. Es puro (trabaja sobre cadenas en memoria), determinista e idempotente.

Estados (``NormalizeResult.status``):
* ``normalized``             se anadieron prefijos a todas las cabeceras (unico caso en que cambia el texto)
* ``already_prefixed``       todas las cabeceras ya llevan ``a/`` ``b/``; sin cambios
* ``unchanged_no_headers``   no hay cabeceras ``---``/``+++`` seguidas de un hunk (no es un diff reconocible)
* ``unchanged_git_headers``  contiene lineas ``diff --git`` que no son un conjunto coherente y ya prefijado
                             (p. ej. ``diff --git a/x b/x`` con ``---``/``+++`` sin prefijo): N no interpreta
                             cual de las dos rutas prevalece y no toca nada. Si son coherentes y ya llevan
                             ``a/`` ``b/`` el estado es ``already_prefixed``
* ``unchanged_mixed``        cabeceras con y sin prefijo, o con prefijos incoherentes entre ``---`` y ``+++``
* ``unchanged_malformed``    hunk con contadores que no cuadran o estructura truncada
* ``unchanged_unsupported``  rutas entre comillas, borrados completos, ``/dev/null`` en ambos lados, renombrados
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

NORMALIZED = "normalized"
ALREADY = "already_prefixed"
NO_HEADERS = "unchanged_no_headers"
GIT_HEADERS = "unchanged_git_headers"
MIXED = "unchanged_mixed"
MALFORMED = "unchanged_malformed"
UNSUPPORTED = "unchanged_unsupported"

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_DEVNULL = "/dev/null"


@dataclass
class NormalizeResult:
    status: str
    patch: str
    detail: str = ""
    changed_lines: List[int] = field(default_factory=list)     # indices (0-based) de las lineas modificadas

    @property
    def changed(self) -> bool:
        return self.status == NORMALIZED


def _lines(text: str) -> List[str]:
    """Lineas conservando su terminador (solo ``\n`` separa lineas; un ``\r`` previo forma parte del terminador o
    del contenido). La union de las lineas reproduce el texto exacto."""
    return _split_lf_only(text)


def _split_lf_only(text: str) -> List[str]:
    out, start = [], 0
    for i, ch in enumerate(text):
        if ch == "\n":
            out.append(text[start:i + 1])
            start = i + 1
    if start < len(text):
        out.append(text[start:])
    return out


def _body(line: str) -> Tuple[str, str]:
    """(contenido sin terminador, terminador)."""
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _split_path(rest: str) -> Tuple[str, str]:
    """Ruta y sufijo (p. ej. tabulador + marca de tiempo) de una cabecera ``---``/``+++``."""
    path, sep, tail = rest.partition("\t")
    return path, sep + tail


def _scan(lines: List[str]):
    """Recorre el parche con conocimiento de los hunks. Devuelve (cabeceras, lineas_diff_git, estado_error).
    cabeceras: lista de (idx_---, idx_+++). estado_error: None o (estado, detalle)."""
    headers: List[Tuple[int, int]] = []
    git_lines: List[str] = []
    i, n = 0, len(lines)
    while i < n:
        text, _ = _body(lines[i])
        if text.startswith("diff --git "):
            git_lines.append(text)
            i += 1
            continue
        if text.startswith("--- ") and i + 2 < n and _body(lines[i + 1])[0].startswith("+++ ") \
                and _HUNK.match(_body(lines[i + 2])[0]):
            headers.append((i, i + 1))
            i += 2
            while i < n and _HUNK.match(_body(lines[i])[0]):
                m = _HUNK.match(_body(lines[i])[0])
                need_old, need_new = int(m.group(2) if m.group(2) is not None else 1), \
                    int(m.group(4) if m.group(4) is not None else 1)
                i += 1
                while need_old > 0 or need_new > 0:
                    if i >= n:
                        return headers, git_lines, (MALFORMED, "hunk truncado")
                    t = _body(lines[i])[0]
                    if t.startswith("\\"):
                        i += 1
                        continue
                    tag = t[:1]
                    if tag == "+":
                        need_new -= 1
                    elif tag == "-":
                        need_old -= 1
                    elif tag == " " or t == "":
                        need_old -= 1
                        need_new -= 1
                    else:
                        return headers, git_lines, (MALFORMED, f"linea {i + 1}: linea de hunk no valida")
                    if need_old < 0 or need_new < 0:
                        return headers, git_lines, (MALFORMED, f"linea {i + 1}: el hunk excede sus contadores")
                    i += 1
                while i < n and _body(lines[i])[0].startswith("\\"):
                    i += 1
            continue
        i += 1
    return headers, git_lines, None


_GIT_LINE = re.compile(r"^diff --git a/(\S+) b/(\S+)$")


def _git_lines_consistent(git_lines, plan) -> bool:
    paths = set()
    for g in git_lines:
        m = _GIT_LINE.match(g)
        if not m or m.group(1) != m.group(2):
            return False
        paths.add(m.group(1))
    return paths == {p[4][2:] for p in plan}


def normalize_patch(text: str) -> NormalizeResult:
    lines = _lines(text)
    headers, git_lines, err = _scan(lines)
    if err:
        return NormalizeResult(err[0], text, err[1])
    if not headers and git_lines:
        return NormalizeResult(GIT_HEADERS, text, "diff --git sin cabeceras ---/+++ con hunk")
    if not headers:
        # --- / +++ sin hunk detras, o sin cabeceras: no es un diff que podamos interpretar
        return NormalizeResult(NO_HEADERS, text, "sin cabeceras de fichero seguidas de un hunk")

    plan = []       # (idx_old, idx_new, old_path, old_tail, new_path, new_tail, kind)
    kinds = set()
    for io, inew in headers:
        old_txt, _ = _body(lines[io])
        new_txt, _ = _body(lines[inew])
        old_path, old_tail = _split_path(old_txt[4:])
        new_path, new_tail = _split_path(new_txt[4:])
        if not old_path or not new_path or old_path.startswith('"') or new_path.startswith('"'):
            return NormalizeResult(UNSUPPORTED, text, "ruta vacia o entre comillas")
        if old_path == _DEVNULL and new_path == _DEVNULL:
            return NormalizeResult(UNSUPPORTED, text, "/dev/null en ambos lados")
        if new_path == _DEVNULL:
            return NormalizeResult(UNSUPPORTED, text, "borrado completo de fichero")
        if old_path == _DEVNULL:                                    # alta de fichero: la evidencia es solo la ruta nueva
            kind = "prefixed" if new_path.startswith("b/") else "bare"
        elif old_path.startswith("a/") and new_path.startswith("b/") and old_path[2:] == new_path[2:]:
            kind = "prefixed"
        elif old_path == new_path:
            kind = "bare"
        else:
            kinds.add("other")
            kind = "other"
        kinds.add(kind)
        plan.append((io, inew, old_path, old_tail, new_path, new_tail, kind))

    if "other" in kinds:
        # prefijos incoherentes, renombrados o rutas distintas en --- y +++
        mixed = any(p[6] != "other" for p in plan)
        return NormalizeResult(MIXED if mixed else UNSUPPORTED, text,
                               "rutas distintas entre --- y +++ (renombrado o prefijos incoherentes)")
    if git_lines:
        ok = kinds == {"prefixed"} and _git_lines_consistent(git_lines, plan)
        return NormalizeResult(ALREADY if ok else GIT_HEADERS, text,
                               "diff --git coherente y ya prefijado" if ok else "diff --git no coherente con ---/+++ o sin prefijos")
    if kinds == {"prefixed"}:
        return NormalizeResult(ALREADY, text, "todas las cabeceras ya llevan a/ b/")
    if kinds != {"bare"}:
        return NormalizeResult(MIXED, text, "cabeceras con y sin prefijo")

    out = list(lines)
    changed: List[int] = []
    for io, inew, old_path, old_tail, new_path, new_tail, _ in plan:
        _, eol_o = _body(lines[io])
        _, eol_n = _body(lines[inew])
        if old_path != _DEVNULL:
            out[io] = f"--- a/{old_path}{old_tail}{eol_o}"
            changed.append(io)
        out[inew] = f"+++ b/{new_path}{new_tail}{eol_n}"
        changed.append(inew)
    return NormalizeResult(NORMALIZED, "".join(out), f"prefijos anadidos en {len(plan)} fichero(s)", changed)
