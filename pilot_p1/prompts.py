"""Reconstruccion y verificacion de los prompts O1 (formato original) y E1 (EDIT-v1) del piloto P1.

Principios:
* No se recupera nada de nuevo (ni BM25, ni UniXcoder, ni RRF): el contexto sale del ``prompt.txt``
  que se guardo en el experimento original.
* ``prompt.txt`` se escribio con ``Path.write_text`` en Windows: cada ``\\n`` del prompt en memoria
  se guardo como ``\\r\\n``. El prompt realmente enviado al modelo se recupera deshaciendo exactamente esa
  traduccion (``\\r\\n`` -> ``\\n``). Un CRLF interno de un fragmento de codigo se guardo como ``\\r\\r\\n``
  y se recupera como ``\\r\\n``: no se normalizan los finales de linea del contexto.
* O1 es el prompt original sin cambios. E1 es O1 con **solo** el bloque INSTRUCTIONS sustituido por el
  texto congelado ``instructions_edit_v1.txt`` (SHA-256 fijado en ``E1_INSTRUCTIONS_SHA256``).
* Los prompts nuevos se guardan en bytes UTF-8 SIN traduccion de saltos de linea (``serialize_prompt``).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

PACKAGE_DIR = Path(__file__).resolve().parent
E1_INSTRUCTIONS_PATH = PACKAGE_DIR / "instructions_edit_v1.txt"
E1_INSTRUCTIONS_SHA256 = "3577b64d079143810dd018d805677146fe515bc49904d2862dded53f8db293be"

# Plantilla de ``build_prompt`` (src/downstream/generation.py, lineas 69-84), copiada literalmente.
HEAD = "You are fixing an issue in a Python repository.\n\nISSUE:\n"
CONTEXT_MARKER = "\n\nRETRIEVED CONTEXT:\n"
O1_INSTRUCTIONS = (
    "INSTRUCTIONS:\n"
    "- Use only the issue description and the retrieved context above.\n"
    "- Do not assume access to any other repository files.\n"
    "- Produce the minimal code change needed to resolve the issue.\n"
    "- Return only a unified diff patch.\n"
    "- Do not use Markdown code fences.\n"
    "- Do not include explanations before or after the patch.\n"
)
O1_INSTRUCTIONS_SHA256 = hashlib.sha256(O1_INSTRUCTIONS.encode("utf-8")).hexdigest()
_CHUNK_HEAD = re.compile(r"--- Chunk (\d+) ---\nFile: ([^\n]*)\nLines: (\d+)-(\d+)\nSymbol: ([^\n]*)\n\n")


class PromptError(ValueError):
    """El prompt no se puede reconstruir o verificar; nunca se adivina."""


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def e1_instructions() -> str:
    """Instrucciones EDIT-v1 congeladas. Verifica el SHA-256 en cada lectura."""
    raw = E1_INSTRUCTIONS_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != E1_INSTRUCTIONS_SHA256:
        raise PromptError("instructions_edit_v1.txt no coincide con el SHA-256 congelado")
    text = raw.decode("utf-8")
    if "\r" in text or not text.startswith("INSTRUCTIONS:\n") or not text.endswith("\n"):
        raise PromptError("instructions_edit_v1.txt: formato inesperado")
    return text


# --------------------------------------------------------------------------- lectura / escritura
def reconstruct_prompt(raw: bytes, *, windows_translated: bool = True) -> str:
    """Prompt tal como se envio al modelo, a partir de los bytes de un ``prompt.txt``.

    ``windows_translated=True`` (originales): exige que TODO ``\\n`` vaya precedido de ``\\r`` (señal de que el
    fichero paso por ``write_text`` en Windows) y deshace esa traduccion. ``False``: prompts nuevos guardados
    con ``serialize_prompt`` (sin traduccion)."""
    if not windows_translated:
        return raw.decode("utf-8")
    for i, c in enumerate(raw):
        if c == 10 and (i == 0 or raw[i - 1] != 13):
            raise PromptError(f"LF sin CR previo en el byte {i}: el fichero no fue escrito con traduccion de Windows")
    return raw.decode("utf-8").replace("\r\n", "\n")


def windows_write_text_bytes(prompt: str) -> bytes:
    """Bytes que produjo ``Path.write_text(prompt, encoding='utf-8')`` en Windows (para verificar la ida y vuelta)."""
    return prompt.replace("\n", "\r\n").encode("utf-8")


def serialize_prompt(prompt: str) -> bytes:
    """Bytes de un prompt nuevo: UTF-8 exacto, sin traduccion de saltos de linea (usar ``write_bytes``)."""
    return prompt.encode("utf-8")


def load_original_prompt(path) -> str:
    return reconstruct_prompt(Path(path).read_bytes())


# --------------------------------------------------------------------------- estructura
@dataclass(frozen=True)
class Chunk:
    rank: int
    file_path: str
    start_line: int
    end_line: int
    symbol: str
    code: str


@dataclass(frozen=True)
class PromptParts:
    issue: str
    chunks: Tuple[Chunk, ...]
    shared: str          # todo lo anterior al bloque INSTRUCTIONS (incluye "\n\n" final)
    instructions: str


def split_prompt(prompt: str) -> PromptParts:
    """Divide un prompt O1 o E1 en (issue, fragmentos, parte compartida, instrucciones) y comprueba que la
    reconstruccion con la plantilla original es exacta."""
    if not prompt.startswith(HEAD):
        raise PromptError("el prompt no empieza con la plantilla original")
    pos = prompt.rfind("\n\nINSTRUCTIONS:\n")
    if pos < 0:
        raise PromptError("no hay bloque INSTRUCTIONS")
    shared, instructions = prompt[:pos + 2], prompt[pos + 2:]
    body = shared[len(HEAD):-2]          # issue + CONTEXT_MARKER + contexto
    starts = [m.start() for m in re.finditer(re.escape(CONTEXT_MARKER) + r"--- Chunk 1 ---\nFile: ", body)]
    if len(starts) != 1:
        raise PromptError(f"no se localiza de forma unica el inicio del contexto ({len(starts)} candidatos)")
    issue, context = body[:starts[0]], body[starts[0] + len(CONTEXT_MARKER):]
    chunks: List[Chunk] = []
    cur, rank = 0, 1
    while True:
        m = _CHUNK_HEAD.match(context, cur)
        if not m or int(m.group(1)) != rank:
            raise PromptError(f"cabecera de fragmento {rank} no encontrada")
        code_start = m.end()
        nxt = context.find(f"\n\n--- Chunk {rank + 1} ---\nFile: ", code_start)
        code = context[code_start:] if nxt < 0 else context[code_start:nxt]
        chunks.append(Chunk(rank, m.group(2), int(m.group(3)), int(m.group(4)), m.group(5), code))
        if nxt < 0:
            break
        cur, rank = nxt + 2, rank + 1
    parts = PromptParts(issue, tuple(chunks), shared, instructions)
    if rebuild_shared(parts.issue, parts.chunks) != shared:
        raise PromptError("la reconstruccion con la plantilla original no es exacta")
    return parts


def rebuild_shared(issue: str, chunks) -> str:
    """Parte compartida generada con la misma logica que ``build_prompt`` del generador original."""
    context = "\n\n".join(
        "\n".join([f"--- Chunk {c.rank} ---", f"File: {c.file_path}", f"Lines: {c.start_line}-{c.end_line}",
                   f"Symbol: {c.symbol}", "", c.code])
        for c in chunks)
    return f"{HEAD}{issue}{CONTEXT_MARKER}{context}\n\n"


# --------------------------------------------------------------------------- brazos
def build_o1(original_prompt: str) -> str:
    """O1: el prompt original, sin cambios (se verifica que termina con las instrucciones originales)."""
    parts = split_prompt(original_prompt)
    if parts.instructions != O1_INSTRUCTIONS:
        raise PromptError("las instrucciones del prompt no son las originales")
    return original_prompt


def build_e1(original_prompt: str) -> str:
    """E1: igual que O1 salvo el bloque INSTRUCTIONS (texto congelado EDIT-v1)."""
    parts = split_prompt(build_o1(original_prompt))
    return parts.shared + e1_instructions()


def context_fingerprint(prompt: str) -> dict:
    """Huellas de la parte que debe ser identica entre brazos: issue, fragmentos, orden y parte compartida."""
    p = split_prompt(prompt)
    return {
        "issue_sha256": sha256_text(p.issue),
        "shared_sha256": sha256_text(p.shared),
        "n_chunks": len(p.chunks),
        "chunk_order_sha256": sha256_text("\n".join(f"{c.rank}|{c.file_path}|{c.start_line}-{c.end_line}|{c.symbol}"
                                                    for c in p.chunks)),
        "chunk_code_sha256": [sha256_text(c.code) for c in p.chunks],
    }


EXPECTED_CHUNKS = 10      # K = 10 del protocolo original (TOP_K)


def arm_record(original_prompt: str) -> dict:
    """Registro de verificacion de una condicion: hashes de O1 y E1 y de su contexto compartido."""
    o1, e1 = build_o1(original_prompt), build_e1(original_prompt)
    fo, fe = context_fingerprint(o1), context_fingerprint(e1)
    if fo["n_chunks"] != EXPECTED_CHUNKS:
        raise PromptError(f"se esperaban {EXPECTED_CHUNKS} fragmentos y hay {fo['n_chunks']}")
    return {
        "o1_prompt_sha256": sha256_text(o1),
        "e1_prompt_sha256": sha256_text(e1),
        "o1_instructions_sha256": O1_INSTRUCTIONS_SHA256,
        "e1_instructions_sha256": E1_INSTRUCTIONS_SHA256,
        "context_identical": fo == fe,
        "context": fo,
    }
