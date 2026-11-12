"""Ayudas para los simulacros: respuestas SINTETICAS derivadas del primer fragmento del prompt (no del modelo)."""
import hashlib
import shutil
import tempfile
from pathlib import Path

from pilot_p1 import prompts as P
from pilot_p1.client import FakeClient

SYNTH = "# pilot-check"


def synthetic_text(prompt: str) -> str:
    """E1: bloque SEARCH/REPLACE con las 6 primeras lineas del primer fragmento. O1: diff con cabeceras sin prefijo."""
    parts = P.split_prompt(prompt)
    c = parts.chunks[0]
    lines = [l.rstrip("\r") for l in c.code.replace("\r\n", "\n").split("\n")][:6]
    if parts.instructions == P.O1_INSTRUCTIONS:
        # el generador original guarda response.strip() + salto: un diff que acabe en una linea de contexto en blanco la pierde
        # (hunk truncado = parche corrupto, tambien en el experimento original). Se evita aqui; ver test_stripping_*.
        while len(lines) > 2 and not lines[-1].strip():
            lines.pop()
        n = len(lines)
        k = (n - 1) // 2                          # se modifica una linea intermedia: contexto antes y despues (git lo exige)
        body = ("".join(f" {l}\n" for l in lines[:k]) + f"-{lines[k]}\n+{lines[k]}\n+{SYNTH}\n"
                + "".join(f" {l}\n" for l in lines[k + 1:]))
        return (f"--- {c.file_path}\n+++ {c.file_path}\n@@ -{c.start_line},{n} +{c.start_line},{n + 1} @@\n" + body)
    return "\n".join([f"FILE: {c.file_path}", "<<<<<<< SEARCH", *lines, "=======", *lines, SYNTH, ">>>>>>> REPLACE"]) + "\n"


def variant(prompt: str, text: str) -> str:
    """Variaciones deterministas que deben conservarse byte a byte (vallas, espacios, CRLF)."""
    k = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:2], 16) % 6
    if k == 1:
        return "```\n" + text + "```\n"
    if k == 2:
        return "\n\n" + text.rstrip("\n") + "   \n\n"
    if k == 3:
        return text.replace("\n", "\r\n")
    return text


class Recorder:
    """Responder que recuerda lo que devolvio para cada prompt (para comparar con lo guardado)."""

    def __init__(self):
        self.produced = {}

    def __call__(self, prompt: str) -> str:
        text = variant(prompt, synthetic_text(prompt))
        self.produced[hashlib.sha256(prompt.encode("utf-8")).hexdigest()] = text
        return text


def fake_client() -> (FakeClient, Recorder):
    rec = Recorder()
    return FakeClient(responder=rec), rec


class TempRun:
    """Directorio de salida temporal 'simulacro_*' FUERA del proyecto."""

    def __init__(self, name="simulacro_test"):
        self._tmp = tempfile.TemporaryDirectory(prefix="p1orch_")
        self.path = Path(self._tmp.name) / name

    def cleanup(self):
        self._tmp.cleanup()


class SyntheticWorld:
    """Mundo sintetico pequeno (sin git ni repos/): ficheros de texto y prompts originales fabricados con la plantilla real."""

    def __init__(self, root: Path, n_tasks: int = 2):
        self.root = Path(root) / "world"
        self.task_ids = [f"synth__task-{i}" for i in range(n_tasks)]
        for j in range(1, 11):
            f = self.root / "pkg" / f"m{j}.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes("".join(f"v{j}_{k} = {k}\n" for k in range(1, 21)).encode())

    def prompt_provider(self, task_id: str, method: str) -> str:
        chunks = []
        for j in range(1, 11):
            code = "\n".join(f"v{j}_{k} = {k}" for k in range(1, 11))
            chunks.append(P.Chunk(j, f"pkg/m{j}.py", 1, 10, "f", code))
        issue = f"Issue de {task_id} con {method}"
        return P.rebuild_shared(issue, chunks) + P.O1_INSTRUCTIONS

    def source_factory(self, task_id: str):
        from pilot_p1.applier import DirSource
        return DirSource(self.root)
