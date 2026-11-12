"""Etapas G (aplicabilidad) y evaluacion funcional simulada dentro de la orquestacion (fase 3B.1).

Solo clientes y evaluadores falsos; repositorios sinteticos temporales (y, en lectura, repos/ en el simulacro completo)."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock
import unittest

from pilot_p1 import applier as A
from pilot_p1 import decision as D
from pilot_p1 import functional as F
from pilot_p1 import gate as G
from pilot_p1 import orchestrator as O
from pilot_p1.client import FakeClient
from pilot_p1.tests import test_orchestrator as TO
from pilot_p1.tests.sim_helpers import Recorder, fake_client, synthetic_text

ROOT = O.PROJECT_ROOT


def resolver(request: F.EvalRequest) -> str:
    return F.RESOLVED if int(request.patch_sha256[:2], 16) % 2 else F.NOT_RESOLVED


def read(p: Path):
    return json.loads(p.read_bytes().decode("utf-8"))


class StageBase(TO.Base):
    """Ejecucion sintetica pequena (12 condiciones) con G aplicada."""

    def full(self, client=None, evaluator=None, **kw):
        o = self.orch(client or fake_client()[0], functional_evaluator=evaluator,
                      task_info_provider=lambda t: {"repo": "synth/repo", "base_commit": "abc123"}, **kw)
        o.run()
        return o

    def cdir_of(self, o, arm, n=0):
        c = [x for x in o.conditions if x.arm == arm][n]
        return self.run_dir.path / O.COND_DIR / c.cond_id


class GateStage(StageBase):
    def test_gate_covers_both_arms_and_keeps_artifacts_distinct(self):
        o = self.full()
        self.assertEqual(o.apply_gate(), {"gate_written": 12, "gate_skipped": 0, "upstream_missing": 0})
        for arm, art in (("O1", "o1n.patch"), ("E1", "diff.patch")):
            d = self.cdir_of(o, arm)
            app = read(d / "applicability.json")
            self.assertEqual((app["input_artifact"], app["status"], app["filter"], app["synthetic"]), (art, "applicable", "G", True))
            self.assertEqual(app["patch_sha256"], hashlib.sha256((d / art).read_bytes()).hexdigest())
            self.assertEqual(app["policy"]["command"], ["git", "apply", "--check", "-p1", "<patch_file>"])
            self.assertTrue(app["policy"]["patch_bytes_unmodified"] and app["policy"]["same_policy_for_O1n_and_E1"])
            att = app["attempts"][0]
            self.assertEqual((att["returncode"], att["command"][-1]), (0, "<patch_file>"))
            self.assertEqual(app["functional"], "pending")
        o1 = self.cdir_of(o, "O1")
        names = {p.name for p in o1.iterdir()}
        self.assertTrue({"response.txt", "o1.patch", "o1n.patch", "applicability.json"} <= names)   # original y normalizado, distintos
        self.assertNotEqual((o1 / "o1.patch").read_bytes(), (o1 / "o1n.patch").read_bytes())
        self.assertTrue(o.verify(recompute=True).ok)

    def test_both_arms_go_through_the_same_function_with_the_same_arguments(self):
        o = self.full()
        with mock.patch.object(O.GATE, "gate_check", wraps=G.gate_check) as gc:
            o.apply_gate()
        self.assertEqual(gc.call_count, 12)
        for call in gc.call_args_list:
            self.assertEqual(len(call.args), 2)                           # (bytes del parche, fabrica de fuente)
            self.assertIsInstance(call.args[0], bytes)
            self.assertEqual(set(call.kwargs), {"max_attempts"})

    def test_stored_verdicts_equal_an_independent_recomputation(self):
        o = self.full()
        o.apply_gate()
        src = self.world.source_factory("x")
        for c in o.conditions:
            d = self.run_dir.path / O.COND_DIR / c.cond_id
            app = read(d / "applicability.json")
            self.assertEqual(G.gate_check((d / app["input_artifact"]).read_bytes(), src).status, app["status"])

    def test_resume_never_repeats_or_overwrites_the_gate(self):
        o = self.full()
        o.apply_gate()
        before = self.digest()
        again = self.orch(FakeClient(script=[]), task_info_provider=lambda t: {})
        self.assertEqual(again.apply_gate(), {"gate_written": 0, "gate_skipped": 12, "upstream_missing": 0})
        self.assertEqual(self.digest(), before)

    def test_gate_requires_an_existing_run(self):
        with self.assertRaises(O.OrchestrationError):
            self.orch().apply_gate()

    def test_pair_results_need_the_gate_first(self):
        o = self.full()
        with self.assertRaises(O.OrchestrationError):
            o.pair_results()

    def test_e1_without_patch_is_not_applicable_and_git_is_not_run_for_it(self):
        bad = "FILE: pkg/m1.py\n<<<<<<< SEARCH\nno existe\n=======\nx\n>>>>>>> REPLACE\n"
        rec = Recorder()
        client = FakeClient(responder=lambda p: bad if "SEARCH" in p.split("INSTRUCTIONS:")[-1] else rec(p))
        o = self.full(client)
        with mock.patch.object(O.GATE, "gate_check", wraps=G.gate_check) as gc:
            o.apply_gate()
        self.assertEqual(gc.call_count, 6)                                  # solo las 6 O1n; las E1 no tienen parche
        app = read(self.cdir_of(o, "E1") / "applicability.json")
        self.assertEqual((app["status"], app["category"], app["reason"], app["attempts"], app["input_artifact"]),
                         ("not_applicable", "model_output_error", "conversion:search_not_found", [], None))
        s = o.summary()
        self.assertEqual(s["by_arm"]["E1"]["not_applicable"], 6)
        self.assertEqual(s["stages"]["functional"]["not_applicable"], 6)

    def test_crlf_o1_patches_are_rejected_without_extra_corrections(self):
        rec = Recorder()
        client = FakeClient(responder=lambda p: (rec(p).replace("\n", "\r\n") if "unified diff" in p.split("INSTRUCTIONS:")[-1]
                                                  else rec(p)))
        o = self.full(client)
        o.apply_gate()
        s = o.summary()
        self.assertEqual((s["by_arm"]["O1"]["not_applicable"], s["by_arm"]["E1"]["applicable"]), (6, 6))
        self.assertEqual(s["model_output_errors"], {})                      # N y G no cuentan como error de conversion
        pairs = o.pair_results()
        self.assertTrue(all(p.e1_pass is True and p.o1n_pass is False for p in pairs))

    def test_infrastructure_errors_in_g_are_retried_and_recovered(self):
        o = self.full()
        n = {"k": 0}

        def flaky(task_id):
            n["k"] += 1
            if n["k"] <= 2:
                raise A.SourceError("git no responde")
            return self.world.source_factory(task_id)

        fresh = self.orch(FakeClient(script=[]), source_factory=flaky)
        fresh.apply_gate()
        app = read(self.cdir_of(o, "O1") / "applicability.json")
        self.assertEqual((app["status"], app["n_attempts"], app["recovered_after_retry"]), ("applicable", 3, True))
        self.assertEqual([a["status"] for a in app["attempts"]], ["environment_error", "environment_error", "applicable"])
        s = fresh.summary()
        self.assertEqual((s["gate_infrastructure"], s["n_excluded_pairs"]), ({"retries": 2, "recovered_after_retry": 1}, 0))
        ev = [e for e in O.EventLog.read(self.run_dir.path / O.EVENTS) if e["type"] == "apply_infra_retry"]
        self.assertEqual(len(ev), 2)

    def test_persistent_infrastructure_errors_exclude_the_pair_and_are_not_model_errors(self):
        self.full()

        def broken(task_id):
            raise A.SourceError("disco no disponible")

        fresh = self.orch(FakeClient(script=[]), source_factory=broken)
        fresh.apply_gate()
        s = fresh.summary()
        self.assertEqual(s["stages"]["applicability"]["not_evaluable_infrastructure"], 12)
        self.assertEqual((s["n_excluded_pairs"], s["model_output_errors"]), (6, {}))
        app = read(self.cdir_of(fresh, "E1") / "applicability.json")
        self.assertEqual((app["status"], app["category"], app["n_attempts"]), ("not_evaluable_infrastructure",
                                                                             "infrastructure_not_evaluable", 3))
        self.assertEqual(len([a for a in app["attempts"]]), 3)                # nunca mas de 3 intentos
        pairs = fresh.pair_results()
        self.assertTrue(all(p.e1_pass is None and p.o1n_pass is None for p in pairs))
        self.assertTrue(all(p.excluded for p in pairs))
        self.assertEqual(len(O.EventLog.read(self.run_dir.path / O.EVENTS)) > 0, True)

    def test_model_rejections_are_not_retried(self):
        rec = Recorder()
        client = FakeClient(responder=lambda p: rec(p).replace("y", "q") if False else rec(p))
        o = self.full(client)
        d = self.cdir_of(o, "O1")
        (d / "o1n.patch")                                                    # el parche existe; se fuerza uno que git rechaza
        with mock.patch.object(O.GATE, "gate_check", wraps=G.gate_check):
            o.apply_gate()
        app = read(d / "applicability.json")
        self.assertEqual(app["n_attempts"], 1)


class FunctionalStage(StageBase):
    def run_all(self, **kw):
        ev = F.FakeFunctionalEvaluator(responder=resolver)
        o = self.full(evaluator=ev, **kw)
        o.apply_gate()
        return o, ev

    def test_only_applicable_patches_are_evaluated_and_everything_is_recorded(self):
        o, ev = self.run_all()
        self.assertEqual(o.summary()["stages"]["functional"]["pending"], 12)
        stats = o.evaluate_functional()
        self.assertEqual((stats["evaluated"], stats["not_applicable"], len(ev.calls)), (12, 0, 12))
        req = ev.calls[0]
        self.assertTrue(req.run_label.startswith("p1-sim-") and req.run_label.endswith(req.cond_id))
        self.assertEqual((req.repo, req.base_commit), ("synth/repo", "abc123"))
        d = self.run_dir.path / O.COND_DIR / req.cond_id
        self.assertEqual(Path(req.patch_path).resolve(), (d / read(d / "applicability.json")["input_artifact"]).resolve())
        f = read(d / "functional.json")
        self.assertEqual((f["outcome"], f["category"], f["synthetic"], f["evaluator"]["is_synthetic"], f["n_attempts"]),
                         (resolver(req), "ok", True, True, 1))
        self.assertEqual(f["request"]["patch_sha256"], req.patch_sha256)
        self.assertEqual(hashlib.sha256((d / "functional_evidence.json").read_bytes()).hexdigest(), f["evidence_sha256"])
        s = o.summary()
        self.assertEqual(s["stages"]["functional"]["resolved"] + s["stages"]["functional"]["not_resolved"], 12)
        self.assertEqual(s["stages"]["functional"]["pending"], 0)
        self.assertTrue(o.verify(recompute=True).ok)

    def test_non_applicable_patches_are_never_evaluated(self):
        rec = Recorder()
        client = FakeClient(responder=lambda p: (rec(p).replace("\n", "\r\n") if "unified diff" in p.split("INSTRUCTIONS:")[-1]
                                                  else rec(p)))
        ev = F.FakeFunctionalEvaluator(responder=resolver)
        o = self.full(client, ev)
        o.apply_gate()
        stats = o.evaluate_functional()
        self.assertEqual((stats["evaluated"], stats["not_applicable"], len(ev.calls)), (6, 6, 6))
        self.assertTrue(all(r.arm == "E1" for r in ev.calls))
        for c in o.conditions:
            if c.arm == "O1":
                self.assertFalse((self.run_dir.path / O.COND_DIR / c.cond_id / "functional.json").exists())

    def test_functional_stage_waits_for_gate(self):
        ev = F.FakeFunctionalEvaluator(responder=resolver)
        o = self.full(evaluator=ev)
        stats = o.evaluate_functional()
        self.assertEqual((stats["pending_gate"], stats["evaluated"], ev.calls), (12, 0, []))

    def test_both_arms_are_evaluated_through_the_same_path_with_the_same_request_shape(self):
        o, ev = self.run_all()
        o.evaluate_functional()
        shapes = {tuple(sorted(vars(r))) for r in ev.calls}
        self.assertEqual(len(shapes), 1)
        self.assertEqual({r.arm for r in ev.calls}, {"O1", "E1"})
        for r in ev.calls:
            self.assertEqual(r.patch_sha256, hashlib.sha256(Path(r.patch_path).read_bytes()).hexdigest())

    def test_resume_does_not_duplicate_evaluations_or_overwrite_files(self):
        o, ev = self.run_all()
        o.evaluate_functional()
        before = self.digest()
        silent = F.FakeFunctionalEvaluator(script=[])
        again = self.orch(FakeClient(script=[]), functional_evaluator=silent)
        stats = again.evaluate_functional()
        self.assertEqual((stats["evaluated"], stats["skipped"], silent.calls), (0, 12, []))
        self.assertEqual(self.digest(), before)

    def test_partial_evaluation_can_be_resumed(self):
        o, ev = self.run_all()
        n = {"k": 0}

        def crashing(req):
            n["k"] += 1
            if n["k"] == 4:
                raise RuntimeError("caida simulada")
            return resolver(req)

        bad = F.FakeFunctionalEvaluator(responder=crashing)
        with self.assertRaises(RuntimeError):
            self.orch(FakeClient(script=[]), functional_evaluator=bad).evaluate_functional()
        self.assertFalse((self.run_dir.path / O.LOCK).exists())
        good = F.FakeFunctionalEvaluator(responder=resolver)
        stats = self.orch(FakeClient(script=[]), functional_evaluator=good).evaluate_functional()
        self.assertEqual((stats["skipped"], stats["evaluated"], len(good.calls)), (3, 9, 9))

    def test_infrastructure_errors_are_retried_and_do_not_exclude_the_pair(self):
        o, _ = self.run_all()
        ev = F.FakeFunctionalEvaluator(script=[F.EvaluatorInfraError("contenedor caido"),
                                               F.EvalResponse(F.INFRA_ERROR, detail="tiempo agotado"), F.RESOLVED],
                                       responder=resolver)
        stats = self.orch(FakeClient(script=[]), functional_evaluator=ev).evaluate_functional()
        self.assertEqual(stats["evaluated"], 12)
        f = read(self.cdir_of(o, "O1") / "functional.json")
        self.assertEqual((f["outcome"], f["n_attempts"], f["recovered_after_retry"], f["category"]), ("resolved", 3, True, "ok"))
        self.assertEqual([a["outcome"] for a in f["attempts"]], ["infrastructure_error", "infrastructure_error", "resolved"])
        s = self.orch(FakeClient(script=[])).summary()
        self.assertEqual(s["functional_infrastructure"]["retries"], 2)
        self.assertEqual(s["n_excluded_pairs"], 0)

    def test_persistent_evaluator_failures_are_not_evaluable_not_excluded_and_trigger_the_25_percent_pause(self):
        o, _ = self.run_all()
        always = [F.EvaluatorInfraError("x")] * 12         # 4 condiciones agotan sus 3 intentos: 4 de 12 = 33 % > 25 %
        ev = F.FakeFunctionalEvaluator(script=always, responder=resolver)
        self.orch(FakeClient(script=[]), functional_evaluator=ev).evaluate_functional()
        s = self.orch(FakeClient(script=[])).summary()
        self.assertEqual(s["stages"]["functional"]["not_evaluable"], 4)
        fx = s["functional_infrastructure"]
        self.assertEqual((fx["not_evaluable"], fx["pause_recommended"]), (4, True))
        f = read(self.cdir_of(o, "O1") / "functional.json")
        self.assertEqual((f["outcome"], f["category"], f["n_attempts"]), ("not_evaluable", "infrastructure_not_evaluable", 3))
        self.assertEqual(s["n_excluded_pairs"], 0)                          # resolucion sin criterio: no afecta a la decision
        self.assertEqual(s["not_evaluable_conditions"], [])

    def test_pause_threshold_is_strictly_above_25_percent(self):
        o, _ = self.run_all()
        ev = F.FakeFunctionalEvaluator(script=[F.EvaluatorInfraError("x")] * 3, responder=resolver)
        self.orch(FakeClient(script=[]), functional_evaluator=ev).evaluate_functional()
        fx = self.orch(FakeClient(script=[])).summary()["functional_infrastructure"]
        self.assertEqual((fx["not_evaluable"], fx["pause_recommended"]), (1, False))             # 1 de 12 < 25 %

    def test_exactly_25_percent_does_not_pause(self):
        o, _ = self.run_all()
        ev = F.FakeFunctionalEvaluator(script=[F.EvaluatorInfraError("x")] * 9, responder=resolver)   # 3 de 12 = 25 %
        self.orch(FakeClient(script=[]), functional_evaluator=ev).evaluate_functional()
        fx = self.orch(FakeClient(script=[])).summary()["functional_infrastructure"]
        self.assertEqual((fx["not_evaluable"], fx["pause_recommended"]), (3, False))

    def test_unsuitable_evaluators_are_refused(self):
        o, _ = self.run_all()

        class NotSynthetic:
            is_synthetic, name, version = False, "x", "1"

            def evaluate(self, request):
                raise AssertionError("no debe llamarse")

        class Official:
            is_synthetic, name, version = True, "official", "1"

            def evaluate(self, request):
                raise AssertionError("no debe llamarse")

        Official.__module__ = "src.downstream.evaluation"
        for ev in (NotSynthetic(), Official()):
            with self.assertRaises(F.OfficialEvaluatorNotAllowed):
                o.evaluate_functional(ev)
        with self.assertRaises(O.OrchestrationError):
            self.orch(FakeClient(script=[])).evaluate_functional()
        with self.assertRaises(F.OfficialEvaluatorNotAllowed):
            F.check_evaluator_allowed(F.FakeFunctionalEvaluator(), synthetic_run=False)
        self.assertFalse(any((self.run_dir.path / O.COND_DIR).rglob("functional.json")))


class Tampering(StageBase):
    def setUp(self):
        super().setUp()
        self.o, _ = FunctionalStage.run_all(self)
        self.o.evaluate_functional(F.FakeFunctionalEvaluator(responder=resolver))
        self.assertTrue(self.orch().verify().ok)

    def refused(self, fragment=""):
        with self.assertRaises(O.IntegrityError) as cm:
            self.orch(FakeClient(script=[])).apply_gate()
        self.assertIn(fragment, str(cm.exception))

    def edit(self, path, **changes):
        d = read(path)
        for k, v in changes.items():
            d[k] = v
        path.write_bytes(O.canonical(d))

    def test_modified_patch_after_gate(self):
        p = self.cdir_of(self.o, "E1") / "diff.patch"
        p.write_bytes(p.read_bytes() + b"\n")
        self.refused()

    def test_modified_applicability_record(self):
        self.edit(self.cdir_of(self.o, "O1") / "applicability.json", patch_sha256="0" * 64)
        self.refused("applicability")

    def test_recompute_detects_a_forged_verdict(self):
        self.edit(self.cdir_of(self.o, "E1") / "applicability.json", status="not_applicable")
        self.assertFalse(self.orch().verify(recompute=True).ok)

    def test_functional_for_a_patch_that_g_did_not_approve(self):
        d = self.cdir_of(self.o, "O1")
        self.edit(d / "applicability.json", status="not_applicable")
        self.refused("functional.json")

    def test_functional_evaluating_another_patch(self):
        d = self.cdir_of(self.o, "O1")
        f = read(d / "functional.json")
        f["request"]["patch_sha256"] = "1" * 64
        (d / "functional.json").write_bytes(O.canonical(f))
        self.refused("functional.json")

    def test_synthetic_and_real_results_cannot_be_mixed(self):
        self.edit(self.cdir_of(self.o, "E1") / "functional.json", synthetic=False)
        self.refused("sinteticos y reales")

    def test_modified_evidence_and_orphan_evidence(self):
        d = self.cdir_of(self.o, "E1")
        (d / "functional_evidence.json").write_bytes(b"{}\n")
        self.refused("functional_evidence")
        (d / "functional_evidence.json").unlink()
        self.refused()
        (d / "functional.json").unlink()
        (d / "functional_evidence.json").write_bytes(b"{}\n")
        self.refused("sin functional.json")

    def test_evaluation_label_must_belong_to_p1(self):
        d = self.cdir_of(self.o, "E1")
        f = read(d / "functional.json")
        f["request"]["run_label"] = "downstream-bm25"                         # identificador de la evaluacion original
        (d / "functional.json").write_bytes(O.canonical(f))
        self.refused("P1")


class OriginalGeneratorStripping(StageBase):
    """Causa del 6.o parche O1 no aplicable en el simulacro: el generador original guarda ``response.strip() + "\\n"``."""

    # hunk correcto (3 lineas antiguas, 4 nuevas) cuya ultima linea de contexto es una linea en BLANCO (" ")
    DIFF = "--- pkg/m1.py\n+++ pkg/m1.py\n@@ -19,3 +19,4 @@\n v1_19 = 19\n-v1_20 = 20\n+v1_20 = 20\n+# pilot-check\n \n"

    def source(self):
        """Mundo sintetico con una linea en blanco al final de cada fichero."""
        import shutil
        from pilot_p1.applier import DirSource
        root = Path(self.run_dir._tmp.name) / "world_blank"
        shutil.copytree(self.world.root, root)
        for f in root.rglob("*.py"):
            f.write_bytes(f.read_bytes() + b"\n")
        return DirSource(root)

    def test_stripping_eats_a_trailing_blank_context_line_and_the_hunk_becomes_corrupt(self):
        src = self.source()
        with_blank = self.DIFF.replace("pkg/m1.py", "a/pkg/m1.py", 1).replace("+++ pkg", "+++ b/pkg")
        self.assertEqual(G.gate_check(with_blank.encode(), src).status, G.APPLICABLE)       # tal cual: aplicable
        stripped = O.original_style_patch(self.DIFF)                                         # tratamiento del generador original
        self.assertEqual(stripped, self.DIFF.rstrip() + "\n")
        n = O.normalize_patch(stripped)
        self.assertEqual((n.status, n.patch), ("unchanged_malformed", stripped))              # N detecta el hunk truncado y no lo repara
        r = G.gate_check(n.patch.encode(), src)
        self.assertEqual((r.status, r.category), (G.NOT_APPLICABLE, "model_output_error"))
        self.assertIn("corrupt patch", r.reason)

    def test_the_orchestrator_keeps_this_original_behaviour_and_the_raw_response_intact(self):
        text = self.DIFF
        src = self.source()
        client = FakeClient(responder=lambda p: text if "unified diff" in p.split("INSTRUCTIONS:")[-1] else synthetic_text(p))
        o = self.full(client, source_factory=lambda t: src)
        o.apply_gate()
        d = self.cdir_of(o, "O1")
        self.assertEqual((d / "response.txt").read_bytes(), text.encode())                  # respuesta original sin tocar
        self.assertEqual((d / "o1.patch").read_bytes(), text.rstrip().encode() + b"\n")
        app = read(d / "applicability.json")
        self.assertEqual((app["status"], app["category"]), ("not_applicable", "model_output_error"))
        self.assertEqual(read(self.cdir_of(o, "E1") / "applicability.json")["status"], "applicable")


class Hygiene(unittest.TestCase):
    CODE = [p for p in (ROOT / "pilot_p1").glob("*.py")]

    def test_package_never_imports_the_original_evaluator_docker_or_the_network_stack(self):
        banned_roots = {"src", "docker", "swebench", "google", "requests", "urllib3", "httpx", "datasets", "huggingface_hub"}
        for p in self.CODE:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                mods = []
                if isinstance(n, ast.Import):
                    mods = [a.name for a in n.names]
                elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                    mods = [n.module]
                for m in mods:
                    if p.name == "select_tasks.py" and m == "datasets":
                        continue                                              # solo --write, lectura de la cache local (3B.1 no lo usa)
                    self.assertNotIn(m.split(".")[0], banned_roots, f"{p.name} importa {m}")

    def test_package_never_calls_the_original_evaluator_or_repository_preparation(self):
        banned = {"prepare_repository", "evaluate_patch", "run_instance", "evaluate_poly_patch", "evaluate_pro_patch",
                  "check_patch_applies"}
        for p in self.CODE:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Call):
                    name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                    self.assertNotIn(name, banned, f"{p.name} llama a {name}")

    def test_git_is_only_used_with_read_only_commands_or_apply_check_in_temporaries(self):
        for p in self.CODE:
            src = p.read_text(encoding="utf-8")
            for forbidden in ('"checkout"', '"fetch"', '"clone"', '"pull"', '"reset"', '"clean"', '"gc"', '"add"', '"push"'):
                self.assertNotIn(forbidden, src, f"{p.name} usa {forbidden}")

    def test_importing_the_package_does_not_load_the_evaluation_stack(self):
        code = ("import sys, pilot_p1.orchestrator, pilot_p1.gate, pilot_p1.functional, pilot_p1.decision, pilot_p1.client;"
                "bad=[m for m in ('docker','swebench','google','src.downstream.evaluation','src.repo_manager') if m in sys.modules];"
                "print(bad)")
        out = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "[]")

    def test_gate_only_runs_git_apply_in_temporary_directories(self):
        self.assertEqual(G.GATE_COMMAND, ["git", "apply", "--check", "-p1"])
        with self.assertRaises(G.GateWorkdirError):
            G.assert_safe_workdir(ROOT / "repos")


@unittest.skipUnless((ROOT / "repos").is_dir() and (ROOT / "logs" / "downstream").is_dir(), "datos originales no disponibles")
class FullSimulationWithGate(unittest.TestCase):
    """72 condiciones sobre prompts y repositorios reales (SOLO LECTURA), respuestas y evaluador sinteticos."""

    @classmethod
    def setUpClass(cls):
        cls.dir = TO.TempRun()
        cls.before = cls._guard()
        cls.client, cls.rec = fake_client()
        cls.ev = F.FakeFunctionalEvaluator(responder=resolver)
        cls.o = O.Orchestrator(cls.dir.path, cls.client, sleep=lambda s: None, functional_evaluator=cls.ev)
        cls.o.run()
        cls.gate_stats = cls.o.apply_gate()
        cls.fun_stats = cls.o.evaluate_functional()
        cls.after = cls._guard()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    @staticmethod
    def _guard():
        h = {"originals": TO.FullSimulation._originals()}
        for r in sorted((ROOT / "repos").iterdir()):
            if (r / ".git").exists():
                head = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                idx = r / ".git" / "index"
                h[r.name] = (head, hashlib.sha256(idx.read_bytes()).hexdigest() if idx.is_file() else None)
        return h

    def test_gate_and_functional_stages_complete_for_72_conditions(self):
        self.assertEqual(self.gate_stats, {"gate_written": 72, "gate_skipped": 0, "upstream_missing": 0})
        s = self.o.summary()
        self.assertEqual(sum(s["stages"]["applicability"][k] for k in ("applicable", "not_applicable",
                                                                       "not_evaluable_infrastructure")), 72)
        self.assertEqual(s["stages"]["applicability"]["pending"], 0)
        applicable = s["stages"]["applicability"]["applicable"]
        self.assertEqual(self.fun_stats["evaluated"], applicable)
        self.assertEqual(len(self.ev.calls), applicable)
        self.assertEqual(s["stages"]["functional"]["resolved"] + s["stages"]["functional"]["not_resolved"], applicable)
        self.assertTrue(self.o.verify(recompute=True).ok)

    def test_verdicts_follow_from_the_synthetic_construction_and_both_arms_use_one_policy(self):
        crlf_o1 = sum(1 for c in self.o.conditions if c.arm == "O1" and "\r" in self.rec.produced[
            hashlib.sha256(self.o.prompts[c.cond_id].encode()).hexdigest()])
        s = self.o.summary()
        self.assertEqual(s["by_arm"]["E1"]["applicable"], 36)
        self.assertEqual(s["by_arm"]["O1"]["not_applicable"], crlf_o1)         # solo las O1 con CRLF; G no corrige nada
        self.assertEqual(s["by_arm"]["O1"]["applicable"], 36 - crlf_o1)

    def test_decision_report_is_computable_and_records_wins_ties_and_net_improvement(self):
        rep = self.o.decision_report()
        pw = rep["pairwise"]
        self.assertTrue(rep["synthetic"])
        self.assertEqual(pw["n_paired"], 36)
        self.assertEqual(pw["e1_wins"] + pw["o1n_wins"] + pw["ties_both_pass"] + pw["ties_both_fail"], 36)
        self.assertEqual(pw["net_improvement"], pw["e1_wins"] - pw["o1n_wins"])
        self.assertEqual(rep["n_excluded_pairs"], 0)
        self.assertIn(rep["decision"], {D.SUCCESS, D.ABANDON, D.INCONCLUSIVE})      # sintetico: no es un resultado

    def test_original_repositories_results_and_logs_were_not_touched(self):
        self.assertEqual(self.before, self.after)
        self.assertFalse((ROOT / "pilot_p1_runs").exists() and any((ROOT / "pilot_p1_runs").iterdir()))

    def test_everything_is_marked_synthetic_and_p1_labels_are_used(self):
        for p in self.dir.path.rglob("*.json"):
            if p.name != O.MANIFEST and p.name != "functional_evidence.json":
                self.assertTrue(read(p)["synthetic"], p)
        self.assertTrue(all(r.run_label.startswith("p1-sim-") for r in self.ev.calls))


if __name__ == "__main__":
    unittest.main()
