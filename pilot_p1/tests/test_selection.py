import copy
import csv
import hashlib
import unittest

from pilot_p1 import select_tasks as S

# Lista del protocolo (15.4) con los identificadores completos de final_tasks.csv, en el orden del hash.
PROTOCOL_IDS = [
    "scikit-learn__scikit-learn-13439", "pytest-dev__pytest-5809", "pydata__xarray-6992", "pytest-dev__pytest-5262",
    "matplotlib__matplotlib-24177", "matplotlib__matplotlib-24627", "sympy__sympy-19637",
    "huggingface__transformers-29675", "yt-dlp__yt-dlp-4841", "keras-team__keras-18871",
    "instance_qutebrowser__qutebrowser-16de05407111ddd82fa12e54389d532362489da9-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d",
    "instance_ansible__ansible-7e1a347695c7987ae56ef1b6919156d9254010ad-v390e508d27db7a51eece36bb6d9698b63a5b638a",
]


class Selection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = S.load_manifest()
        cls.pop = {r["id"]: r["source"] for r in cls.manifest["population"]}

    def test_hash_matches_protocol(self):
        ids = S.verify_manifest(self.manifest)
        self.assertEqual(S.selection_hash(ids), "6dbd0c9f9365690c")
        self.assertEqual(self.manifest["selection_hash"], "6dbd0c9f9365690c")

    def test_quotas_and_population(self):
        ids = S.select(self.pop)
        self.assertEqual(len(ids), 12)
        self.assertEqual([self.pop[i] for i in ids], ["Verified"] * 7 + ["Poly"] * 3 + ["Pro"] * 2)
        self.assertEqual(len(self.pop), 50)
        self.assertEqual({s: sum(1 for v in self.pop.values() if v == s) for s in ("Verified", "Poly", "Pro")},
                         {"Verified": 29, "Poly": 12, "Pro": 9})

    def test_matches_the_task_table_of_the_protocol(self):
        self.assertEqual(S.select(self.pop), PROTOCOL_IDS)
        self.assertEqual([r["id"] for r in self.manifest["selected"]], PROTOCOL_IDS)

    def test_order_rule_is_sha256_of_seed_colon_id(self):
        ids = S.select(self.pop)
        for source, lo, hi in (("Verified", 0, 7), ("Poly", 7, 10), ("Pro", 10, 12)):
            pool = sorted((i for i in self.pop if self.pop[i] == source),
                          key=lambda i: hashlib.sha256(f"42:{i}".encode()).hexdigest())
            self.assertEqual(ids[lo:hi], pool[:hi - lo])

    def test_list_hash_rule(self):
        ids = S.select(self.pop)
        self.assertEqual(hashlib.sha256("\n".join(ids).encode()).hexdigest()[:16], "6dbd0c9f9365690c")

    def test_deterministic_and_independent_of_input_order(self):
        a = S.select(self.pop)
        shuffled = dict(reversed(list(self.pop.items())))
        self.assertEqual(S.select(shuffled), a)
        self.assertEqual(S.select(self.pop), a)

    def test_hash_depends_on_order_and_content(self):
        ids = S.select(self.pop)
        self.assertNotEqual(S.selection_hash(list(reversed(ids))), S.selection_hash(ids))
        self.assertNotEqual(S.selection_hash(ids[:-1]), S.selection_hash(ids))

    def test_mismatch_stops_and_never_substitutes_silently(self):
        ids = S.select(self.pop)
        with self.assertRaises(S.SelectionHashMismatch):
            S.check_selection(ids[:-1] + ["otra-tarea"])
        bad = copy.deepcopy(self.pop)
        bad[ids[0]] = "Poly"                       # cambia la poblacion: cambia la seleccion
        with self.assertRaises(S.SelectionHashMismatch):
            S.check_selection(S.select(bad))
        with self.assertRaises(S.SelectionHashMismatch):
            S.build_manifest(bad)

    def test_tampered_manifest_is_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["selected"][0], m["selected"][1] = m["selected"][1], m["selected"][0]
        with self.assertRaises(S.SelectionError):
            S.verify_manifest(m)
        m = copy.deepcopy(self.manifest)
        m["population"] = m["population"][:-1]
        with self.assertRaises(S.SelectionError):
            S.verify_manifest(m)

    def test_not_enough_tasks_in_a_source(self):
        with self.assertRaises(S.SelectionError):
            S.select({"x": "Verified"})

    def test_population_equals_final_tasks_csv(self):
        with S.TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            ids = [r["original_inst_id"] for r in csv.DictReader(fh)]
        self.assertEqual(sorted(ids), sorted(self.pop))

    def test_conditions_are_36_and_cover_three_strategies(self):
        c = S.conditions(S.select(self.pop))
        self.assertEqual(len(c), 36)
        self.assertEqual(len(set(c)), 36)
        self.assertEqual({m for _, m in c}, {"bm25", "semantic", "hybrid"})

    def test_three_selected_tasks_already_have_an_applicable_original_patch(self):
        ids = S.select(self.pop)
        for needle in ("pytest-dev__pytest-5809", "matplotlib__matplotlib-24177", "ansible-7e1a347695c7"):
            self.assertTrue(any(needle in i for i in ids), needle)

    def test_manifest_file_is_lf_only_and_stable(self):
        raw = S.MANIFEST_PATH.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))

    def test_cli_check(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(S.main(["--check"]), 0)
            self.assertEqual(S.main([]), 2)
        self.assertIn("6dbd0c9f9365690c", out.getvalue())


if __name__ == "__main__":
    unittest.main()
