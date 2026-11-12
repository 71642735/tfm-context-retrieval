"""Orquestacion aislada de las 72 generaciones de P1 (fase 3A: solo clientes SINTETICOS; sin API real).

Garantias:
* Lee solo la seleccion congelada (``data/task_selection.json``) y reconstruye los prompts con ``prompts.py``.
* Escribe unicamente en un directorio de salida explicito y validado (``validate_output_dir``), nunca en ``src/``, ``repos/``,
  ``results/``, ``logs/``, ``diagnostics/``, ``docs/`` ni dentro de ningun arbol git.
* Todos los ficheros se crean una sola vez (nunca se sobrescribe); el registro de eventos es de solo anadir y encadena hashes.
* La respuesta del modelo se guarda tal cual, sin modificar; generacion, formato, conversion (E1), normalizacion (O1),
  aplicabilidad y resolucion funcional son etapas separadas (las dos ultimas quedan pendientes de la fase 3B).
* Reanudable: verifica la integridad de lo existente antes de continuar y nunca repite una generacion ya sellada.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from . import applier as A
from . import prompts as P
from . import select_tasks as S
from .client import (APIError, ClientResponse, MAX_API_ATTEMPTS, MAX_OUTPUT_TOKENS, MODEL, RETRYABLE_API_CODES,
                     THINKING_LEVEL)
from .format_metrics import format_metrics
from .normalizer import normalize_patch
from . import decision as DEC
from . import functional as FUN
from . import gate as GATE

PROTOCOL_COMMIT = "fb589c13129e6da2c8302cd243bc151dff598158"
PROTOCOL_VERSION = f"P1-frozen-{PROTOCOL_COMMIT[:7]}"
SCHEMA_VERSION = 1
ARMS = ("O1", "E1")
MAX_APPLY_ATTEMPTS = 3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / "pilot_p1_runs"          # unico lugar dentro del proyecto donde se permite escribir
FORBIDDEN_TOP = ("src", "repos", "results", "logs", "diagnostics", "docs", "external", "pilot_p1", "cache", ".git", ".venv")
LOGS_ORIGINAL = PROJECT_ROOT / "logs" / "downstream"
TASKS_CSV = PROJECT_ROOT / "results" / "final_tasks.csv"

MANIFEST = "RUN_MANIFEST.json"
EVENTS = "events.jsonl"
LOCK = "RUN.lock"
COND_DIR = "conditions"
FILES_COMMON = {"prompt.txt", "generation.json", "generation_failed.json", "response.txt", "format_metrics.json"}
FILES_STAGE2 = {"applicability.json", "functional.json", "functional_evidence.json"}      # fase 3B.1
FILES_E1 = {"conversion.json", "diff.patch"} | FILES_STAGE2
FILES_O1 = {"normalization.json", "o1.patch", "o1n.patch"} | FILES_STAGE2
EVIDENCE_LIMIT = 200_000


class OrchestrationError(RuntimeError):
    pass


class IntegrityError(OrchestrationError):
    pass


class OutputDirError(OrchestrationError):
    pass


class OverwriteError(OrchestrationError):
    pass


class RealClientNotAllowed(OrchestrationError):
    pass


class InterruptedConditionError(OrchestrationError):
    pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def canonical(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- aislamiento
def validate_output_dir(path, *, synthetic: bool = True) -> Path:
    """Valida el directorio de salida ANTES de escribir. Lanza ``OutputDirError``."""
    p = Path(path)
    if not p.is_absolute():
        raise OutputDirError(f"el directorio de salida debe ser absoluto: {path!s}")
    r = Path(os.path.realpath(p))
    leaf_prefix = "simulacro_" if synthetic else "p1_run_"
    if not r.name.startswith(leaf_prefix):
        raise OutputDirError(f"el directorio debe llamarse {leaf_prefix}*: {r.name}")
    root = PROJECT_ROOT.resolve()
    if r == root or r in root.parents:
        raise OutputDirError("el directorio de salida no puede ser el proyecto ni uno de sus ancestros")
    if root in r.parents:
        rel = r.relative_to(root)
        if rel.parts[0] in FORBIDDEN_TOP:
            raise OutputDirError(f"zona protegida del proyecto: {rel.parts[0]}/")
        if RUNS_ROOT.resolve() not in r.parents:
            raise OutputDirError(f"dentro del proyecto solo se admite {RUNS_ROOT.name}/<ejecucion>")
    else:
        for a in r.parents:
            if (a / ".git").exists():
                raise OutputDirError(f"el directorio esta dentro de un arbol git ({a})")
    if r.exists():
        if not r.is_dir():
            raise OutputDirError("la ruta existe y no es un directorio")
        if any(r.iterdir()) and not (r / MANIFEST).is_file():
            raise OutputDirError("el directorio no esta vacio y no es una ejecucion de P1 (sin manifiesto)")
    return r


def write_new(path: Path, data: bytes) -> None:
    """Crea ``path`` exclusivamente: si ya existe lanza ``OverwriteError``; escritura atomica via temporal + enlace."""
    if path.exists():
        raise OverwriteError(f"ya existe y no se sobrescribe: {path}")
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(3)}.tmp")
    with open(tmp, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        try:
            os.link(tmp, path)
        except FileExistsError:
            raise OverwriteError(f"ya existe y no se sobrescribe: {path}") from None
        except OSError:
            if path.exists():
                raise OverwriteError(f"ya existe y no se sobrescribe: {path}") from None
            os.rename(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


# --------------------------------------------------------------------------- condiciones
@dataclass(frozen=True)
class Condition:
    cond_id: str
    pair_id: str
    task_id: str
    task_index: int
    method: str
    arm: str


def build_conditions(task_ids: Sequence[str], methods: Sequence[str] = S.METHODS) -> List[Condition]:
    """72 condiciones; para cada (tarea, metodo) el par O1 y E1 va consecutivo (O1 primero)."""
    out = []
    for i, t in enumerate(task_ids):
        h = sha256_text(t)[:8]
        for m in methods:
            pair = f"c{i:02d}-{h}-{m}"
            for arm in ARMS:
                out.append(Condition(f"{pair}-{arm}", pair, t, i, m, arm))
    return out


def selection_from_manifest() -> List[str]:
    """Seleccion congelada, leida solo de data/task_selection.json y comprobada contra el hash del protocolo."""
    m = S.load_manifest()
    pop = {r["id"]: r["source"] for r in m["population"]}
    ids = S.select(pop)
    S.check_selection(ids)
    if [r["id"] for r in m["selected"]] != ids:
        raise IntegrityError("la seleccion guardada no coincide con la recalculada")
    return ids


def default_prompt_provider(task_id: str, method: str) -> str:
    return P.load_original_prompt(LOGS_ORIGINAL / task_id / method / "prompt.txt")


def default_task_info(task_id: str) -> dict:
    """Repositorio y base_commit de la tarea (solo lectura de results/final_tasks.csv); {} si no se encuentra."""
    try:
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            row = next(r for r in csv.DictReader(fh) if r["original_inst_id"] == task_id)
        return {"repo": row["repo"], "base_commit": row["base_commit"]}
    except (OSError, StopIteration):
        return {}


def default_source_factory(task_id: str):
    with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
        row = next(r for r in csv.DictReader(fh) if r["original_inst_id"] == task_id)
    return A.GitSource(PROJECT_ROOT / "repos" / row["repo"].replace("/", "__"), row["base_commit"])


# --------------------------------------------------------------------------- registro de eventos
class EventLog:
    """JSONL de solo anadir con cadena de hashes (cada linea incluye el SHA-256 de la anterior)."""

    def __init__(self, path: Path, clock: Callable[[], str]):
        self.path, self.clock = path, clock
        self.seq, self.prev = 0, "0" * 64

    @staticmethod
    def read(path: Path) -> List[dict]:
        events, prev = [], "0" * 64
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise IntegrityError("events.jsonl: ultima linea truncada (escritura incompleta)")
        for n, line in enumerate(raw.split(b"\n")[:-1], 1):
            try:
                e = json.loads(line.decode("utf-8"))
            except ValueError:
                raise IntegrityError(f"events.jsonl: linea {n} no es JSON valido") from None
            if e.get("seq") != n or e.get("prev") != prev:
                raise IntegrityError(f"events.jsonl: cadena de hashes rota en la linea {n}")
            events.append(e)
            prev = sha256_bytes(line)
        return events

    def load(self) -> List[dict]:
        events = self.read(self.path) if self.path.exists() else []
        self.seq = len(events)
        if events:
            self.prev = sha256_bytes(self.path.read_bytes().split(b"\n")[-2])
        return events

    def append(self, type_: str, **fields) -> dict:
        self.seq += 1
        e = {"seq": self.seq, "ts": self.clock(), "type": type_, **fields, "prev": self.prev}
        line = json.dumps(e, sort_keys=True, ensure_ascii=False).encode("utf-8")
        with open(self.path, "ab") as fh:
            fh.write(line + b"\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.prev = sha256_bytes(line)
        return e


@dataclass
class VerifyReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def original_style_patch(response: str) -> str:
    """Lo que hacia el generador original con la respuesta antes de guardarla como patch.diff (strip + salto final)."""
    return response.strip() + "\n"


# --------------------------------------------------------------------------- orquestador
class Orchestrator:
    def __init__(self, out_dir, client, *, synthetic: bool = True, require_synthetic: bool = True,
                 task_ids: Optional[Sequence[str]] = None, prompt_provider=None, source_factory=None,
                 clock: Optional[Callable[[], str]] = None, sleep: Callable[[float], None] = time.sleep,
                 on_interrupted: str = "stop", max_apply_attempts: int = MAX_APPLY_ATTEMPTS,
                 functional_evaluator=None, task_info_provider=None):
        if require_synthetic and not getattr(client, "is_synthetic", False):
            raise RealClientNotAllowed("la fase 3A solo admite clientes sinteticos (is_synthetic = True)")
        if synthetic and not getattr(client, "is_synthetic", False):
            raise RealClientNotAllowed("una ejecucion sintetica exige un cliente sintetico")
        if on_interrupted not in ("stop", "retry"):
            raise ValueError("on_interrupted debe ser 'stop' o 'retry'")
        self.out = validate_output_dir(out_dir, synthetic=synthetic)
        self.client, self.synthetic = client, synthetic
        self.clock = clock or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.sleep = sleep
        self.on_interrupted = on_interrupted
        self.max_apply_attempts = max_apply_attempts
        self.prompt_provider = prompt_provider or default_prompt_provider
        self.source_factory = source_factory or default_source_factory
        self.functional_evaluator = functional_evaluator
        self.task_info_provider = task_info_provider or default_task_info
        self.task_ids = list(task_ids) if task_ids is not None else selection_from_manifest()
        self.conditions = build_conditions(self.task_ids)
        self.prompts: Dict[str, str] = {}
        self.log = EventLog(self.out / EVENTS, self.clock)
        self._sources: Dict[str, object] = {}

    # ---- preparacion ---------------------------------------------------------------------------
    def _prepare(self) -> dict:
        """Construye los 72 prompts, comprueba que O1 y E1 comparten el mismo contexto y devuelve el nucleo del manifiesto."""
        recs, originals = [], {}
        for c in self.conditions:
            key = (c.task_id, c.method)
            if key not in originals:
                originals[key] = self.prompt_provider(c.task_id, c.method)
            o = originals[key]
            prompt = P.build_o1(o) if c.arm == "O1" else P.build_e1(o)
            self.prompts[c.cond_id] = prompt
            fp = P.context_fingerprint(prompt)
            recs.append({"cond_id": c.cond_id, "pair_id": c.pair_id, "task_id": c.task_id, "method": c.method, "arm": c.arm,
                         "prompt_sha256": sha256_text(prompt), "shared_sha256": fp["shared_sha256"],
                         "issue_sha256": fp["issue_sha256"], "chunk_order_sha256": fp["chunk_order_sha256"],
                         "n_chunks": fp["n_chunks"]})
        by_pair: Dict[str, dict] = {}
        for r in recs:
            other = by_pair.setdefault(r["pair_id"], r)
            if other is not r and (other["shared_sha256"], other["issue_sha256"], other["chunk_order_sha256"],
                                   other["n_chunks"]) != (r["shared_sha256"], r["issue_sha256"], r["chunk_order_sha256"],
                                                          r["n_chunks"]):
                raise OrchestrationError(f"O1 y E1 no comparten contexto en {r['pair_id']}")
        if any(r["n_chunks"] != P.EXPECTED_CHUNKS for r in recs):
            raise OrchestrationError("alguna condicion no tiene K = 10 fragmentos")
        return {
            "schema_version": SCHEMA_VERSION, "protocol_version": PROTOCOL_VERSION, "protocol_commit": PROTOCOL_COMMIT,
            "synthetic": self.synthetic,
            "warning": ("SIMULACRO: respuestas sinteticas; NO son resultados experimentales." if self.synthetic else ""),
            "model": MODEL, "max_output_tokens": MAX_OUTPUT_TOKENS, "thinking_level": THINKING_LEVEL,
            "max_api_attempts": MAX_API_ATTEMPTS, "retryable_api_codes": sorted(RETRYABLE_API_CODES),
            "max_apply_attempts": self.max_apply_attempts,
            "selection_hash": S.selection_hash(self.task_ids), "tasks": self.task_ids,
            "e1_instructions_sha256": P.E1_INSTRUCTIONS_SHA256, "o1_instructions_sha256": P.O1_INSTRUCTIONS_SHA256,
            "n_conditions": len(recs), "conditions": recs,
        }

    @staticmethod
    def _core_sha(manifest: dict) -> str:
        core = {k: v for k, v in manifest.items() if k not in ("run_id", "created_utc", "manifest_core_sha256")}
        return sha256_bytes(canonical(core))

    def _open(self) -> dict:
        """Crea la ejecucion o, si existe, verifica su integridad y su compatibilidad con la configuracion actual."""
        core = self._prepare()
        mpath = self.out / MANIFEST
        self.out.mkdir(parents=True, exist_ok=True)
        if mpath.exists():
            existing = json.loads(mpath.read_bytes().decode("utf-8"))
            if existing.get("manifest_core_sha256") != self._core_sha(existing) or self._core_sha(existing) != self._core_sha(core):
                raise IntegrityError("el manifiesto existente no coincide con la configuracion actual (protocolo, modelo, "
                                     "seleccion o prompts)")
            rep = self.verify()
            if not rep.ok:
                raise IntegrityError("la ejecucion existente no supera la verificacion: " + "; ".join(rep.errors[:5]))
            self.log.load()
            self.manifest = existing
            self.log.append("run_resumed", run_id=existing["run_id"], warnings=len(rep.warnings))
            return existing
        run_id = f"p1-{'sim' if self.synthetic else 'real'}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        manifest = dict(core, run_id=run_id, created_utc=self.clock())
        manifest["manifest_core_sha256"] = self._core_sha(manifest)
        data = canonical(manifest)
        write_new(mpath, data)
        (self.out / COND_DIR).mkdir(exist_ok=True)
        self.log.load()
        self.log.append("run_started", run_id=run_id, manifest_sha256=sha256_bytes(data), synthetic=self.synthetic)
        self.manifest = manifest
        return manifest

    # ---- ejecucion -----------------------------------------------------------------------------
    def run(self, max_new_generations: Optional[int] = None) -> Dict[str, int]:
        """Ejecuta (o reanuda) la ejecucion. ``max_new_generations`` limita las llamadas nuevas (para pruebas)."""
        self.out.mkdir(parents=True, exist_ok=True)
        lock = self.out / LOCK
        try:
            with open(lock, "xb") as fh:
                fh.write(f"pid={os.getpid()}\n".encode())
        except FileExistsError:
            raise OrchestrationError(f"hay otra ejecucion en curso o un bloqueo previo: {lock}") from None
        try:
            self._open()
            stats = {"new_generations": 0, "skipped_generations": 0, "derived_written": 0, "not_evaluable": 0}
            for c in self.conditions:
                if max_new_generations is not None and stats["new_generations"] >= max_new_generations:
                    break
                self._process(c, stats)
            return stats
        finally:
            if lock.exists():
                lock.unlink()

    def _cdir(self, c: Condition) -> Path:
        d = self.out / COND_DIR / c.cond_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _events_for(self, cond_id: str) -> List[dict]:
        return [e for e in EventLog.read(self.out / EVENTS) if e.get("cond_id") == cond_id]

    def _process(self, c: Condition, stats: Dict[str, int]) -> None:
        d = self._cdir(c)
        prompt = self.prompts[c.cond_id]
        pbytes = P.serialize_prompt(prompt)
        pfile = d / "prompt.txt"
        if pfile.exists():
            if pfile.read_bytes() != pbytes:
                raise IntegrityError(f"{c.cond_id}: prompt.txt no coincide con el prompt reconstruido")
        else:
            write_new(pfile, pbytes)
            self.log.append("prompt_written", cond_id=c.cond_id, prompt_sha256=sha256_bytes(pbytes))

        gen, gfail = d / "generation.json", d / "generation_failed.json"
        if gfail.exists():
            stats["not_evaluable"] += 1
            return
        if gen.exists():
            stats["skipped_generations"] += 1
        else:
            if (d / "response.txt").exists():
                self._seal_recovered(c, d)
                stats["skipped_generations"] += 1
            else:
                evs = [e["type"] for e in self._events_for(c.cond_id)]
                if "api_attempt_started" in evs:
                    if self.on_interrupted == "stop":
                        raise InterruptedConditionError(
                            f"{c.cond_id}: hay una llamada iniciada sin respuesta guardada; decision manual (no se repite sola)")
                    self.log.append("interrupted_retry", cond_id=c.cond_id)
                self._generate(c, d, prompt, pbytes, stats)
                if gfail.exists():
                    stats["not_evaluable"] += 1
                    return
        self._derive(c, d, stats)

    def _generate(self, c: Condition, d: Path, prompt: str, pbytes: bytes, stats: Dict[str, int]) -> None:
        attempts: List[dict] = []
        started = self.clock()
        for n in range(1, MAX_API_ATTEMPTS + 1):
            self.log.append("api_attempt_started", cond_id=c.cond_id, attempt=n)
            try:
                resp: ClientResponse = self.client.generate(prompt, model=MODEL, max_output_tokens=MAX_OUTPUT_TOKENS,
                                                            thinking_level=THINKING_LEVEL)
            except APIError as exc:
                retryable = exc.code in RETRYABLE_API_CODES
                attempts.append({"attempt": n, "outcome": "api_error", "code": exc.code, "retryable": retryable})
                self.log.append("api_attempt_failed", cond_id=c.cond_id, attempt=n, code=exc.code, retryable=retryable)
                if not retryable or n == MAX_API_ATTEMPTS:
                    rec = {"schema_version": SCHEMA_VERSION, "cond_id": c.cond_id, "synthetic": self.synthetic,
                           "category": "infrastructure_not_evaluable", "status": "api_error", "attempts": attempts,
                           "prompt_sha256": sha256_bytes(pbytes), "started": started, "finished": self.clock()}
                    write_new(d / "generation_failed.json", canonical(rec))
                    self.log.append("condition_not_evaluable", cond_id=c.cond_id, reason="api_error", stage="generation")
                    return
                self.sleep(10 * n)
                continue
            attempts.append({"attempt": n, "outcome": "response"})
            text = resp.text if resp.text is not None else ""
            rbytes = text.encode("utf-8")
            self.log.append("api_response_received", cond_id=c.cond_id, attempt=n, response_sha256=sha256_bytes(rbytes),
                            usage=self._usage(resp), model_version=resp.model_version, text_was_none=resp.text is None)
            write_new(d / "response.txt", rbytes)             # respuesta original, sin tocar
            self._write_generation(c, d, pbytes, rbytes, attempts, resp, started)
            stats["new_generations"] += 1
            return

    @staticmethod
    def _usage(resp: ClientResponse) -> dict:
        return {"input": resp.input_tokens, "output": resp.output_tokens, "thinking": resp.thinking_tokens,
                "total": resp.total_tokens}

    def _write_generation(self, c, d, pbytes, rbytes, attempts, resp, started, recovered=False) -> None:
        empty = not rbytes.decode("utf-8").strip()
        rec = {"schema_version": SCHEMA_VERSION, "cond_id": c.cond_id, "pair_id": c.pair_id, "task_id": c.task_id,
               "method": c.method, "arm": c.arm, "synthetic": self.synthetic, "run_id": self.manifest["run_id"],
               "protocol_version": PROTOCOL_VERSION, "model": MODEL, "max_output_tokens": MAX_OUTPUT_TOKENS,
               "thinking_level": THINKING_LEVEL, "prompt_sha256": sha256_bytes(pbytes),
               "response_sha256": sha256_bytes(rbytes), "response_bytes": len(rbytes),
               "status": "empty_response" if empty else "ok",
               "category": "model_output_error" if empty else "ok", "attempts": attempts,
               "usage": self._usage(resp) if resp else None, "model_version": resp.model_version if resp else None,
               "finish_reason": resp.finish_reason if resp else None, "recovered_from_event": recovered,
               "started": started, "finished": self.clock()}
        data = canonical(rec)
        write_new(d / "generation.json", data)
        self.log.append("generation_sealed", cond_id=c.cond_id, generation_sha256=sha256_bytes(data),
                        response_sha256=rec["response_sha256"], status=rec["status"])

    def _seal_recovered(self, c: Condition, d: Path) -> None:
        """response.txt existe pero no se sello: se recupera el sello desde el evento api_response_received si coincide."""
        rbytes = (d / "response.txt").read_bytes()
        evs = [e for e in self._events_for(c.cond_id) if e["type"] == "api_response_received"]
        if not evs or evs[-1]["response_sha256"] != sha256_bytes(rbytes):
            raise IntegrityError(f"{c.cond_id}: response.txt sin sellar y sin evento que lo respalde")
        u = evs[-1]["usage"]
        resp = ClientResponse(text=rbytes.decode("utf-8"), input_tokens=u["input"], output_tokens=u["output"],
                              thinking_tokens=u["thinking"], total_tokens=u["total"], model_version=evs[-1]["model_version"])
        self._write_generation(c, d, (d / "prompt.txt").read_bytes(), rbytes, [{"attempt": evs[-1]["attempt"],
                                                                                "outcome": "response"}], resp, self.clock(), True)

    # ---- etapas derivadas (deterministas, sin llamar al modelo) ---------------------------------
    def _derive(self, c: Condition, d: Path, stats: Dict[str, int]) -> None:
        rbytes = (d / "response.txt").read_bytes()
        rsha = sha256_bytes(rbytes)
        response = rbytes.decode("utf-8")
        if not (d / "format_metrics.json").exists():
            write_new(d / "format_metrics.json", canonical({"cond_id": c.cond_id, "response_sha256": rsha,
                                                             "synthetic": self.synthetic, **format_metrics(response, c.arm)}))
            self.log.append("stage_written", cond_id=c.cond_id, stage="format_metrics")
            stats["derived_written"] += 1
        if c.arm == "O1":
            if not (d / "normalization.json").exists():
                self._normalize(c, d, response, rsha)
                stats["derived_written"] += 1
        elif not (d / "conversion.json").exists():
            self._convert(c, d, response, rsha)
            stats["derived_written"] += 1

    def _normalize(self, c, d, response, rsha) -> None:
        o1 = original_style_patch(response)
        r = normalize_patch(o1)
        write_new(d / "o1.patch", o1.encode("utf-8"))
        write_new(d / "o1n.patch", r.patch.encode("utf-8"))
        write_new(d / "normalization.json", canonical({
            "cond_id": c.cond_id, "response_sha256": rsha, "synthetic": self.synthetic, "stage": "normalization",
            "o1_patch_sha256": sha256_text(o1), "o1n_patch_sha256": sha256_text(r.patch), "status": r.status,
            "changed": r.changed, "detail": r.detail, "category": "ok",
            "applicability": "pending_phase_3B", "resolution": "pending_phase_3B"}))
        self.log.append("stage_written", cond_id=c.cond_id, stage="normalization", status=r.status)

    def _source(self, task_id: str):
        if task_id not in self._sources:
            self._sources[task_id] = self.source_factory(task_id)
        return self._sources[task_id]

    def _convert(self, c, d, response, rsha) -> None:
        """Conversion E1 -> diff con hasta ``max_apply_attempts`` intentos SOLO ante environment_error (misma respuesta)."""
        attempts, result = [], None
        for n in range(1, self.max_apply_attempts + 1):
            try:
                result = A.apply_text(response, self._source(c.task_id))
            except (A.SourceError, OSError) as exc:                    # fallo del entorno al abrir la fuente
                self._sources.pop(c.task_id, None)
                result = A.ApplyResult(A.ENV_ERROR, str(exc))
            attempts.append({"attempt": n, "status": result.status, "detail": result.detail if not result.ok else ""})
            if result.status != A.ENV_ERROR:
                break
            self.log.append("apply_infra_retry", cond_id=c.cond_id, attempt=n, detail=result.detail[:200])
        infra = result.status == A.ENV_ERROR
        rec = {"cond_id": c.cond_id, "response_sha256": rsha, "synthetic": self.synthetic, "stage": "conversion",
               "status": "not_evaluable_infrastructure" if infra else result.status,
               "category": "infrastructure_not_evaluable" if infra else ("ok" if result.ok else "model_output_error"),
               "model_fault": result.model_fault, "detail": result.detail, "attempts": attempts,
               "n_attempts": len(attempts), "recovered_after_retry": (not infra) and len(attempts) > 1,
               "blocks": [{"index": o.index, "path": o.path, "status": o.status, "match_level": o.match_level,
                           "start_line": o.start_line} for o in result.outcomes],
               "diff_sha256": result.diff_sha256 if result.ok else None, "files": sorted(result.files),
               "applicability": "pending_phase_3B", "resolution": "pending_phase_3B"}
        if result.ok:
            write_new(d / "diff.patch", result.diff_bytes)
        write_new(d / "conversion.json", canonical(rec))
        self.log.append("stage_written", cond_id=c.cond_id, stage="conversion", status=rec["status"])
        if infra:
            self.log.append("condition_not_evaluable", cond_id=c.cond_id, reason="environment_error", stage="conversion")


    # ---- aplicabilidad (filtro comun G) y evaluacion funcional (fase 3B.1) -----------------------
    def _locked(self, fn):
        """Ejecuta ``fn`` con el bloqueo de la ejecucion, tras verificar la integridad de una ejecucion YA existente."""
        if not (self.out / MANIFEST).is_file():
            raise OrchestrationError("no existe la ejecucion (falta RUN_MANIFEST.json): ejecute antes run()")
        lock = self.out / LOCK
        try:
            with open(lock, "xb") as fh:
                fh.write(f"pid={os.getpid()}\n".encode())
        except FileExistsError:
            raise OrchestrationError(f"hay otra ejecucion en curso o un bloqueo previo: {lock}") from None
        try:
            self._open()
            return fn()
        finally:
            if lock.exists():
                lock.unlink()

    def _patch_artifact(self, c: Condition, d: Path):
        """(nombre, bytes|None, registro_previo) del parche que entra en G, o None si aun no existe la etapa previa."""
        if c.arm == "O1":
            if not (d / "normalization.json").exists():
                return None
            return "o1n.patch", (d / "o1n.patch").read_bytes(), json.loads((d / "normalization.json").read_bytes())
        if not (d / "conversion.json").exists():
            return None
        up = json.loads((d / "conversion.json").read_bytes())
        return ("diff.patch", (d / "diff.patch").read_bytes(), up) if up["status"] == "patch_ready" else (None, None, up)

    def apply_gate(self) -> Dict[str, int]:
        """Aplica G a todas las condiciones con parche disponible. Reanudable: no repite ni sobrescribe ``applicability.json``."""
        def go():
            stats = {"gate_written": 0, "gate_skipped": 0, "upstream_missing": 0}
            for c in self.conditions:
                d = self.out / COND_DIR / c.cond_id
                if (d / "applicability.json").exists():
                    stats["gate_skipped"] += 1
                    continue
                if not (d / "generation.json").exists() or self._patch_artifact(c, d) is None:
                    stats["upstream_missing"] += 1
                    continue
                self._gate_condition(c, d)
                stats["gate_written"] += 1
            return stats
        return self._locked(go)

    def _gate_condition(self, c: Condition, d: Path) -> None:
        name, data, up = self._patch_artifact(c, d)
        rec = {"cond_id": c.cond_id, "pair_id": c.pair_id, "task_id": c.task_id, "method": c.method, "arm": c.arm,
               "synthetic": self.synthetic, "stage": "applicability", "filter": "G",
               "policy": {"command": GATE.GATE_COMMAND + ["<patch_file>"], "patch_bytes_unmodified": True,
                          "tree": "copia temporal de los ficheros que toca el parche, leidos como blobs del base_commit",
                          "same_policy_for_O1n_and_E1": True, "max_attempts": self.max_apply_attempts,
                          "retry_only": "environment_error"},
               "input_artifact": name, "response_sha256": up["response_sha256"],
               "upstream": {"stage": up["stage"], "status": up["status"], "category": up["category"]},
               "functional": "pending"}
        if data is None:                                            # E1 sin parche: no hay nada que aplicar
            infra = up["category"] == "infrastructure_not_evaluable"
            rec.update(status="not_evaluable_infrastructure" if infra else GATE.NOT_APPLICABLE,
                       category="infrastructure_not_evaluable" if infra else "model_output_error",
                       reason=f"conversion:{up['status']}", patch_sha256=None, attempts=[], paths=[], git_version="")
            rec["functional"] = "not_applicable"
        else:
            res = GATE.gate_check(data, lambda: self._source(c.task_id), max_attempts=self.max_apply_attempts)
            for a in res.attempts:
                if a.status == GATE.ENV_ERROR:
                    self.log.append("apply_infra_retry", cond_id=c.cond_id, stage="applicability", attempt=a.attempt,
                                    detail=(a.detail or a.stderr)[:200])
            infra = res.status == GATE.ENV_ERROR
            rec.update(status="not_evaluable_infrastructure" if infra else res.status, category=res.category,
                       reason=res.reason, patch_sha256=res.patch_sha256, paths=res.paths, git_version=res.git_version,
                       unmaterialized=res.unmaterialized,
                       attempts=[{"attempt": a.attempt, "status": a.status, "command": a.command[:-1] + ["<patch_file>"],
                                  "returncode": a.returncode, "stdout": a.stdout.replace(a.command[-1], "<patch_file>"),
                                  "stderr": a.stderr.replace(a.command[-1], "<patch_file>"), "detail": a.detail,
                                  "duration_s": round(a.duration_s, 4)} for a in res.attempts])
            rec["recovered_after_retry"] = (not infra) and len(res.attempts) > 1
            rec["functional"] = "pending" if res.status == GATE.APPLICABLE else "not_applicable"
        rec["n_attempts"] = len(rec["attempts"])
        write_new(d / "applicability.json", canonical(rec))
        self.log.append("stage_written", cond_id=c.cond_id, stage="applicability", status=rec["status"])
        if rec["status"] == "not_evaluable_infrastructure":
            self.log.append("condition_not_evaluable", cond_id=c.cond_id, reason="environment_error", stage="applicability")

    def evaluate_functional(self, evaluator=None) -> Dict[str, int]:
        """Evalua funcionalmente los parches aplicables (solo evaluadores sinteticos en 3B.1). Reanudable, sin duplicados."""
        ev = evaluator if evaluator is not None else self.functional_evaluator
        if ev is None:
            raise OrchestrationError("no hay evaluador funcional configurado")
        FUN.check_evaluator_allowed(ev, synthetic_run=self.synthetic)

        def go():
            stats = {"evaluated": 0, "skipped": 0, "not_applicable": 0, "pending_gate": 0, "not_evaluable": 0}
            run_id = self.manifest["run_id"]
            for c in self.conditions:
                d = self.out / COND_DIR / c.cond_id
                if not (d / "applicability.json").exists():
                    stats["pending_gate"] += 1
                    continue
                app = json.loads((d / "applicability.json").read_bytes())
                if app["status"] != GATE.APPLICABLE:
                    stats["not_applicable"] += 1
                    continue
                if (d / "functional.json").exists():
                    stats["skipped"] += 1
                    continue
                self._functional_condition(c, d, app, ev, run_id)
                stats["evaluated"] += 1
                stats["not_evaluable"] += json.loads((d / "functional.json").read_bytes())["outcome"] == FUN.NOT_EVALUABLE
            return stats
        return self._locked(go)

    def _functional_condition(self, c: Condition, d: Path, app: dict, ev, run_id: str) -> None:
        info = self.task_info_provider(c.task_id) or {}
        req = FUN.EvalRequest(cond_id=c.cond_id, pair_id=c.pair_id, task_id=c.task_id, method=c.method, arm=c.arm,
                              patch_path=str(d / app["input_artifact"]), patch_sha256=app["patch_sha256"],
                              run_label=f"{run_id}-{c.cond_id}", repo=info.get("repo"), base_commit=info.get("base_commit"))
        started, attempts, resp = self.clock(), [], None
        for n in range(1, self.max_apply_attempts + 1):
            try:
                resp = ev.evaluate(req)
                attempts.append({"attempt": n, "outcome": resp.outcome, "detail": resp.detail[:300]})
            except FUN.EvaluatorInfraError as exc:
                resp = None
                attempts.append({"attempt": n, "outcome": FUN.INFRA_ERROR, "detail": str(exc)[:300]})
            if resp is not None and resp.outcome in (FUN.RESOLVED, FUN.NOT_RESOLVED):
                break
            self.log.append("apply_infra_retry", cond_id=c.cond_id, stage="functional", attempt=n)
        ok = resp is not None and resp.outcome in (FUN.RESOLVED, FUN.NOT_RESOLVED)
        outcome = resp.outcome if ok else FUN.NOT_EVALUABLE
        evidence = {} if resp is None else dict(resp.evidence)
        edata = json.dumps({"cond_id": c.cond_id, "synthetic": self.synthetic, "evidence": evidence}, sort_keys=True,
                           ensure_ascii=False, default=str)
        truncated = len(edata) > EVIDENCE_LIMIT
        edata_b = (edata[:EVIDENCE_LIMIT] if truncated else edata).encode("utf-8")
        write_new(d / "functional_evidence.json", edata_b + b"\n")
        rec = {"cond_id": c.cond_id, "pair_id": c.pair_id, "arm": c.arm, "synthetic": self.synthetic, "stage": "functional",
               "evaluator": {"name": ev.name, "version": ev.version, "is_synthetic": bool(ev.is_synthetic)},
               "request": {"task_id": req.task_id, "method": req.method, "run_label": req.run_label, "repo": req.repo,
                           "base_commit": req.base_commit, "patch_artifact": app["input_artifact"],
                           "patch_sha256": req.patch_sha256},
               "applicability_sha256": sha256_bytes((d / "applicability.json").read_bytes()),
               "outcome": outcome, "category": "ok" if ok else "infrastructure_not_evaluable", "attempts": attempts,
               "n_attempts": len(attempts), "recovered_after_retry": ok and len(attempts) > 1,
               "evidence_sha256": sha256_bytes(edata_b + b"\n"), "evidence_truncated": truncated,
               "started": started, "finished": self.clock()}
        write_new(d / "functional.json", canonical(rec))
        self.log.append("stage_written", cond_id=c.cond_id, stage="functional", status=outcome)
        if not ok:
            self.log.append("condition_not_evaluable", cond_id=c.cond_id, reason="evaluator_infrastructure", stage="functional")

    # ---- pares y decision ----------------------------------------------------------------------
    def pair_results(self) -> List[DEC.PairResult]:
        """Un ``PairResult`` por (tarea, metodo) a partir de G y del formato. ``None`` = no evaluable por infraestructura."""
        out = []
        for c in self.conditions:
            if c.arm != "O1":
                continue
            e1 = self.out / COND_DIR / f"{c.pair_id}-E1"
            o1 = self.out / COND_DIR / c.cond_id

            def passed(d: Path):
                if (d / "generation_failed.json").exists():
                    return None
                f = d / "applicability.json"
                if not f.exists():
                    raise OrchestrationError(f"aplicabilidad pendiente en {d.name}: ejecute apply_gate()")
                s = json.loads(f.read_bytes())["status"]
                return None if s == "not_evaluable_infrastructure" else s == GATE.APPLICABLE

            parse = None
            if (e1 / "format_metrics.json").exists():
                parse = bool(json.loads((e1 / "format_metrics.json").read_bytes())["parse"]["parseable"])
            out.append(DEC.PairResult(c.task_id, c.method, passed(e1), passed(o1), parse))
        return out

    def decision_report(self) -> dict:
        """Decision del protocolo (``decision.evaluate``); exige las 36 condiciones. Con datos sinteticos no es un resultado."""
        rep = DEC.evaluate(self.pair_results())
        rep["synthetic"] = self.synthetic
        return rep

    # ---- verificacion --------------------------------------------------------------------------
    def verify(self, recompute: bool = False) -> VerifyReport:
        rep = VerifyReport()
        mpath = self.out / MANIFEST
        if not mpath.is_file():
            rep.errors.append("falta RUN_MANIFEST.json")
            return rep
        mraw = mpath.read_bytes()
        try:
            manifest = json.loads(mraw.decode("utf-8"))
        except ValueError:
            rep.errors.append("RUN_MANIFEST.json no es JSON valido")
            return rep
        if manifest.get("manifest_core_sha256") != self._core_sha(manifest):
            rep.errors.append("el manifiesto fue alterado (hash del nucleo)")
        self._manifest_synthetic = manifest.get("synthetic")
        try:
            events = EventLog.read(self.out / EVENTS)
        except (IntegrityError, FileNotFoundError) as exc:
            rep.errors.append(str(exc) if isinstance(exc, IntegrityError) else "falta events.jsonl")
            return rep
        if not events or events[0]["type"] != "run_started" or events[0].get("manifest_sha256") != sha256_bytes(mraw):
            rep.errors.append("el primer evento no respalda el manifiesto")
        cdir = self.out / COND_DIR
        known = {r["cond_id"]: r for r in manifest["conditions"]}
        gen_events = {e["cond_id"]: e for e in events if e["type"] == "generation_sealed"}
        n_sealed = 0
        for d in sorted(p for p in cdir.iterdir()) if cdir.is_dir() else []:
            rec = known.get(d.name)
            if rec is None:
                rep.errors.append(f"directorio de condicion desconocido: {d.name}")
                continue
            arm_files = FILES_COMMON | (FILES_E1 if rec["arm"] == "E1" else FILES_O1)
            names = {p.name for p in d.iterdir()}
            for nm in sorted(names):
                if nm.endswith(".tmp"):
                    rep.warnings.append(f"{d.name}: temporal de una escritura interrumpida ({nm})")
                elif nm not in arm_files:
                    rep.errors.append(f"{d.name}: fichero inesperado {nm}")
            self._verify_condition(d, rec, names, gen_events.get(d.name), rep, recompute)
            n_sealed += "generation.json" in names
        for cid in gen_events:
            if not (cdir / cid / "generation.json").exists():
                rep.errors.append(f"{cid}: evento generation_sealed sin generation.json")
        rep.stats = {"conditions_dirs": len(list(cdir.iterdir())) if cdir.is_dir() else 0, "sealed": n_sealed,
                     "events": len(events)}
        return rep

    def _verify_condition(self, d: Path, rec: dict, names: set, gen_event, rep: VerifyReport, recompute: bool) -> None:
        cid = d.name

        def read_json(name):
            try:
                obj = json.loads((d / name).read_bytes().decode("utf-8"))
            except ValueError:
                rep.errors.append(f"{cid}: {name} no es JSON valido")
                return None
            if isinstance(obj, dict) and obj.get("synthetic") != self._manifest_synthetic:
                rep.errors.append(f"{cid}: {name} mezcla resultados sinteticos y reales (synthetic != manifiesto)")
            return obj

        if "prompt.txt" in names and sha256_bytes((d / "prompt.txt").read_bytes()) != rec["prompt_sha256"]:
            rep.errors.append(f"{cid}: prompt.txt no coincide con el manifiesto")
        if "generation.json" in names and "generation_failed.json" in names:
            rep.errors.append(f"{cid}: generation.json y generation_failed.json a la vez")
        if "response.txt" in names and "generation.json" not in names:
            rep.warnings.append(f"{cid}: response.txt sin sellar (se recuperara desde el evento)")
        gen = None
        if "generation.json" in names:
            gen = read_json("generation.json")
            if gen is not None:
                if "response.txt" not in names:
                    rep.errors.append(f"{cid}: generation.json sin response.txt")
                elif sha256_bytes((d / "response.txt").read_bytes()) != gen["response_sha256"]:
                    rep.errors.append(f"{cid}: response.txt no coincide con su hash sellado (corrupto o modificado)")
                if gen["prompt_sha256"] != rec["prompt_sha256"]:
                    rep.errors.append(f"{cid}: generation.json con otro prompt")
                if gen_event is None or gen_event["generation_sha256"] != sha256_bytes((d / "generation.json").read_bytes()):
                    rep.errors.append(f"{cid}: generation.json no coincide con el evento que lo sello")
        for stage in ("format_metrics.json", "conversion.json", "normalization.json"):
            if stage in names and gen is not None:
                s = read_json(stage)
                if s is not None and s.get("response_sha256") != gen["response_sha256"]:
                    rep.errors.append(f"{cid}: {stage} no corresponde a la respuesta sellada")
                if s is not None and stage == "conversion.json" and s.get("diff_sha256"):
                    if "diff.patch" not in names or sha256_bytes((d / "diff.patch").read_bytes()) != s["diff_sha256"]:
                        rep.errors.append(f"{cid}: diff.patch no coincide con conversion.json")
                if s is not None and stage == "normalization.json":
                    for pn, key in (("o1.patch", "o1_patch_sha256"), ("o1n.patch", "o1n_patch_sha256")):
                        if pn not in names or sha256_bytes((d / pn).read_bytes()) != s[key]:
                            rep.errors.append(f"{cid}: {pn} no coincide con normalization.json")
            elif stage in names and gen is None:
                rep.errors.append(f"{cid}: {stage} sin generacion sellada")
        self._verify_stage2(d, rec, names, gen, read_json, rep, recompute)
        if recompute and gen is not None and "response.txt" in names:
            response = (d / "response.txt").read_bytes().decode("utf-8")
            if "format_metrics.json" in names:
                stored = read_json("format_metrics.json")
                again = {"cond_id": cid, "response_sha256": gen["response_sha256"], "synthetic": self.synthetic,
                         **format_metrics(response, rec["arm"])}
                if stored != json.loads(canonical(again)):
                    rep.errors.append(f"{cid}: format_metrics.json no se reproduce al recalcular")
            if "normalization.json" in names:
                r = normalize_patch(original_style_patch(response))
                if read_json("normalization.json").get("status") != r.status:
                    rep.errors.append(f"{cid}: normalization.json no se reproduce al recalcular")

    def _verify_stage2(self, d: Path, rec: dict, names: set, gen, read_json, rep: VerifyReport, recompute: bool) -> None:
        cid = d.name
        app = None
        if "applicability.json" in names:
            app = read_json("applicability.json")
            if app is not None:
                if gen is None or app.get("response_sha256") != gen["response_sha256"]:
                    rep.errors.append(f"{cid}: applicability.json no corresponde a la respuesta sellada")
                art = app.get("input_artifact")
                if art:
                    if art not in names or sha256_bytes((d / art).read_bytes()) != app.get("patch_sha256"):
                        rep.errors.append(f"{cid}: el parche de entrada de G no coincide con applicability.json ({art})")
                elif app.get("status") == GATE.APPLICABLE:
                    rep.errors.append(f"{cid}: applicability.json aplicable sin parche")
                if recompute and art and art in names and app.get("status") != "not_evaluable_infrastructure":
                    res = GATE.gate_check((d / art).read_bytes(), lambda: self._source(rec["task_id"]),
                                          max_attempts=self.max_apply_attempts)
                    if res.status != GATE.ENV_ERROR and res.status != app["status"]:
                        rep.errors.append(f"{cid}: applicability.json no se reproduce al recalcular G")
        if "functional.json" in names:
            fun = read_json("functional.json")
            if app is None or app.get("status") != GATE.APPLICABLE:
                rep.errors.append(f"{cid}: functional.json sin aplicabilidad aprobada por G")
            elif fun is not None:
                if fun["request"]["patch_sha256"] != app["patch_sha256"]:
                    rep.errors.append(f"{cid}: functional.json evalua otro parche distinto del aprobado por G")
                if fun.get("applicability_sha256") != sha256_bytes((d / "applicability.json").read_bytes()):
                    rep.errors.append(f"{cid}: functional.json no corresponde a applicability.json")
                if not fun["request"]["run_label"].startswith("p1-"):
                    rep.errors.append(f"{cid}: identificador de evaluacion no propio de P1")
                if "functional_evidence.json" not in names or \
                        sha256_bytes((d / "functional_evidence.json").read_bytes()) != fun.get("evidence_sha256"):
                    rep.errors.append(f"{cid}: functional_evidence.json no coincide con functional.json")
        elif "functional_evidence.json" in names:
            rep.errors.append(f"{cid}: functional_evidence.json sin functional.json")
        if "applicability.json" in names:
            ev = d / "functional_evidence.json"
            if ev.exists():
                read_json("functional_evidence.json")

    # ---- resumen -------------------------------------------------------------------------------
    def _summary_stage2(self, d: Path, r: dict, out: dict, not_eval: set) -> None:
        if not (d / "generation.json").exists():
            return
        st = out["stages"]
        if not (d / "applicability.json").exists():
            if (d / "conversion.json").exists() or (d / "normalization.json").exists():
                st["applicability"]["pending"] += 1
                out["by_arm"][r["arm"]]["pending"] += 1
            return
        a = json.loads((d / "applicability.json").read_bytes())
        st["applicability"][a["status"]] += 1
        out["by_arm"][r["arm"]][a["status"]] += 1
        out["gate_infrastructure"]["retries"] += max(a["n_attempts"] - 1, 0)
        out["gate_infrastructure"]["recovered_after_retry"] += bool(a.get("recovered_after_retry"))
        if a["status"] == "not_evaluable_infrastructure":
            not_eval.add(r["cond_id"])                                    # afecta a la decision: el par queda excluido
        if a["status"] != GATE.APPLICABLE:
            st["functional"]["not_applicable"] += 1
            return
        if not (d / "functional.json").exists():
            st["functional"]["pending"] += 1
            return
        f = json.loads((d / "functional.json").read_bytes())
        st["functional"][f["outcome"]] += 1
        out["functional_infrastructure"]["retries"] += f["n_attempts"] - 1
        out["functional_infrastructure"]["recovered_after_retry"] += bool(f["recovered_after_retry"])
        out["functional_infrastructure"]["not_evaluable"] += f["outcome"] == FUN.NOT_EVALUABLE   # NO excluye el par (sin criterio)

    def summary(self) -> dict:
        """Resumen separado por etapa y por tipo de error (modelo / infraestructura / no evaluable)."""
        cdir = self.out / COND_DIR
        manifest = json.loads((self.out / MANIFEST).read_bytes().decode("utf-8"))
        out = {"run_id": manifest["run_id"], "synthetic": manifest["synthetic"], "n_conditions": manifest["n_conditions"],
               "stages": {"generation": 0, "format_metrics": 0, "conversion_E1": 0, "normalization_O1": 0,
                          "applicability": {"applicable": 0, "not_applicable": 0, "not_evaluable_infrastructure": 0, "pending": 0},
                          "functional": {"resolved": 0, "not_resolved": 0, "not_evaluable": 0, "pending": 0,
                                         "not_applicable": 0}},
               "by_arm": {a: {"applicable": 0, "not_applicable": 0, "not_evaluable_infrastructure": 0, "pending": 0}
                          for a in ARMS},
               "gate_infrastructure": {"retries": 0, "recovered_after_retry": 0},
               "functional_infrastructure": {"retries": 0, "recovered_after_retry": 0, "not_evaluable": 0,
                                             "pause_recommended": False},
               "model_output_errors": {}, "infrastructure": {"api_failures": 0, "apply_retries": 0, "recovered_after_retry": 0},
               "not_evaluable_conditions": [], "format": {"external_fences": 0, "inner_fences": 0, "wraps_response": 0,
                                                          "fences_union": 0, "original_metric_a": 0,
                                                          "e1_parseable": 0, "e1_with_fences_and_parseable": 0},
               "statuses": {}}
        not_eval = set()
        for r in manifest["conditions"]:
            d = cdir / r["cond_id"]
            if (d / "generation_failed.json").exists():
                g = json.loads((d / "generation_failed.json").read_bytes())
                out["infrastructure"]["api_failures"] += len(g["attempts"])
                not_eval.add(r["cond_id"])
                continue
            if not (d / "generation.json").exists():
                continue
            out["stages"]["generation"] += 1
            g = json.loads((d / "generation.json").read_bytes())
            if g["category"] == "model_output_error":
                out["model_output_errors"]["empty_response"] = out["model_output_errors"].get("empty_response", 0) + 1
            out["infrastructure"]["api_failures"] += sum(1 for a in g["attempts"] if a["outcome"] == "api_error")
            if (d / "format_metrics.json").exists():
                out["stages"]["format_metrics"] += 1
                f = json.loads((d / "format_metrics.json").read_bytes())
                out["format"]["external_fences"] += f["external_fences_present"]
                out["format"]["inner_fences"] += f["inner_fences_present"]
                out["format"]["wraps_response"] += f["wraps_response"]
                out["format"]["fences_union"] += f["fences_union_present"]
                out["format"]["original_metric_a"] += f["original_metric_a_present"]
                if r["arm"] == "E1":
                    out["format"]["e1_parseable"] += bool(f["parse"]["parseable"])
                    out["format"]["e1_with_fences_and_parseable"] += f["fences_and_parseable"]
            for stage, key in (("conversion.json", "conversion_E1"), ("normalization.json", "normalization_O1")):
                if (d / stage).exists():
                    out["stages"][key] += 1
                    s = json.loads((d / stage).read_bytes())
                    out["statuses"][f"{r['arm']}:{s['status']}"] = out["statuses"].get(f"{r['arm']}:{s['status']}", 0) + 1
                    if s["category"] == "model_output_error":
                        out["model_output_errors"][s["status"]] = out["model_output_errors"].get(s["status"], 0) + 1
                    if s["category"] == "infrastructure_not_evaluable":
                        not_eval.add(r["cond_id"])
                    if stage == "conversion.json":
                        out["infrastructure"]["apply_retries"] += s["n_attempts"] - 1
                        out["infrastructure"]["recovered_after_retry"] += bool(s["recovered_after_retry"])
            self._summary_stage2(d, r, out, not_eval)
        fx = out["functional_infrastructure"]
        evaluated = out["stages"]["functional"]["resolved"] + out["stages"]["functional"]["not_resolved"] + fx["not_evaluable"]
        fx["pause_recommended"] = bool(evaluated) and fx["not_evaluable"] / evaluated > 0.25      # regla del protocolo (25 %)
        out["not_evaluable_conditions"] = sorted(not_eval)
        pairs = {r["pair_id"] for r in manifest["conditions"] if r["cond_id"] in not_eval}
        out["excluded_pairs"] = sorted(pairs)
        out["n_excluded_pairs"] = len(pairs)
        return out
