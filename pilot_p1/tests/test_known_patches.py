"""Contraste con ejemplos conocidos: los parches ORIGINALES (logs/downstream) que `git apply --check -p1`
acepta sobre los ficheros del base_commit se convierten bloque a bloque en SEARCH/REPLACE y se
reaplican con el aplicador. Donde el aplicador acepta, el fichero resultante debe ser identico al que
produce `git apply` real. Que un bloque no sea unico o se solape NO es un fallo (anclar no implica
unicidad); solo se cuentan.

Lectura exclusivamente: git ls-tree/cat-file sobre repos/ y lectura de logs/. Se omite si faltan datos
o con P1_SKIP_KNOWN=1.
"""
import csv
import os
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from pilot_p1 import applier as A
from pilot_p1.applier import GitSource, apply_blocks
from pilot_p1.edit_format import EditBlock
from pilot_p1.tests.helpers import git_apply_result, tree_digest

ROOT = Path(__file__).resolve().parents[2]
TASKS_CSV = ROOT / "results" / "final_tasks.csv"
LOGS = ROOT / "logs" / "downstream"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(text):
    """-> ([(ruta, [hunk], es_alta)], prefijos) con hunk = (lineas_viejas, lineas_nuevas, marcador_no_newline).
    Admite ficheros existentes y altas (``--- /dev/null``); no admite bajas. ``prefijos``: True (a/ b/),
    False (sin prefijos) o None (mezcla)."""
    lines = text.replace("\r\n", "\n").split("\n")
    files, i, prefixed = [], 0, []
    while i < len(lines):
        m0 = re.match(r"^--- (a/)?(\S.*)$", lines[i]) if i + 1 < len(lines) else None
        m1 = re.match(r"^\+\+\+ (b/)?(\S.*)$", lines[i + 1]) if m0 else None
        is_new = bool(m0 and m1 and m0.group(2) == "/dev/null" and m1.group(2) != "/dev/null")
        same = bool(m0 and m1 and m0.group(2) == m1.group(2) and m0.group(2) != "/dev/null"
                    and bool(m0.group(1)) == bool(m1.group(1)))
        if is_new or same:
            path = m1.group(2)
            prefixed.append(bool(m1.group(1)))
            hunks, i = [], i + 2
            while i < len(lines) and HUNK.match(lines[i]):
                m = HUNK.match(lines[i])
                need_old, need_new = int(m.group(2) or 1), int(m.group(4) or 1)
                old, new, marker, i = [], [], False, i + 1
                while i < len(lines) and (need_old > 0 or need_new > 0 or lines[i].startswith("\\")):
                    ln = lines[i]
                    if ln.startswith("\\"):
                        marker = True
                    elif ln.startswith("-"):
                        old.append(ln[1:]); need_old -= 1
                    elif ln.startswith("+"):
                        new.append(ln[1:]); need_new -= 1
                    elif ln.startswith(" ") or ln == "":
                        old.append(ln[1:]); new.append(ln[1:]); need_old -= 1; need_new -= 1
                    else:
                        break
                    i += 1
                hunks.append((old, new, marker))
            files.append((path, hunks, is_new))
        else:
            i += 1
    return files, (all(prefixed) if prefixed else True) if (all(prefixed) or not any(prefixed)) else None


@unittest.skipIf(os.environ.get("P1_SKIP_KNOWN") == "1" or not (TASKS_CSV.is_file() and LOGS.is_dir()),
                 "datos del experimento no disponibles o P1_SKIP_KNOWN=1")
class KnownPatchesRoundTrip(unittest.TestCase):
    stats = Counter()

    @classmethod
    def tearDownClass(cls):
        print("\n[contraste con parches conocidos]", dict(sorted(cls.stats.items())))

    def test_round_trip_against_real_git_apply(self):
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            tasks = {r["original_inst_id"]: r for r in csv.DictReader(fh)}
        repos_before = {}
        compared = 0
        for task_dir in sorted(LOGS.iterdir()):
            row = tasks.get(task_dir.name)
            if not row:
                continue
            repo = ROOT / "repos" / row["repo"].replace("/", "__")
            if not (repo / ".git").exists():
                continue
            repos_before.setdefault(repo, tree_digest(repo / ".git"))
            for method_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
                pf = method_dir / "patch.diff"
                if not pf.is_file() or pf.stat().st_size == 0:
                    continue
                self.stats["parches_no_vacios"] += 1
                text = pf.read_bytes().decode("utf-8", "replace")
                files, prefixed = parse_patch(text)
                if not files or prefixed is None:
                    self.stats["sin_cabeceras_validas_o_mixtas"] += 1
                    continue
                src = GitSource(repo, row["base_commit"])
                blobs, ok = {}, True
                for path, _, is_new in files:
                    ent = src.entry(path)
                    if is_new:
                        continue
                    if ent is None or ent.kind != "file":
                        ok = False
                        break
                    blobs[path] = src.read(ent)
                if not ok:
                    self.stats["fichero_inexistente_en_base"] += 1
                    continue
                lf_patch = text.replace("\r\n", "\n").encode("utf-8")
                rc, _, real = git_apply_result(blobs, lf_patch, [p for p, *_ in files], strip=1 if prefixed else 0)
                if rc != 0:
                    self.stats["git_apply_check_falla"] += 1
                    continue
                self.stats["git_apply_check_pasa"] += 1
                blocks = []
                for path, hunks, is_new in files:
                    for old, new, marker in hunks:
                        if marker or (not old and not is_new):
                            continue
                        blocks.append(EditBlock(len(blocks), path, () if is_new else tuple(old), tuple(new)))
                    self.stats["altas_de_fichero_convertidas"] += int(is_new)
                if not blocks or any(h[2] for _, hs, _n in files for h in hs):
                    self.stats["omitido_sin_bloques_o_con_no_newline"] += 1
                    continue
                r = apply_blocks(blocks, src)
                self.stats["aplicador_" + r.status] += 1
                if r.status == A.READY:
                    compared += 1
                    # el aplicador no puede cambiar el salto final: solo comparamos si git tampoco lo hizo
                    for path in r.files:
                        self.assertEqual(r.files[path], real[path], f"{task_dir.name}/{method_dir.name}:{path}")
                    rc2, err2, _ = git_apply_result(blobs, r.diff_bytes, list(r.files))
                    self.assertEqual(rc2, 0, f"el diff generado no pasa git apply --check: {err2}")
        self.assertGreater(self.stats["git_apply_check_pasa"], 0)
        self.assertGreater(compared, 0)
        for repo, d in repos_before.items():
            self.assertEqual(tree_digest(repo / ".git"), d, f"{repo.name}: .git modificado")


if __name__ == "__main__":
    unittest.main()
