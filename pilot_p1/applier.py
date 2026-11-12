"""Aplicador determinista de bloques SEARCH/REPLACE sobre copias temporales de ficheros de un commit.

Garantias:
* Solo LEE del repositorio (``git ls-tree`` / ``git cat-file``); nunca hace checkout, fetch ni escribe.
* Trabaja sobre copias en un directorio temporal propio (se borra al terminar).
* Todo o nada: si un bloque falla, no se devuelve ningun diff.
* Salida reproducible: mismo commit + mismas instrucciones => mismo diff byte a byte.
* Los fallos del entorno (git que falla, tiempo agotado, disco) se devuelven como ``environment_error`` y
  nunca se atribuyen al modelo (``ApplyResult.model_fault`` es False).
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .edit_format import EditBlock, EditFormatError, normalize_newlines, parse_edits

# Estados
PARSE_ERROR = "parse_error"
UNSAFE_PATH = "unsafe_path"
FILE_NOT_FOUND = "file_not_found"
UNSUPPORTED_FILE = "unsupported_file"
SEARCH_NOT_FOUND = "search_not_found"
BLANK_SEARCH = "blank_search"
AMBIGUOUS = "ambiguous_match"
OVERLAPPING = "overlapping_edits"
INCONSISTENT = "inconsistent_edits"
EMPTY_DIFF = "empty_diff"
READY = "patch_ready"
ENV_ERROR = "environment_error"      # fallo del entorno, NO del modelo

CONTEXT_LINES = 3
GIT_TIMEOUT_S = 60                  # por invocacion de git (ls-tree / cat-file)
WS = " \t"                          # unicos caracteres que se ignoran al comparar lineas
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_HEX = re.compile(r"^[0-9a-fA-F]{7,64}$")


# --------------------------------------------------------------------------- fuentes de ficheros
@dataclass(frozen=True)
class Entry:
    kind: str            # file | symlink | submodule | tree
    ref: str = ""        # sha del blob (GitSource) o ruta real (DirSource)


class SourceError(RuntimeError):
    """Fallo del entorno al leer la fuente (git falla, tiempo agotado, objeto ausente...)."""


class WorkdirError(ValueError):
    """Directorio de copias solicitado inseguro (error de uso, no de la salida del modelo)."""


class GitSource:
    """Lee ficheros de un commit con comandos git de SOLO lectura (lista blanca)."""

    def __init__(self, repo_dir, commit: str, timeout: float = GIT_TIMEOUT_S):
        if not _HEX.match(commit or ""):
            raise SourceError(f"commit no valido (se exige hash hexadecimal): {commit!r}")
        self.repo = str(repo_dir)
        self.commit = commit
        self.timeout = timeout
        self._env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        if self._run("cat-file", "-e", f"{commit}^{{commit}}", check=False)[0] != 0:
            raise SourceError(f"el commit {commit} no existe en {self.repo}")

    def protected_paths(self) -> List[Path]:
        return [Path(self.repo).resolve()]

    def _run(self, *args: str, check: bool = True) -> Tuple[int, bytes]:
        if args[0] not in ("ls-tree", "cat-file"):
            raise SourceError(f"comando git no permitido: {args[0]}")
        try:
            p = subprocess.run(["git", "--no-optional-locks", "--literal-pathspecs", "-C", self.repo, *args],
                               capture_output=True, env=self._env, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise SourceError(f"git {args[0]} supero el limite de {self.timeout:g} s") from None
        except OSError as e:
            raise SourceError(f"no se pudo ejecutar git: {e}") from None
        if check and p.returncode != 0:
            raise SourceError(f"git {args[0]} fallo (codigo {p.returncode}): "
                              f"{p.stderr.decode('utf-8', 'replace').strip()[:300]}")
        return p.returncode, p.stdout

    def entry(self, path: str) -> Optional[Entry]:
        """None solo si la ruta NO existe en el commit; cualquier fallo de git lanza SourceError."""
        _, out = self._run("ls-tree", "-z", self.commit, "--", path)
        if not out:
            return None
        meta, _, name = out.rstrip(b"\0").partition(b"\t")
        if name.decode("utf-8", "surrogateescape") != path:
            return None
        mode, typ, sha = meta.decode().split()
        if mode == "120000":
            return Entry("symlink", sha)
        if typ == "commit":
            return Entry("submodule", sha)
        if typ == "tree":
            return Entry("tree", sha)
        return Entry("file", sha)

    def list_dir(self, path: str) -> List[str]:
        """Nombres (no rutas) de los hijos directos de un directorio ('' = raiz); [] si no existe."""
        args = ["ls-tree", "--name-only", "-z", self.commit] + (["--", path + "/"] if path else [])
        _, out = self._run(*args)
        return [n.decode("utf-8", "surrogateescape").rsplit("/", 1)[-1] for n in out.split(b"\0") if n]

    def read(self, entry: Entry) -> bytes:
        return self._run("cat-file", "blob", entry.ref)[1]


class DirSource:
    """Lee de un directorio (fixtures/pruebas). Nunca escribe."""

    def __init__(self, root):
        self.root = Path(root).resolve()

    def protected_paths(self) -> List[Path]:
        return [self.root]

    def list_dir(self, path: str) -> List[str]:
        d = self.root.joinpath(*path.split("/")) if path else self.root
        try:
            return os.listdir(d) if d.is_dir() and not d.is_symlink() else []
        except OSError as e:
            raise SourceError(f"no se pudo listar {path or '.'}: {e}") from None

    def entry(self, path: str) -> Optional[Entry]:
        p = self.root.joinpath(*path.split("/"))
        if p.is_symlink():
            return Entry("symlink", str(p))
        if p.is_dir():
            return Entry("tree", str(p))
        if p.is_file():
            return Entry("file", str(p))
        return None

    def read(self, entry: Entry) -> bytes:
        try:
            return Path(entry.ref).read_bytes()
        except OSError as e:
            raise SourceError(f"no se pudo leer {entry.ref}: {e}") from None


# --------------------------------------------------------------------------- resultado
@dataclass
class BlockOutcome:
    index: int
    path: str
    status: str = READY
    detail: str = ""
    match_level: int = 0       # 1 exacto (sin espacios finales), 2 ignorando indentacion, 0 n/a
    start_line: int = 0        # linea 1-based donde casa en el original


@dataclass
class ApplyResult:
    status: str
    detail: str = ""
    diff: str = ""
    files: Dict[str, Optional[bytes]] = field(default_factory=dict)   # ruta -> bytes nuevos
    outcomes: List[BlockOutcome] = field(default_factory=list)
    workdir: Optional[str] = None      # solo si se pidio conservar las copias (keep_copies_in)

    @property
    def ok(self) -> bool:
        return self.status == READY

    @property
    def model_fault(self) -> bool:
        """True si el rechazo se debe a la salida del modelo; False para exito y para fallos del entorno."""
        return self.status not in (READY, ENV_ERROR)

    @property
    def diff_bytes(self) -> bytes:
        return self.diff.encode("utf-8")

    @property
    def diff_sha256(self) -> str:
        return hashlib.sha256(self.diff_bytes).hexdigest()


# --------------------------------------------------------------------------- rutas
def path_problem(path: str) -> Optional[str]:
    """Devuelve el motivo si la ruta no es una ruta relativa segura dentro del repositorio."""
    if not path or path != path.strip():
        return "ruta vacia o con espacios en los extremos"
    if "\0" in path or any(ord(c) < 32 for c in path):
        return "caracteres de control"
    if "\\" in path:
        return "barra invertida"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path) or path.startswith("~"):
        return "ruta absoluta o con unidad"
    if path.endswith("/"):
        return "termina en '/'"
    if len(path) > 1024:
        return "ruta demasiado larga"
    parts = path.split("/")
    for part in parts:
        if len(part.encode("utf-8")) > 255:
            return "segmento de mas de 255 bytes"
        if part.split(".")[0].upper() in _RESERVED:
            return "nombre reservado de dispositivo en Windows"
        if part in ("", ".", ".."):
            return f"segmento no permitido: {part!r}"
        if part.lower() in (".git", ".gitmodules"):
            return "ruta dentro de .git / .gitmodules"
        if part.endswith((" ", ".")):
            return "segmento acabado en espacio o punto (ambiguo en Windows)"
        if ":" in part:
            return "':' en un segmento (flujos de datos alternativos en Windows)"
    return None


# --------------------------------------------------------------------------- texto de un fichero
@dataclass
class _Doc:
    lines: List[str]
    final_nl: bool
    eol: str            # "\n" o "\r\n"
    bom: bool


def _load(data: bytes) -> Tuple[Optional[_Doc], str]:
    if b"\0" in data:
        return None, "fichero binario (NUL)"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "no es UTF-8"
    bom = text.startswith("﻿")
    if bom:
        text = text[1:]
    crlf = text.count("\r\n")
    bare_lf = text.count("\n") - crlf
    bare_cr = text.count("\r") - crlf
    if bare_cr or (crlf and bare_lf):
        return None, "finales de linea mixtos o CR sueltos"
    eol = "\r\n" if crlf else "\n"
    body = text.replace("\r\n", "\n")
    final_nl = body.endswith("\n")
    lines = body.split("\n")
    if final_nl:
        lines.pop()
    if body == "":
        lines, final_nl = [], True
    return _Doc(lines, final_nl, eol, bom), ""


def _dump(doc: _Doc) -> bytes:
    text = doc.eol.join(doc.lines)
    if doc.lines and doc.final_nl:
        text += doc.eol
    return (("﻿" if doc.bom else "") + text).encode("utf-8")


# --------------------------------------------------------------------------- busqueda
def _lead(s: str) -> str:
    return s[: len(s) - len(s.lstrip(" \t"))]


def _find_exact(file_lines: Sequence[str], search: Sequence[str]) -> List[int]:
    f = [x.rstrip(WS) for x in file_lines]
    s = [x.rstrip(WS) for x in search]
    n, m = len(f), len(s)
    return [i for i in range(n - m + 1) if f[i:i + m] == s]


def _find_loose(file_lines: Sequence[str], search: Sequence[str]) -> List[Tuple[int, Tuple[str, str]]]:
    """Casa ignorando indentacion con un desplazamiento de indentacion UNIFORME.
    Devuelve (inicio, (prefijo_a_anadir, prefijo_a_quitar))."""
    f = [x.rstrip(WS) for x in file_lines]
    s = [x.rstrip(WS) for x in search]
    n, m = len(f), len(s)
    found = []
    for i in range(n - m + 1):
        delta, ok = None, True
        for a, b in zip(f[i:i + m], s):
            if (a == "") != (b == ""):
                ok = False
                break
            if a == "":
                continue
            if a.lstrip(" \t") != b.lstrip(" \t"):
                ok = False
                break
            fa, sb = _lead(a), _lead(b)
            if fa.endswith(sb):
                d = (fa[:len(fa) - len(sb)], "")
            elif sb.endswith(fa):
                d = ("", sb[:len(sb) - len(fa)])
            else:
                ok = False
                break
            if delta is None:
                delta = d
            elif delta != d:
                ok = False
                break
        if ok and delta is not None and delta != ("", ""):
            found.append((i, delta))
    return found


def _reindent(lines: Sequence[str], delta: Tuple[str, str]) -> Optional[List[str]]:
    add, rem = delta
    out = []
    for ln in lines:
        if ln.strip(WS) == "":
            out.append(ln)
        elif add:
            out.append(add + ln)
        elif ln.startswith(rem):
            out.append(ln[len(rem):])
        else:
            return None
    return out


# --------------------------------------------------------------------------- diff
def _diff_lines(doc: _Doc) -> List[str]:
    out = [l + doc.eol for l in doc.lines]
    if out and not doc.final_nl:
        out[-1] = doc.lines[-1]
    if out and doc.bom:
        out[0] = "﻿" + out[0]
    return out


def _fmt_range(start: int, length: int) -> str:
    if length == 0:
        return f"{start},0"
    return str(start + 1) if length == 1 else f"{start + 1},{length}"


def _emit(prefix: str, line: str, out: List[str]) -> None:
    out.append(prefix + line)
    if not line.endswith("\n"):
        out.append("\n\\ No newline at end of file\n")


def unified_diff(path: str, old: Optional[List[str]], new: List[str]) -> str:
    """Diff unificado estilo git (3 lineas de contexto, prefijos a/ b/, finales LF en cabeceras)."""
    out: List[str] = [f"diff --git a/{path} b/{path}\n"]
    if old is None:
        out += ["new file mode 100644\n", "--- /dev/null\n", f"+++ b/{path}\n"]
        old = []
    else:
        out += [f"--- a/{path}\n", f"+++ b/{path}\n"]
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for group in sm.get_grouped_opcodes(CONTEXT_LINES):
        a0, a1, b0, b1 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        out.append(f"@@ -{_fmt_range(a0, a1 - a0)} +{_fmt_range(b0, b1 - b0)} @@\n")
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for l in old[i1:i2]:
                    _emit(" ", l, out)
            else:
                for l in old[i1:i2]:
                    _emit("-", l, out)
                for l in new[j1:j2]:
                    _emit("+", l, out)
    return "".join(out)


# --------------------------------------------------------------------------- aplicacion
def _fail(status: str, detail: str, outcomes: List[BlockOutcome]) -> ApplyResult:
    return ApplyResult(status, detail, outcomes=outcomes)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def check_keep_dir(parent, source=None) -> Path:
    """Valida el directorio PADRE donde conservar las copias. El aplicador nunca escribe en el
    directorio indicado: crea dentro un subdirectorio nuevo y vacio (mkdtemp), asi que no puede
    sobrescribir nada existente. Se rechaza todo lo que este dentro del proyecto, de la fuente
    leida o de cualquier arbol git. Lanza ``WorkdirError`` (error de uso)."""
    p = Path(parent)
    if not p.is_absolute():
        raise WorkdirError(f"se exige una ruta absoluta: {parent!s}")
    try:
        r = p.resolve(strict=True)
    except OSError:
        raise WorkdirError(f"el directorio no existe: {parent!s}") from None
    if not r.is_dir():
        raise WorkdirError(f"no es un directorio: {parent!s}")
    protected = [PROJECT_ROOT] + (list(source.protected_paths()) if hasattr(source, "protected_paths") else [])
    for q in protected:
        if r == q or q in r.parents:
            raise WorkdirError(f"{r} esta dentro de una zona protegida ({q})")
    for a in (r, *r.parents):
        if (a / ".git").exists():
            raise WorkdirError(f"{r} esta dentro de un arbol git ({a})")
    return r


def apply_text(text: str, source, *, keep_copies_in=None) -> ApplyResult:
    """Analiza ``text`` (formato EDIT-v1) y lo aplica. No lanza por entradas del modelo ni por fallos
    del entorno (estos devuelven ``environment_error``). ``keep_copies_in``: directorio padre donde
    conservar las copias temporales (ver ``check_keep_dir``); por defecto se borran."""
    keep = check_keep_dir(keep_copies_in, source) if keep_copies_in is not None else None
    try:
        blocks = parse_edits(text)
    except EditFormatError as e:
        return ApplyResult(PARSE_ERROR, str(e))
    return _guarded(blocks, source, keep)


def apply_blocks(blocks: Sequence[EditBlock], source, *, keep_copies_in=None) -> ApplyResult:
    keep = check_keep_dir(keep_copies_in, source) if keep_copies_in is not None else None
    return _guarded(blocks, source, keep)


def _guarded(blocks, source, keep) -> ApplyResult:
    try:
        return _apply(blocks, source, keep)
    except SourceError as e:
        return ApplyResult(ENV_ERROR, str(e))
    except OSError as e:
        return ApplyResult(ENV_ERROR, f"error de E/S: {e}")


def _case_clash(source, path: str) -> Optional[str]:
    """Colision por mayusculas/minusculas con una entrada existente (rompe en sistemas insensibles)."""
    parts = path.split("/")
    for k, name in enumerate(parts):
        for n in source.list_dir("/".join(parts[:k])):
            if n != name and n.casefold() == name.casefold():
                return f"colision de mayusculas con la entrada existente {n!r}"
    return None


def _apply(blocks: Sequence[EditBlock], source, keep) -> ApplyResult:
    outcomes = [BlockOutcome(b.index, b.path) for b in blocks]

    def bad(i: int, status: str, detail: str) -> None:
        if outcomes[i].status == READY:
            outcomes[i].status, outcomes[i].detail = status, detail

    # 1) rutas
    for i, b in enumerate(blocks):
        why = path_problem(b.path)
        if why:
            bad(i, UNSAFE_PATH, why)
    by_path: Dict[str, List[int]] = {}
    for i, b in enumerate(blocks):
        if outcomes[i].status == READY:
            by_path.setdefault(b.path, []).append(i)

    docs: Dict[str, Optional[_Doc]] = {}           # None => fichero nuevo
    matches: Dict[int, Tuple[int, int, List[str]]] = {}   # bloque -> (inicio, fin, lineas_nuevas)

    # 2) existencia, tipo y contenido
    for path, idxs in by_path.items():
        creates = [i for i in idxs if not blocks[i].search]
        edits = [i for i in idxs if blocks[i].search]
        ent = source.entry(path)
        if ent is None:
            for i in edits:
                bad(i, FILE_NOT_FOUND, "el fichero no existe en el commit")
            if creates and edits:
                for i in creates:
                    bad(i, INCONSISTENT, "se crea y se edita el mismo fichero")
            elif len(creates) > 1:
                for i in creates:
                    bad(i, INCONSISTENT, "el mismo fichero nuevo se crea mas de una vez")
            elif creates:
                i = creates[0]
                parts = path.split("/")
                for k in range(1, len(parts)):
                    anc = source.entry("/".join(parts[:k]))
                    if anc is not None and anc.kind != "tree":
                        bad(i, UNSAFE_PATH, f"un directorio padre es {anc.kind}")
                        break
                else:
                    clash = _case_clash(source, path)
                    if not any(x.strip(WS) for x in blocks[i].replace):
                        bad(i, INCONSISTENT, "fichero nuevo vacio o solo con lineas en blanco")
                    elif clash:
                        bad(i, INCONSISTENT, clash)
                    else:
                        docs[path] = None
            continue
        if ent.kind != "file":
            for i in idxs:
                bad(i, UNSUPPORTED_FILE, f"la ruta es {ent.kind}, no un fichero")
            continue
        for i in creates:
            bad(i, INCONSISTENT, "SEARCH vacio sobre un fichero que ya existe")
        doc, why = _load(source.read(ent))
        if doc is None:
            for i in edits:
                bad(i, UNSUPPORTED_FILE, why)
            continue
        docs[path] = doc
        # 3) busqueda de cada bloque sobre el ORIGINAL
        for i in edits:
            b = blocks[i]
            if all(x.strip(WS) == "" for x in b.search):
                bad(i, BLANK_SEARCH, "SEARCH solo contiene lineas en blanco")
                continue
            ex = _find_exact(doc.lines, b.search)
            if len(ex) > 1:
                bad(i, AMBIGUOUS, f"{len(ex)} coincidencias exactas (lineas {', '.join(str(k + 1) for k in ex[:5])})")
            elif len(ex) == 1:
                outcomes[i].match_level, outcomes[i].start_line = 1, ex[0] + 1
                matches[i] = (ex[0], ex[0] + len(b.search), list(b.replace))
            else:
                lo = _find_loose(doc.lines, b.search)
                if len(lo) > 1:
                    bad(i, AMBIGUOUS, f"{len(lo)} coincidencias ignorando indentacion")
                elif len(lo) == 1:
                    start, delta = lo[0]
                    rep = _reindent(b.replace, delta)
                    if rep is None:
                        bad(i, SEARCH_NOT_FOUND, "coincide ignorando indentacion pero REPLACE no admite el mismo desplazamiento")
                    else:
                        outcomes[i].match_level, outcomes[i].start_line = 2, start + 1
                        matches[i] = (start, start + len(b.search), rep)
                else:
                    bad(i, SEARCH_NOT_FOUND, "SEARCH no aparece en el fichero")

    # 3b) ficheros nuevos que colisionan entre si (mayusculas) o con un directorio que se crea a la vez
    news = sorted(pth for pth, d in docs.items() if d is None)
    for x in range(len(news)):
        for y in range(x + 1, len(news)):
            ca, cb = news[x].casefold(), news[y].casefold()
            if ca == cb or cb.startswith(ca + "/") or ca.startswith(cb + "/"):
                for pth in (news[x], news[y]):
                    bad(by_path[pth][0], INCONSISTENT, f"colision entre ficheros nuevos {news[x]!r} y {news[y]!r}")

    # 4) solapamientos entre bloques del mismo fichero
    for path, idxs in by_path.items():
        ms = sorted((matches[i][0], matches[i][1], i) for i in idxs if i in matches)
        for (s1, e1, i1), (s2, e2, i2) in zip(ms, ms[1:]):
            if s2 < e1:
                bad(i1, OVERLAPPING, f"se solapa con el bloque {i2}")
                bad(i2, OVERLAPPING, f"se solapa con el bloque {i1}")

    failed = [o for o in outcomes if o.status != READY]
    if failed:
        order = [UNSAFE_PATH, FILE_NOT_FOUND, UNSUPPORTED_FILE, SEARCH_NOT_FOUND, BLANK_SEARCH,
                 AMBIGUOUS, OVERLAPPING, INCONSISTENT]
        first = min(failed, key=lambda o: (order.index(o.status), o.index))
        return _fail(first.status, f"bloque {first.index} ({first.path}): {first.detail}", outcomes)

    # 5) aplicar sobre copias temporales y generar diff
    new_files: Dict[str, Optional[bytes]] = {}
    diff_parts: List[str] = []
    tmp_ctx = None
    if keep is not None:
        root = Path(tempfile.mkdtemp(prefix="pilot_p1_", dir=keep)).resolve()    # subdirectorio NUEVO y vacio
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="pilot_p1_")
        root = Path(tmp_ctx.name).resolve()
    try:
        for path in sorted(by_path):
            idxs = by_path[path]
            doc = docs[path]
            target = (root / Path(*path.split("/"))).resolve()
            if root not in target.parents:
                return _fail(UNSAFE_PATH, f"{path}: sale del directorio de trabajo", outcomes)
            target.parent.mkdir(parents=True, exist_ok=True)
            if doc is None:
                new_doc = _Doc(list(blocks[idxs[0]].replace), True, "\n", False)
                target.write_bytes(_dump(new_doc))
                old_lines = None
            else:
                target.write_bytes(_dump(doc))                      # copia temporal del original
                old_lines = _diff_lines(doc)
                lines = list(doc.lines)
                for i in sorted((i for i in idxs), key=lambda k: matches[k][0], reverse=True):
                    s, e, rep = matches[i]
                    lines[s:e] = rep
                final_nl = doc.final_nl
                if not final_nl and any(matches[i][1] == len(doc.lines) and not matches[i][2] for i in idxs):
                    final_nl = True      # se borra la ultima linea (sin salto): la anterior pasa a ser la ultima
                new_doc = _Doc(lines, final_nl, doc.eol, doc.bom)
                target.write_bytes(_dump(new_doc))                  # el aplicador modifica la copia
            data = target.read_bytes()
            if doc is not None and data == _dump(doc):
                continue                                            # edicion sin efecto
            new_files[path] = data
            diff_parts.append(unified_diff(path, old_lines, _diff_lines(new_doc)))
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    if not diff_parts:
        return _fail(EMPTY_DIFF, "las ediciones no cambian ningun fichero", outcomes)
    return ApplyResult(READY, "", "".join(diff_parts), new_files, outcomes, workdir=str(root) if keep is not None else None)
