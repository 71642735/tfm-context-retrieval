import time
import unittest

from pilot_p1 import decision as D
from pilot_p1.decision import PairResult

TASKS = [f"t{i}" for i in range(12)]


def pairs(spec):
    """spec: dict (metodo, indice) -> (e1_pass, o1n_pass, parseable); por defecto (False, False, True)."""
    out = []
    for i, t in enumerate(TASKS):
        for m in D.STRATEGIES:
            out.append(PairResult(t, m, *spec.get((m, i), (False, False, True))))
    return out


def with_wins(e1_only=(), both=(), o1_only=(), parse=True):
    spec = {}
    for m, i in e1_only:
        spec[(m, i)] = (True, False, parse)
    for m, i in both:
        spec[(m, i)] = (True, True, parse)
    for m, i in o1_only:
        spec[(m, i)] = (False, True, parse)
    return spec


SUCCESS_SPEC = with_wins(e1_only=[("bm25", i) for i in range(3)] + [("semantic", i) for i in range(3)] + [("hybrid", 0), ("hybrid", 1)],
                         both=[("bm25", 5), ("hybrid", 5)])      # E1 = 10, O1n = 2, gain 8, +,+,+


class Rule(unittest.TestCase):
    def test_thresholds_are_the_frozen_ones(self):
        self.assertEqual((D.SUCCESS_GAIN, D.SUCCESS_E1_PASSES, D.ABANDON_GAIN, D.ABANDON_E1_PASSES, D.SUCCESS_PARSE,
                          D.ABANDON_PARSE, D.N_CONDITIONS), (6, 10, 2, 6, 0.80, 0.60, 36))

    def test_success(self):
        r = D.evaluate(pairs(SUCCESS_SPEC))
        self.assertEqual((r["decision"], r["n_excluded_pairs"], r["inconclusive_by_infrastructure"]), (D.SUCCESS, 0, False))
        self.assertEqual(r["observed"]["e1_passes"], 10)

    def test_success_needs_every_condition(self):
        # diferencia negativa en una estrategia -> no exito
        neg = with_wins(e1_only=[("bm25", i) for i in range(5)] + [("semantic", i) for i in range(5)] + [("hybrid", i) for i in range(3)],
                        o1_only=[("hybrid", 5), ("hybrid", 6), ("hybrid", 7), ("hybrid", 8)])
        r = D.evaluate(pairs(neg))
        self.assertNotEqual(r["decision"], D.SUCCESS)
        # solo una estrategia positiva -> no exito
        one = with_wins(e1_only=[("bm25", i) for i in range(10)])
        self.assertNotEqual(D.evaluate(pairs(one))["decision"], D.SUCCESS)

    def test_parse_rate_conditions(self):
        r = D.evaluate([PairResult(p.task, p.method, p.e1_pass, p.o1n_pass, False) for p in pairs(SUCCESS_SPEC)])
        self.assertEqual(r["decision"], D.ABANDON)                   # < 60 % parseable
        mid = pairs(SUCCESS_SPEC)
        mid = [PairResult(p.task, p.method, p.e1_pass, p.o1n_pass, i % 4 != 0) for i, p in enumerate(mid)]   # 75 %
        self.assertEqual(D.evaluate(mid)["decision"], D.INCONCLUSIVE)

    def test_abandon_conditions(self):
        self.assertEqual(D.evaluate(pairs({}))["decision"], D.ABANDON)                           # nada pasa
        two = with_wins(e1_only=[("bm25", 0), ("semantic", 0)], both=[("hybrid", i) for i in range(6)])
        self.assertEqual(D.evaluate(pairs(two))["decision"], D.ABANDON)                         # ganancia <= 2
        five = with_wins(both=[("bm25", i) for i in range(5)])
        self.assertEqual(D.evaluate(pairs(five))["decision"], D.ABANDON)                        # E1 < 6

    def test_inconclusive(self):
        spec = with_wins(e1_only=[("bm25", i) for i in range(4)] + [("semantic", 0)], both=[("hybrid", i) for i in range(3)])
        self.assertEqual(D.evaluate(pairs(spec))["decision"], D.INCONCLUSIVE)                   # gain 5, E1 8

    def test_requires_36_distinct_pairs(self):
        with self.assertRaises(ValueError):
            D.evaluate(pairs({})[:-1])
        dup = pairs({})
        dup[-1] = dup[0]
        with self.assertRaises(ValueError):
            D.evaluate(dup)


class NetImprovement(unittest.TestCase):
    """Interpretacion fijada el 12/11/2026: 'E1 supera a O1n en N condiciones' = victorias E1 - victorias O1n."""

    def test_net_improvement_is_the_rule_not_the_count_of_e1_wins(self):
        # E1 gana 8, O1n gana 3, E1 pasa 10: mejora neta 5 -> NO es exito (con solo victorias de E1 si lo seria)
        spec = with_wins(e1_only=[("bm25", i) for i in range(4)] + [("semantic", i) for i in range(4)],
                         o1_only=[("hybrid", i) for i in range(3)], both=[("bm25", 8), ("hybrid", 8)])
        pw = D.evaluate(pairs(spec))["pairwise"]
        self.assertEqual((pw["e1_wins"], pw["o1n_wins"], pw["net_improvement"]), (8, 3, 5))
        self.assertGreaterEqual(pw["e1_wins"], 6)
        self.assertEqual(D.evaluate(pairs(spec))["decision"], D.INCONCLUSIVE)

    def test_net_improvement_six_is_success(self):
        spec = with_wins(e1_only=[("bm25", i) for i in range(4)] + [("semantic", i) for i in range(3)] + [("hybrid", 0), ("hybrid", 1)],
                         o1_only=[("semantic", 5), ("hybrid", 5), ("hybrid", 6)], both=[("bm25", 9)])
        r = D.evaluate(pairs(spec))
        self.assertEqual((r["pairwise"]["e1_wins"], r["pairwise"]["o1n_wins"], r["pairwise"]["net_improvement"]), (9, 3, 6))
        self.assertEqual(r["observed"]["diffs"], {"bm25": 4, "semantic": 2, "hybrid": 0})
        self.assertEqual((r["observed"]["e1_passes"], r["decision"]), (10, D.SUCCESS))

    def test_many_e1_wins_do_not_save_a_small_net_improvement(self):
        spec = with_wins(e1_only=[("bm25", i) for i in range(5)] + [("semantic", i) for i in range(4)],
                         o1_only=[("hybrid", i) for i in range(7)])
        r = D.evaluate(pairs(spec))
        self.assertEqual((r["pairwise"]["e1_wins"], r["pairwise"]["net_improvement"]), (9, 2))
        self.assertEqual(r["decision"], D.ABANDON)                                  # neta <= 2

    def test_abandon_boundary_is_net_two_and_success_boundary_is_net_six(self):
        self.assertEqual(D.decide(12, 2, {"bm25": 1, "semantic": 1, "hybrid": 0}, 1.0), D.ABANDON)
        self.assertEqual(D.decide(12, 3, {"bm25": 1, "semantic": 1, "hybrid": 1}, 1.0), D.INCONCLUSIVE)
        self.assertEqual(D.decide(12, 5, {"bm25": 2, "semantic": 2, "hybrid": 1}, 1.0), D.INCONCLUSIVE)
        self.assertEqual(D.decide(12, 6, {"bm25": 2, "semantic": 2, "hybrid": 2}, 1.0), D.SUCCESS)

    def test_wins_ties_and_net_are_recorded_and_consistent(self):
        spec = with_wins(e1_only=[("bm25", 0), ("bm25", 1)], o1_only=[("semantic", 0)], both=[("hybrid", 0), ("hybrid", 1), ("hybrid", 2)])
        r = D.evaluate(pairs(spec))
        pw = r["pairwise"]
        self.assertEqual((pw["n_paired"], pw["e1_wins"], pw["o1n_wins"], pw["ties_both_pass"], pw["ties_both_fail"]),
                         (36, 2, 1, 3, 30))
        self.assertEqual(pw["e1_wins"] + pw["o1n_wins"] + pw["ties_both_pass"] + pw["ties_both_fail"], pw["n_paired"])
        self.assertEqual(pw["net_improvement"], pw["e1_wins"] - pw["o1n_wins"])
        for k in ("e1_wins", "o1n_wins", "ties_both_pass", "ties_both_fail", "net_improvement", "n_paired"):
            self.assertEqual(sum(s[k] for s in pw["by_strategy"].values()), pw[k], k)
        self.assertEqual(pw["by_strategy"]["bm25"]["net_improvement"], 2)
        self.assertEqual(r["observed"]["net_improvement"], r["observed"]["gain"])

    def test_unpaired_conditions_are_not_counted_in_wins_or_ties(self):
        plist = pairs(with_wins(e1_only=[("bm25", 0)]))
        plist[0] = PairResult(plist[0].task, plist[0].method, True, None, True)
        pw = D.evaluate(plist)["pairwise"]
        self.assertEqual((pw["n_paired"], pw["e1_wins"]), (35, 0))

    def test_interpretation_is_documented_as_fixed_before_generation(self):
        doc = D.__doc__
        self.assertIn("mejora neta", doc)
        self.assertIn("antes de cualquier generacion experimental", doc)


class Exclusions(unittest.TestCase):
    def exclude(self, plist, which, what="both"):
        out = []
        for p in plist:
            if (p.method, p.task) in which:
                e1, o1 = (None, None) if what == "both" else ((None, p.o1n_pass) if what == "e1" else (p.e1_pass, None))
                out.append(PairResult(p.task, p.method, e1, o1, None if e1 is None else p.e1_parseable))
            else:
                out.append(p)
        return out

    def test_exclusion_that_cannot_change_the_decision_is_reported_but_not_inconclusive(self):
        base = pairs({})                                             # abandono firme: E1 pasa 0
        ex = self.exclude(base, {("bm25", "t0")})
        r = D.evaluate(ex)
        self.assertEqual((r["n_excluded_pairs"], r["decision"], r["inconclusive_by_infrastructure"]), (1, D.ABANDON, False))
        self.assertEqual(r["possible_decisions"], [D.ABANDON])

    def test_exclusion_that_can_change_the_decision_is_inconclusive_by_infrastructure(self):
        spec = dict(SUCCESS_SPEC)
        spec[("hybrid", 11)] = (True, False, True)
        spec.pop(("hybrid", 1))
        base = pairs(spec)
        ex = self.exclude(base, {("hybrid", "t0")})                    # el par excluido pasa de ganar a desconocido
        r = D.evaluate(ex)
        self.assertEqual(r["n_excluded_pairs"], 1)
        self.assertGreater(len(r["possible_decisions"]), 1)
        self.assertTrue(r["inconclusive_by_infrastructure"])
        self.assertEqual(r["decision"], D.INCONCLUSIVE_INFRA)

    def test_thresholds_are_not_rescaled(self):
        ex = self.exclude(pairs(SUCCESS_SPEC), {("bm25", f"t{i}") for i in range(12)})
        r = D.evaluate(ex)
        self.assertEqual(r["observed"]["parse_rate"] * D.N_CONDITIONS, 24)      # denominador sigue siendo 36
        self.assertTrue(r["inconclusive_by_infrastructure"])

    def test_one_arm_excluded_excludes_the_pair(self):
        for what in ("e1", "o1"):
            r = D.evaluate(self.exclude(pairs({}), {("semantic", "t3")}, what))
            self.assertEqual(r["excluded"], [("t3", "semantic")])

    def test_all_excluded_is_inconclusive_and_fast(self):
        t0 = time.time()
        r = D.evaluate([PairResult(p.task, p.method, None, None, None) for p in pairs({})])
        self.assertTrue(r["inconclusive_by_infrastructure"])
        self.assertEqual(set(r["possible_decisions"]), {D.SUCCESS, D.ABANDON, D.INCONCLUSIVE})
        self.assertLess(time.time() - t0, 60)

    def test_known_infeasible_completions_do_not_count(self):
        # e1_pass True exige parseable True: una finalizacion con pasa y no parseable no existe
        p = PairResult("t0", "bm25", None, False, None)
        self.assertNotIn((1, 0, 0), D._options(p))


if __name__ == "__main__":
    unittest.main()
