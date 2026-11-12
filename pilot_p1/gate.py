"""Filtro comun G de P1 (fase 3B.1): aplicabilidad de los parches ``O1n`` y ``E1``.

Politica unica, identica para los dos brazos (``gate_check`` no recibe el brazo):
* ``git apply --check -p1 <parche>`` ejecutado en un directorio TEMPORAL que contiene una copia de los ficheros que el parche
  toca (y de los antecesores que sean ficheros), leidos como blobs del ``base_commit`` con ``git cat-file`` (solo lectura);
* el parche se pasa **byte a byte, sin ninguna correccion adicional** (ni finales de linea, ni prefijos, ni espacios);
* nunca se ejecuta ``git apply`` sobre los repositorios de trabajo: el directorio de trabajo es siempre un temporal fuera del
  proyecto y de cualquier arbol git; el entorno se limpia de ``GIT_DIR``/``GIT_WORK_TREE`` y de la configuracion global.

Estados: ``applicable`` (codigo 0), ``not_applicable`` (git rechaza el parche: codigo 1, o 128/129 con uno de los mensajes de
rechazo de parche de ``PATCH_REJECTION_MARKERS``; atribuible a la salida) y ``environment_error`` (cualquier otro fallo de git,
tiempo agotado o fuente ilegible: infraestructura). Solo los errores
de infraestructura se reintentan (hasta 3 intentos totales, misma entrada). Aplicabilidad no es resolucion funcional.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import applier as A

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICABLE, NOT_APPLICABLE, ENV_ERROR = "applicable", "not_applicable", "environment_error"
GATE_COMMAND = ["git", "apply", "--check", "-p1"]
GATE_TIMEOUT_S = 60
MAX_GATE_ATTEMPTS = 3
OUTPUT_LIMIT = 4000
PATCH_REJECTION_MARKERS = ("No valid patches in input", "corrupt patch", "patch does not apply", "patch failed",
                           "No such file or directory", "already exists", "lacks filename", "unrecognized input",
                           "invalid path", "binary patch", "does not exist", "does not match", "inexact", "not a valid")
_DROP_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
             "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES")


class GateWorkdirError(RuntimeError):
    """El directorio temporal no es seguro (dentro del proyecto o de un arbol git)."""


@dataclass
class GateAttempt:
    attempt: int
    status: str
    command: List[str]
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    detail: str = ""
    duration_s: float = 0.0


@dataclass
class GateResult:
    status: str
    reason: str
    patch_sha256: str
    paths: List[str]
    attempts: List[GateAttempt] = field(default_factory=list)
    git_version: str = ""
    unmaterialized: List[str] = field(default_factory=list)

    @property
    def category(self) -> str:
        return {APPLICABLE: "ok", NOT_APPLICABLE: "model_output_error", ENV_ERROR: "infrastructure_not_evaluable"}[self.status]

    def comparable(self) -> dict:
        """Contenido del resultado sin tiempos ni rutas temporales (para comparar dos brazos o dos ejecuciones)."""
        return {"status": self.status, "reason": self.reason, "patch_sha256": self.patch_sha256, "paths": self.paths,
                "attempts": [(a.attempt, a.status, a.command[:-1], a.returncode, a.stderr.replace(a.command[-1], "<patch>"))
                             for a in self.attempts]}


def _clean_env() -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _DROP_ENV}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    return env


def assert_safe_workdir(path: Path) -> None:
    """El directorio de trabajo de G debe estar fuera del proyecto y de cualquier arbol git."""
    r = Path(os.path.realpath(path))
    root = PROJECT_ROOT.resolve()
    if r == root or root in r.parents:
        raise GateWorkdirError(f"el directorio de trabajo de G no puede estar dentro del proyecto: {r}")
    for a in (r, *r.parents):
        if (a / ".git").exists():
            raise GateWorkdirError(f"el directorio de trabajo de G esta dentro de un arbol git: {a}")


def _run_git(args: List[str], cwd: Path, timeout: float):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, env=_clean_env(), timeout=timeout)


def git_version(timeout: float = 15) -> str:
    try:
        return _run_git(["git", "--version"], Path(tempfile.gettempdir()), timeout).stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return "desconocida"


def _numstat_paths(out: bytes) -> List[str]:
    """Rutas de ``git apply --numstat -z`` (incluye ambos extremos de un renombrado)."""
    parts = out.split(b"\0")
    paths: List[str] = []
    i = 0
    while i < len(parts):
        rec = parts[i]
        if not rec:
            i += 1
            continue
        fields = rec.split(b"\t", 2)
        if len(fields) == 3 and fields[2] == b"":            # renombrado: dos rutas en los registros siguientes
            for nxt in parts[i + 1:i + 3]:
                paths.append(nxt.decode("utf-8", "surrogateescape"))
            i += 3
        elif len(fields) == 3:
            paths.append(fields[2].decode("utf-8", "surrogateescape"))
            i += 1
        else:
            i += 1
    return sorted(dict.fromkeys(paths))


def _header_paths(patch: bytes) -> List[str]:
    """Rutas citadas en las cabeceras (complemento de numstat: un renombrado puro solo muestra el destino)."""
    out: List[str] = []
    for line in patch.split(b"\n"):
        line = line.rstrip(b"\r")
        for pre in (b"rename from ", b"copy from "):
            if line.startswith(pre):
                out.append(line[len(pre):].decode("utf-8", "surrogateescape"))
        if line.startswith((b"--- ", b"+++ ")):
            path = line[4:].split(b"\t")[0].decode("utf-8", "surrogateescape")
            if path != "/dev/null" and "/" in path:
                out.append(path.split("/", 1)[1])                          # -p1
    return out


def _materialize(patch_file: Path, tree: Path, source, timeout: float) -> (List[str], List[str]):
    """Copia en ``tree`` los ficheros que toca el parche (y antecesores que sean ficheros). Devuelve (rutas, no copiadas)."""
    p = _run_git(["git", "apply", "--numstat", "-z", "-p1", str(patch_file)], tree, timeout)
    paths = _numstat_paths(p.stdout) if p.returncode == 0 else []
    patch_bytes = patch_file.read_bytes()
    paths = sorted(dict.fromkeys(paths + _header_paths(patch_bytes)))
    skipped: List[str] = []
    for path in paths:
        if A.path_problem(path):
            skipped.append(path)                               # git rechazara la ruta; nunca se escribe fuera del temporal
            continue
        parts = path.split("/")
        for k in range(1, len(parts) + 1):
            sub = "/".join(parts[:k])
            ent = source.entry(sub)
            if ent is None:
                break
            dest = tree.joinpath(*sub.split("/"))
            if ent.kind == "file":
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read(ent))
            elif ent.kind == "tree":
                dest.mkdir(parents=True, exist_ok=True)
            else:
                skipped.append(sub)
                break
    return paths, skipped


def gate_check(patch: bytes, source, *, timeout: float = GATE_TIMEOUT_S, max_attempts: int = MAX_GATE_ATTEMPTS) -> GateResult:
    """Aplica el filtro comun G a ``patch``. No recibe el brazo: ``O1n`` y ``E1`` reciben exactamente el mismo tratamiento."""
    sha = hashlib.sha256(patch).hexdigest()
    version = git_version()
    attempts: List[GateAttempt] = []
    paths: List[str] = []
    skipped: List[str] = []
    for n in range(1, max_attempts + 1):
        t0 = time.monotonic()
        cmd: List[str] = list(GATE_COMMAND) + ["<patch>"]
        try:
            with tempfile.TemporaryDirectory(prefix="p1gate_tree_") as td, tempfile.TemporaryDirectory(prefix="p1gate_patch_") as pd:
                tree, pfile = Path(td), Path(pd) / "g.patch"
                assert_safe_workdir(tree)
                src = source if hasattr(source, "entry") else source()      # fabrica perezosa: su fallo es de infraestructura
                pfile.write_bytes(patch)                       # bytes exactos del parche, sin tocar
                paths, skipped = _materialize(pfile, tree, src, timeout)
                cmd = list(GATE_COMMAND) + [str(pfile)]
                proc = _run_git(cmd, tree, timeout)
        except (A.SourceError, GateWorkdirError, OSError, subprocess.SubprocessError) as exc:
            kind = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else type(exc).__name__
            attempts.append(GateAttempt(n, ENV_ERROR, cmd, None, detail=f"{kind}: {exc}"[:500], duration_s=time.monotonic() - t0))
            continue
        out, err = proc.stdout.decode("utf-8", "replace")[:OUTPUT_LIMIT], proc.stderr.decode("utf-8", "replace")[:OUTPUT_LIMIT]
        if proc.returncode == 0:
            st = APPLICABLE
        elif proc.returncode == 1 or (proc.returncode in (128, 129) and any(m in err for m in PATCH_REJECTION_MARKERS)):
            st = NOT_APPLICABLE
        else:
            st = ENV_ERROR                                       # otro fallo de git: no es un rechazo del parche
        attempts.append(GateAttempt(n, st, cmd, proc.returncode, out, err, duration_s=time.monotonic() - t0))
        if st != ENV_ERROR:
            break
    final = attempts[-1]
    reason = {APPLICABLE: "git apply --check -p1 acepta el parche",
              NOT_APPLICABLE: (final.stderr.strip().splitlines() or ["git rechaza el parche"])[-1][:300],
              ENV_ERROR: (final.detail or final.stderr.strip() or f"codigo de salida {final.returncode}")[:300]}[final.status]
    return GateResult(final.status, reason, sha, paths, attempts, version, skipped)
