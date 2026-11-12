"""Parser estricto del formato EDIT-v1 (FILE / SEARCH / REPLACE).

Formato::

    FILE: ruta/relativa.py
    <<<<<<< SEARCH
    texto literal existente (0 o mas lineas)
    =======
    texto de reemplazo (0 o mas lineas)
    >>>>>>> REPLACE

Reglas (estrictas):
* Un ``FILE:`` puede ir seguido de varios bloques; el siguiente ``FILE:`` cambia de fichero.
* Fuera de los bloques solo se admiten lineas en blanco y lineas que empiezan por ``` (vallas
  de Markdown). Cualquier otro texto es un error (no se interpreta prosa).
* Los marcadores se reconocen por igualdad exacta de la linea (ignorando solo espacios y tabuladores finales).
* Un marcador dentro de la seccion equivocada (anidado, duplicado, fuera de orden) es un error.
* Los finales de linea CRLF y CR se normalizan a LF antes de analizar.
* Un bloque con SEARCH vacio (cero lineas) significa "crear fichero"; la validez de esa
  operacion la decide el aplicador, no el parser.

El parser no toca el sistema de ficheros ni valida rutas (eso es responsabilidad del aplicador).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

MARK_SEARCH = "<<<<<<< SEARCH"
MARK_SEP = "======="
MARK_REPLACE = ">>>>>>> REPLACE"
_FILE_RE = re.compile(r"^FILE:[ \t]*(\S.*?)[ \t]*$")


class EditFormatError(ValueError):
    """Instruccion mal formada. ``line`` es la linea (1-based) donde se detecto, o 0."""

    def __init__(self, message: str, line: int = 0):
        super().__init__(f"linea {line}: {message}" if line else message)
        self.message = message
        self.line = line


@dataclass(frozen=True)
class EditBlock:
    index: int                   # posicion del bloque en la instruccion (0-based)
    path: str                    # tal cual aparece tras "FILE:"
    search: Tuple[str, ...]      # lineas (sin salto de linea); vacio => crear fichero
    replace: Tuple[str, ...]     # lineas (sin salto de linea); vacio => borrar lo encontrado
    line: int = 0                # linea 1-based del marcador SEARCH (para diagnosticos)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_edits(text: str) -> List[EditBlock]:
    """Devuelve los bloques en orden. Lanza ``EditFormatError`` si algo no cumple el formato."""
    if not isinstance(text, str):
        raise EditFormatError("la entrada debe ser texto")
    if "\0" in text:
        raise EditFormatError("la instruccion contiene el caracter NUL")
    lines = normalize_newlines(text).split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    blocks: List[EditBlock] = []
    state = "outside"            # outside | search | replace
    path = None                  # fichero actual
    pending_file = False         # hay un FILE: sin ningun bloque todavia
    search: List[str] = []
    replace: List[str] = []
    start_line = 0

    for n, raw in enumerate(lines, 1):
        marker = raw.rstrip(" \t")
        if state == "outside":
            if marker == "" or raw.startswith("```"):
                continue
            m = _FILE_RE.match(raw)
            if m:
                if pending_file:
                    raise EditFormatError("FILE: sin ningun bloque SEARCH/REPLACE antes del siguiente FILE:", n)
                path, pending_file = m.group(1), True
            elif marker == MARK_SEARCH:
                if path is None:
                    raise EditFormatError("bloque SEARCH sin FILE: previo", n)
                state, search, replace, start_line = "search", [], [], n
            elif raw.startswith("FILE:"):
                raise EditFormatError("FILE: sin ruta", n)
            else:
                raise EditFormatError(f"texto fuera de un bloque: {raw[:60]!r}", n)
        elif state == "search":
            if marker == MARK_SEP:
                state = "replace"
            elif marker in (MARK_SEARCH, MARK_REPLACE):
                raise EditFormatError(f"marcador {marker!r} inesperado dentro de SEARCH", n)
            else:
                search.append(raw)
        else:  # replace
            if marker == MARK_REPLACE:
                blocks.append(EditBlock(len(blocks), path, tuple(search), tuple(replace), start_line))
                state, pending_file = "outside", False
            elif marker in (MARK_SEARCH, MARK_SEP):
                raise EditFormatError(f"marcador {marker!r} inesperado dentro de REPLACE", n)
            else:
                replace.append(raw)

    if state == "search":
        raise EditFormatError("bloque SEARCH sin separador '=======' ni cierre", start_line)
    if state == "replace":
        raise EditFormatError("bloque sin cierre '>>>>>>> REPLACE'", start_line)
    if pending_file:
        raise EditFormatError("FILE: sin ningun bloque SEARCH/REPLACE")
    if not blocks:
        raise EditFormatError("no hay ningun bloque SEARCH/REPLACE")
    return blocks
