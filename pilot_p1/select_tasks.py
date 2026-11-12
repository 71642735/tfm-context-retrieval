"""Seleccion determinista de las 12 tareas del piloto P1 (protocolo: docs/downstream-patch-diagnostics.md, 15.4).

Regla (no se modifica): de las 50 tareas de ``results/final_tasks.csv`` (Verified 29, Poly 12, Pro 9) se toman
7 / 3 / 2; dentro de cada fuente se ordenan por ``sha256("42:<original_inst_id>")`` y se cogen las primeras *n*.
El identificador de la lista es ``sha256("\\n".join(ids))[:16]`` con ids completos, en el orden Verified, Poly, Pro.
Hash esperado por el protocolo: ``6dbd0c9f9365690c``. Si no coincide se lanza ``SelectionHashMismatch``: nunca se
sustituye la seleccion en silencio.

Metadatos minimos para reproducir (``data/task_selection.json``): las 50 tareas con su fuente, la regla y el hash.
Calcular la seleccion no necesita red ni el dataset. Solo ``--write`` lee la fuente (Verified/Poly/Pro) del dataset
local en cache (``HF_DATASETS_OFFLINE=1``), y no escribe nada si el hash no coincide.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "task_selection.json"
TASKS_CSV = ROOT / "results" / "final_tasks.csv"

SEED = "42"
QUOTAS = (("Verified", 7), ("Poly", 3), ("Pro", 2))
EXPECTED_HASH = "6dbd0c9f9365690c"
METHODS = ("bm25", "semantic", "hybrid")


class SelectionError(RuntimeError):
    pass


class SelectionHashMismatch(SelectionError):
    pass


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def order_key(task_id: str) -> str:
    return _sha(f"{SEED}:{task_id}")


def select(population: Dict[str, str]) -> List[str]:
    """``population``: {original_inst_id: fuente}. Devuelve los 12 ids en el orden Verified, Poly, Pro."""
    out: List[str] = []
    for source, n in QUOTAS:
        ids = sorted((i for i, s in population.items() if s == source), key=order_key)
        if len(ids) < n:
            raise SelectionError(f"fuente {source}: hay {len(ids)} tareas y se piden {n}")
        out.extend(ids[:n])
    return out


def selection_hash(ids: Sequence[str]) -> str:
    return _sha("\n".join(ids))[:16]


def check_selection(ids: Sequence[str]) -> str:
    h = selection_hash(ids)
    if h != EXPECTED_HASH:
        raise SelectionHashMismatch(f"hash de seleccion {h} != {EXPECTED_HASH} (protocolo); no se sustituye la seleccion")
    return h


def conditions(ids: Sequence[str]) -> List[tuple]:
    """36 condiciones = tarea x estrategia, en orden estable."""
    return [(i, m) for i in ids for m in METHODS]


def build_manifest(population: Dict[str, str]) -> dict:
    ids = select(population)
    h = check_selection(ids)
    return {
        "protocol": "docs/downstream-patch-diagnostics.md, seccion 15.4 (P1, borrador no aprobado)",
        "seed": SEED,
        "quotas": {s: n for s, n in QUOTAS},
        "ordering_rule": 'sha256("42:<original_inst_id>") ascendente dentro de cada fuente; se toman las primeras n',
        "hash_rule": 'sha256("\\n".join(ids))[:16], ids completos, orden Verified, Poly, Pro',
        "expected_hash": EXPECTED_HASH,
        "selection_hash": h,
        "population_source": "results/final_tasks.csv; campo `source` de Contextbench/ContextBench (cache local, offline)",
        "population": [{"id": i, "source": population[i]} for i in sorted(population)],
        "selected": [{"id": i, "source": population[i]} for i in ids],
        "methods": list(METHODS),
        "n_conditions": len(ids) * len(METHODS),
    }


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def verify_manifest(manifest: dict, tasks_csv: Path = TASKS_CSV) -> List[str]:
    """Recalcula la seleccion desde la poblacion del manifiesto y la contrasta con el protocolo y con final_tasks.csv."""
    pop = {r["id"]: r["source"] for r in manifest["population"]}
    with Path(tasks_csv).open(encoding="utf-8", newline="") as fh:
        csv_ids = [r["original_inst_id"] for r in csv.DictReader(fh)]
    if sorted(csv_ids) != sorted(pop):
        raise SelectionError("la poblacion del manifiesto no coincide con results/final_tasks.csv")
    ids = select(pop)
    check_selection(ids)
    if [r["id"] for r in manifest["selected"]] != ids or manifest["selection_hash"] != EXPECTED_HASH:
        raise SelectionError("el manifiesto guardado no coincide con la seleccion recalculada")
    return ids


def _source_from_dataset(ids: Sequence[str]) -> Dict[str, str]:
    import os
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from datasets import load_dataset
    ds = {r["original_inst_id"]: r["source"] for r in load_dataset("Contextbench/ContextBench")["train"]}
    return {i: ds[i] for i in ids}


def main(argv: Sequence[str]) -> int:
    if not argv or argv[0] not in ("--check", "--write"):
        print("uso: python -m pilot_p1.select_tasks --check | --write")
        return 2
    if argv[0] == "--check":
        ids = verify_manifest(load_manifest())
        print(f"OK: {len(ids)} tareas, hash {selection_hash(ids)}")
        for i in ids:
            print(" ", i)
        return 0
    with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
        csv_ids = [r["original_inst_id"] for r in csv.DictReader(fh)]
    manifest = build_manifest(_source_from_dataset(csv_ids))        # lanza si el hash no coincide
    if MANIFEST_PATH.exists():
        print("el manifiesto ya existe; no se sobrescribe")
        return 1
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("manifiesto escrito:", MANIFEST_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
