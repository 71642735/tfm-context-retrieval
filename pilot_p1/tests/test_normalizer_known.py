"""Contraste de N con los parches originales sin prefijos que Git acepta con ``-p0`` sobre el ``base_commit``
(los "recuperables"). Comprobacion tecnica en directorios temporales; NO es el filtro experimental G ni un
evaluador. Lectura exclusiva de ``repos/`` (git ls-tree / cat-file)."""
import csv
import os
import unittest
from collections import Counter
from pathlib import Path

from pilot_p1 import normalizer as N
from pilot_p1.applier import GitSource
from pilot_p1.tests.helpers import git_apply_result
from pilot_p1.tests.test_known_patches import LOGS, ROOT, TASKS_CSV, parse_patch


@unittest.skipIf(os.environ.get("P1_SKIP_KNOWN") == "1" or not (TASKS_CSV.is_file() and LOGS.is_dir()),
                 "datos del experimento no disponibles o P1_SKIP_KNOWN=1")
class NormalizerAgainstGitP0(unittest.TestCase):
    stats = Counter()

    @classmethod
    def tearDownClass(cls):
        print("\n[N frente a git apply -p0 sobre parches sin prefijos]", dict(sorted(cls.stats.items())))

    def test_every_recoverable_patch_is_normalized_and_equivalent(self):
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            tasks = {r["original_inst_id"]: r for r in csv.DictReader(fh)}
        for task_dir in sorted(LOGS.iterdir()):
            row = tasks.get(task_dir.name)
            if not row:
                continue
            repo = ROOT / "repos" / row["repo"].replace("/", "__")
            for method_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
                pf = method_dir / "patch.diff"
                if not pf.is_file() or pf.stat().st_size == 0:
                    continue
                text = pf.read_bytes().decode("utf-8", "replace")
                files, prefixed = parse_patch(text)
                if not files or prefixed is not False:
                    continue
                self.stats["sin_prefijos"] += 1
                src = GitSource(repo, row["base_commit"])
                blobs = {}
                for path, _, is_new in files:
                    ent = src.entry(path)
                    if ent is not None and ent.kind == "file":
                        blobs[path] = src.read(ent)
                    elif not is_new:
                        blobs = None
                        break
                if blobs is None:
                    self.stats["fichero_inexistente"] += 1
                    continue
                lf = text.replace("\r\n", "\n").encode("utf-8")
                rc0, _, out0 = git_apply_result(blobs, lf, [p for p, *_ in files], strip=0)
                r = N.normalize_patch(text)
                if rc0 != 0:
                    self.stats["no_aplica_ni_con_p0"] += 1
                    continue
                self.stats["aplica_con_p0"] += 1
                self.assertEqual(r.status, N.NORMALIZED, f"{task_dir.name}/{method_dir.name}: {r.detail}")
                rc1, err, out1 = git_apply_result(blobs, r.patch.replace("\r\n", "\n").encode("utf-8"),
                                                  [p for p, *_ in files], strip=1)
                self.assertEqual(rc1, 0, err)
                self.assertEqual(out1, out0, "N no debe cambiar el resultado de la edicion")
                self.stats["normalizado_y_equivalente"] += 1
        self.assertGreaterEqual(self.stats["aplica_con_p0"], 1)
        self.assertEqual(self.stats["aplica_con_p0"], self.stats["normalizado_y_equivalente"])


if __name__ == "__main__":
    unittest.main()
