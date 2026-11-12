"""Interfaz de evaluacion funcional de P1 (fase 3B.1): adaptadores inyectables y evaluador FALSO.

En esta fase NO existe ningun adaptador del evaluador oficial. El evaluador original (``src/downstream/evaluation.py``) no se puede
reutilizar tal cual (ver README, "Efectos secundarios del evaluador original"): hace ``git fetch`` y ``git checkout --force`` sobre los
repositorios de trabajo, usa la red (clone, ``podman pull``, ``load_dataset``), escribe en ``logs/`` con identificadores de ejecucion
fijos y parchea globalmente ``Path.write_text``. Un adaptador futuro (3B.2) tendra que implementar esta misma interfaz en un entorno
aislado.

Resolver o no una tarea es un resultado distinto de la aplicabilidad (G) y no tiene criterio de decision en el protocolo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Union

RESOLVED, NOT_RESOLVED, NOT_EVALUABLE = "resolved", "not_resolved", "not_evaluable"
INFRA_ERROR = "infrastructure_error"


class EvaluatorInfraError(Exception):
    """Fallo de infraestructura del evaluador (contenedor, red, tiempo...). No es un resultado del modelo."""


class OfficialEvaluatorNotAllowed(RuntimeError):
    """Se intento conectar el evaluador original u otro no sintetico en la fase 3B.1."""


@dataclass(frozen=True)
class EvalRequest:
    cond_id: str
    pair_id: str
    task_id: str
    method: str
    arm: str
    patch_path: str
    patch_sha256: str
    run_label: str                       # identificador unico de P1 (prefijo p1-), nunca los run_id originales
    repo: Optional[str] = None
    base_commit: Optional[str] = None


@dataclass
class EvalResponse:
    outcome: str                          # resolved | not_resolved | infrastructure_error
    evidence: Dict[str, object] = field(default_factory=dict)
    detail: str = ""


class FunctionalEvaluator(Protocol):
    is_synthetic: bool
    name: str
    version: str

    def evaluate(self, request: EvalRequest) -> EvalResponse: ...


class FakeFunctionalEvaluator:
    """Evaluador falso. ``script``: lista de respuestas (en orden) o ``responder(request)``; un elemento ``Exception`` se lanza.

    Registra las peticiones recibidas (``calls``). Sus resultados son sinteticos y nunca resultados experimentales."""

    is_synthetic = True
    name = "fake-functional-evaluator"
    version = "1"

    def __init__(self, script: Optional[List[Union[str, EvalResponse, Exception]]] = None,
                 responder: Optional[Callable[[EvalRequest], Union[str, EvalResponse]]] = None):
        self._script = list(script or [])
        self._responder = responder
        self.calls: List[EvalRequest] = []

    def evaluate(self, request: EvalRequest) -> EvalResponse:
        self.calls.append(request)
        if self._script:
            item = self._script.pop(0)
        elif self._responder is not None:
            item = self._responder(request)
        else:
            raise AssertionError("FakeFunctionalEvaluator sin respuestas programadas")
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return EvalResponse(item, {"synthetic": True, "fake_report": {"resolved": item == RESOLVED},
                                       "patch_sha256": request.patch_sha256})
        return item


def check_evaluator_allowed(evaluator, *, synthetic_run: bool) -> None:
    """Impide mezclar resultados sinteticos y reales y conectar el evaluador original por error."""
    module = type(evaluator).__module__ or ""
    if module.startswith("src.") or module == "src" or "swebench" in module:
        raise OfficialEvaluatorNotAllowed(f"evaluador no permitido en 3B.1 (modulo {module})")
    is_syn = bool(getattr(evaluator, "is_synthetic", False))
    if synthetic_run and not is_syn:
        raise OfficialEvaluatorNotAllowed("una ejecucion sintetica solo admite evaluadores sinteticos")
    if not synthetic_run and is_syn:
        raise OfficialEvaluatorNotAllowed("una ejecucion real no admite evaluadores sinteticos")
    if not synthetic_run:
        raise OfficialEvaluatorNotAllowed("en 3B.1 no hay ningun evaluador real habilitado")
    for attr in ("name", "version", "evaluate"):
        if not hasattr(evaluator, attr):
            raise OfficialEvaluatorNotAllowed(f"el evaluador no implementa {attr}")
