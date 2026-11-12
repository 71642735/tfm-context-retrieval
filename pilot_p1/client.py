"""Interfaz de cliente de generacion INYECTABLE para la orquestacion de P1 (fase 3A).

No hay aqui ningun cliente real de API: la fase 3A solo admite clientes sinteticos (``is_synthetic = True``). El
cliente real se anadira en la fase 3B, con autorizacion expresa, implementando la misma interfaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, Tuple, Union

# Mismos valores que src/downstream/generation.py (verificados por una prueba que los lee por AST).
MODEL = "gemini-3.5-flash-lite"
MAX_OUTPUT_TOKENS = 4096
THINKING_LEVEL = "minimal"
MAX_API_ATTEMPTS = 3
RETRYABLE_API_CODES = frozenset({429, 503})


@dataclass(frozen=True)
class ClientResponse:
    text: Optional[str]
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    model_version: Optional[str] = None
    finish_reason: Optional[str] = None


class APIError(Exception):
    """Error de la API; ``code`` es el codigo HTTP. Los transitorios (429, 503) se reintentan."""

    def __init__(self, code: int, message: str = ""):
        super().__init__(f"HTTP {code}: {message}" if message else f"HTTP {code}")
        self.code = code


class GenerationClient(Protocol):
    is_synthetic: bool

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, thinking_level: str) -> ClientResponse: ...


Script = Union[str, ClientResponse, APIError, Callable[[str], Union[str, ClientResponse]]]


class FakeClient:
    """Cliente falso. ``script``: lista de respuestas por llamada (en orden) o ``responder(prompt)``.

    Cada elemento puede ser un ``str``, un ``ClientResponse`` o un ``APIError`` (se lanza). Registra todas las llamadas
    (``calls``) para comprobar la secuencia. Sus respuestas son sinteticas y se marcan como tales en los registros."""

    is_synthetic = True

    def __init__(self, script: Union[List[Script], Callable[[str], Union[str, ClientResponse]], None] = None,
                 responder: Optional[Callable[[str], Union[str, ClientResponse]]] = None):
        self._script = list(script) if isinstance(script, list) else []
        self._responder = script if callable(script) else responder
        self.calls: List[Dict[str, object]] = []

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, thinking_level: str) -> ClientResponse:
        self.calls.append({"prompt": prompt, "model": model, "max_output_tokens": max_output_tokens,
                           "thinking_level": thinking_level})
        if self._script:
            item = self._script.pop(0)
        elif self._responder is not None:
            item = self._responder(prompt)
        else:
            raise AssertionError("FakeClient sin respuestas programadas")
        if isinstance(item, APIError):
            raise item
        if callable(item):
            item = item(prompt)
        if isinstance(item, str) or item is None:
            return ClientResponse(text=item, input_tokens=len(prompt) // 4, output_tokens=len(item or "") // 4,
                                  thinking_tokens=0, total_tokens=(len(prompt) + len(item or "")) // 4,
                                  model_version="fake-synthetic", finish_reason="STOP")
        return item
