"""Regla de decision de P1 con condiciones excluidas por infraestructura (fase 3A; solo logica, sin datos reales).

Los umbrales son los del protocolo congelado (docs/downstream-patch-diagnostics.md, 15.4) y NO se reescalan:
* exito: ``E1`` supera a ``O1n`` en >= 6 condiciones, ``E1`` >= 10 de 36, la diferencia no es negativa en ninguna estrategia
  y es positiva en al menos dos, y >= 80 % de las salidas de ``E1`` son parseables;
* abandono: ``E1`` supera a ``O1n`` en <= 2 condiciones, o ``E1`` < 6 de 36, o < 60 % de salidas parseables;
* inconcluyente: el resto (el abandono tiene prioridad sobre el exito).

Interpretacion FIJADA el 12/11/2026, antes de cualquier generacion experimental (no es un ajuste posterior a resultados):
"``E1`` supera a ``O1n`` en N condiciones" = **mejora neta** = victorias de ``E1`` - victorias de ``O1n``, sobre los pares
evaluables; la diferencia por estrategia se calcula igual. Victoria de ``E1`` = par donde ``E1`` es aplicable y ``O1n`` no;
victoria de ``O1n`` = al reves; empate = ambos aplicables o ambos no aplicables. La parseabilidad se mide sobre las 36
condiciones. ``evaluate`` registra siempre las victorias de cada brazo, los empates y la mejora neta (global y por estrategia).

Condiciones excluidas: un par (tarea, metodo) con un brazo no evaluable por infraestructura queda fuera de la comparacion
pareada. Si alguna forma de completar los datos que faltan cambiase la decision, el resultado es
``inconclusive_by_infrastructure``. Siempre se informa de cuantos pares se excluyeron.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

N_CONDITIONS = 36
SUCCESS_GAIN = 6
SUCCESS_E1_PASSES = 10
ABANDON_GAIN = 2
ABANDON_E1_PASSES = 6
SUCCESS_PARSE = 0.80
ABANDON_PARSE = 0.60
STRATEGIES = ("bm25", "semantic", "hybrid")

SUCCESS, ABANDON, INCONCLUSIVE, INCONCLUSIVE_INFRA = "success", "abandon", "inconclusive", "inconclusive_by_infrastructure"


@dataclass(frozen=True)
class PairResult:
    """Resultado de una condicion (tarea, metodo). ``None`` = desconocido por infraestructura (brazo no evaluable)."""
    task: str
    method: str
    e1_pass: Optional[bool]
    o1n_pass: Optional[bool]
    e1_parseable: Optional[bool]

    @property
    def paired(self) -> bool:
        return self.e1_pass is not None and self.o1n_pass is not None

    @property
    def excluded(self) -> bool:
        return not self.paired or self.e1_parseable is None


def decide(e1_passes: int, gain: int, diffs: Dict[str, int], parse_rate: float) -> str:
    if gain <= ABANDON_GAIN or e1_passes < ABANDON_E1_PASSES or parse_rate < ABANDON_PARSE:
        return ABANDON
    if (gain >= SUCCESS_GAIN and e1_passes >= SUCCESS_E1_PASSES and all(d >= 0 for d in diffs.values())
            and sum(1 for d in diffs.values() if d > 0) >= 2 and parse_rate >= SUCCESS_PARSE):
        return SUCCESS
    return INCONCLUSIVE


def pairwise_counts(pairs: Iterable[PairResult]) -> Dict[str, object]:
    """Victorias de E1 y de O1n, empates y mejora neta sobre los pares evaluables (ambos brazos conocidos)."""
    def blank():
        return {"n_paired": 0, "e1_wins": 0, "o1n_wins": 0, "ties_both_pass": 0, "ties_both_fail": 0, "net_improvement": 0}

    total, by = blank(), {s: blank() for s in STRATEGIES}
    for p in pairs:
        if not p.paired:
            continue
        for c in (total, by[p.method]):
            c["n_paired"] += 1
            if p.e1_pass and not p.o1n_pass:
                c["e1_wins"] += 1
            elif p.o1n_pass and not p.e1_pass:
                c["o1n_wins"] += 1
            elif p.e1_pass:
                c["ties_both_pass"] += 1
            else:
                c["ties_both_fail"] += 1
            c["net_improvement"] = c["e1_wins"] - c["o1n_wins"]
    total["by_strategy"] = by
    return total


def _observed(pairs: Iterable[PairResult]) -> Tuple[int, int, Dict[str, int], float]:
    e1 = gain = par = 0
    diffs = {s: 0 for s in STRATEGIES}
    for p in pairs:
        e1 += bool(p.e1_pass)
        par += bool(p.e1_parseable)
        if p.paired:
            d = int(p.e1_pass) - int(p.o1n_pass)
            gain += d
            diffs[p.method] += d
    return e1, gain, diffs, par / N_CONDITIONS


def _options(p: PairResult) -> Set[Tuple[int, int, int]]:
    e1 = [p.e1_pass] if p.e1_pass is not None else [False, True]
    o1 = [p.o1n_pass] if p.o1n_pass is not None else [False, True]
    pa = [p.e1_parseable] if p.e1_parseable is not None else [False, True]
    return {(int(a), int(b), int(c)) for a in e1 for b in o1 for c in pa if not (a and not c)}


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def _possible_decisions(pairs: List[PairResult]) -> Set[str]:
    per: Dict[str, Set[Tuple[int, int, int]]] = {}
    for s in STRATEGIES:
        reach = {(0, 0, 0)}
        for p in (q for q in pairs if q.method == s):
            reach = {(e + a, d + (a - b), pr + c) for (e, d, pr) in reach for (a, b, c) in _options(p)}
        per[s] = reach
    states = {(0, 0, 0, ())}
    for s in STRATEGIES:
        states = {(E + e, G + d, P + pr, sg + (_sign(d),)) for (E, G, P, sg) in states for (e, d, pr) in per[s]}
    out = set()
    for E, G, P, sg in states:
        out.add(decide(E, G, dict(zip(STRATEGIES, sg)), P / N_CONDITIONS))
    return out


def evaluate(pairs: List[PairResult]) -> Dict[str, object]:
    """Decision con la informacion disponible y comprobacion de si las exclusiones podrian cambiarla."""
    if len(pairs) != N_CONDITIONS or len({(p.task, p.method) for p in pairs}) != N_CONDITIONS:
        raise ValueError(f"se esperan {N_CONDITIONS} pares distintos (tarea, metodo)")
    excluded = [p for p in pairs if p.excluded]
    e1, gain, diffs, parse_rate = _observed(pairs)
    observed = decide(e1, gain, diffs, parse_rate)
    result: Dict[str, object] = {
        "n_pairs": len(pairs), "n_excluded_pairs": len(excluded),
        "excluded": [(p.task, p.method) for p in excluded],
        "observed": {"e1_passes": e1, "gain": gain, "net_improvement": gain, "diffs": diffs, "parse_rate": parse_rate},
        "pairwise": pairwise_counts(pairs),
        "observed_decision": observed,
    }
    if not excluded:
        result.update(decision=observed, possible_decisions=[observed], inconclusive_by_infrastructure=False)
        return result
    possible = _possible_decisions(pairs)
    changes = possible != {observed}
    result.update(possible_decisions=sorted(possible), inconclusive_by_infrastructure=changes,
                  decision=INCONCLUSIVE_INFRA if changes else observed)
    return result
