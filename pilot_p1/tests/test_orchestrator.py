"""Simulacros de la orquestacion (fase 3A): solo clientes falsos y respuestas sinteticas; sin API real."""
import ast
import hashlib
import itertools
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pilot_p1 import applier as A
from pilot_p1 import client as C
from pilot_p1 import orchestrator as O
from pilot_p1 import prompts as P
from pilot_p1 import select_tasks as S
from pilot_p1.client import APIError, FakeClient
from pilot_p1.tests.helpers import git, make_repo, tree_digest
from pilot_p1.tests.sim_helpers import Recorder, SyntheticWorld, TempRun, fake_client, synthetic_text

ROOT = O.PROJECT_ROOT
GENERATION = ROOT / "src" / "downstream" / "generation.py"


def clock():
    c = itertools.count(1)
    return lambda: f"2026-11-12T00:00:{next(c) % 60:02d}.{next(c):06d}Z"


class Base(unittest.TestCase):
    def setUp(self):
        self.run_dir = TempRun()
        self.addCleanup(self.run_dir.cleanup)
        self.world = SyntheticWorld(Path(self.run_dir._tmp.name), n_tasks=2)
        self.sleeps = []

    def orch(self, client=None, out=None, **kw):
        client = client or fake_client()[0]
        kw.setdefault("task_ids", self.world.task_ids)
        kw.setdefault("prompt_provider", self.world.prompt_provider)
        kw.setdefault("source_factory", self.world.source_factory)
        return O.Orchestrator(out or self.run_dir.path, client, clock=clock(), sleep=self.sleeps.append, **kw)

    def cond_dir(self, n=0, arm=None):
        o = self.orch()
        c = [x for x in o.conditions if arm is None or x.arm == arm][n]
        return self.run_dir.path / O.COND_DIR / c.cond_id

    def digest(self, skip=("events.jsonl", "RUN.lock")):
        h = hashlib.sha256()
        for p in sorted(self.run_dir.path.rglob("*"), key=lambda q: q.as_posix()):
            if p.is_file() and p.name not in skip:
                h.update(p.relative_to(self.run_dir.path).as_posix().encode() + p.read_bytes())
        return h.hexdigest()

    def complete_run(self):
        client, rec = fake_client()
        stats = self.orch(client).run()
        return client, rec, stats


class Conditions(unittest.TestCase):
    def test_72_conditions_from_the_frozen_selection(self):
        ids = O.selection_from_manifest()
        conds = O.build_conditions(ids)
        self.assertEqual(len(conds), 72)
        self.assertEqual(len({c.cond_id for c in conds}), 72)
        self.assertEqual(S.selection_hash(ids), "6dbd0c9f9365690c")
        self.assertEqual(len({c.pair_id for c in conds}), 36)
        self.assertEqual({(c.method) for c in conds}, {"bm25", "semantic", "hybrid"})
        self.assertEqual({c.arm for c in conds}, {"O1", "E1"})
        for i in range(0, 72, 2):                       # el par O1/E1 es consecutivo, O1 primero
            self.assertEqual((conds[i].arm, conds[i + 1].arm, conds[i].pair_id), ("O1", "E1", conds[i + 1].pair_id))

    def test_condition_ids_are_stable_and_unique_per_task(self):
        a, b = O.build_conditions(["x", "y"]), O.build_conditions(["x", "y"])
        self.assertEqual([c.cond_id for c in a], [c.cond_id for c in b])
        self.assertNotEqual(O.build_conditions(["x"])[0].cond_id, O.build_conditions(["y"])[0].cond_id)


class FullSimulation(unittest.TestCase):
    """Simulacro completo de las 72 condiciones sobre los prompts y repositorios reales (lectura) y respuestas sinteticas."""

    @classmethod
    def setUpClass(cls):
        cls.dir = TempRun()
        cls.before = cls._originals()
        cls.client, cls.rec = fake_client()
        cls.orch = O.Orchestrator(cls.dir.path, cls.client, clock=clock(), sleep=lambda s: None)
        cls.stats = cls.orch.run()
        cls.after = cls._originals()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    @staticmethod
    def _originals():
        h = hashlib.sha256()
        for p in sorted((ROOT / "results").glob("*")):
            if p.is_file():
                h.update(p.read_bytes())
        sizes = sorted((str(p.relative_to(ROOT)), p.stat().st_size) for p in (ROOT / "logs" / "downstream").glob("*/*/*"))
        return h.hexdigest(), hashlib.sha256(json.dumps(sizes).encode()).hexdigest()

    def test_stats_and_call_sequence(self):
        self.assertEqual(self.stats, {"new_generations": 72, "skipped_generations": 0, "derived_written": 72 * 2,
                                      "not_evaluable": 0})
        calls = self.client.calls
        self.assertEqual(len(calls), 72)
        for call, cond in zip(calls, self.orch.conditions):
            self.assertEqual(call["prompt"], self.orch.prompts[cond.cond_id])
            self.assertEqual((call["model"], call["max_output_tokens"], call["thinking_level"]),
                             ("gemini-3.5-flash-lite", 4096, "minimal"))
        self.assertEqual([c.arm for c in self.orch.conditions[:4]], ["O1", "E1", "O1", "E1"])

    def test_manifest_metadata(self):
        m = json.loads((self.dir.path / O.MANIFEST).read_bytes())
        self.assertEqual((m["model"], m["max_output_tokens"], m["thinking_level"], m["max_api_attempts"],
                          m["max_apply_attempts"]), ("gemini-3.5-flash-lite", 4096, "minimal", 3, 3))
        self.assertEqual((m["protocol_commit"], m["synthetic"], m["n_conditions"], m["selection_hash"]),
                         ("fb589c13129e6da2c8302cd243bc151dff598158", True, 72, "6dbd0c9f9365690c"))
        self.assertIn("NO son resultados experimentales", m["warning"])
        self.assertEqual(m["e1_instructions_sha256"], P.E1_INSTRUCTIONS_SHA256)
        self.assertTrue(m["run_id"].startswith("p1-sim-"))
        self.assertEqual(m["tasks"], O.selection_from_manifest())

    def test_o1_and_e1_share_exactly_the_same_context(self):
        m = json.loads((self.dir.path / O.MANIFEST).read_bytes())
        by_pair = {}
        for r in m["conditions"]:
            by_pair.setdefault(r["pair_id"], []).append(r)
        self.assertEqual(len(by_pair), 36)
        for pair, (o1, e1) in by_pair.items():
            self.assertEqual((o1["arm"], e1["arm"]), ("O1", "E1"))
            for k in ("shared_sha256", "issue_sha256", "chunk_order_sha256", "n_chunks"):
                self.assertEqual(o1[k], e1[k], pair)
            self.assertNotEqual(o1["prompt_sha256"], e1["prompt_sha256"])
            po = P.split_prompt((self.dir.path / O.COND_DIR / o1["cond_id"] / "prompt.txt").read_bytes().decode("utf-8"))
            pe = P.split_prompt((self.dir.path / O.COND_DIR / e1["cond_id"] / "prompt.txt").read_bytes().decode("utf-8"))
            self.assertEqual((po.shared, po.chunks), (pe.shared, pe.chunks))

    def test_responses_are_stored_byte_for_byte(self):
        for c in self.orch.conditions:
            d = self.dir.path / O.COND_DIR / c.cond_id
            sent = hashlib.sha256(self.orch.prompts[c.cond_id].encode("utf-8")).hexdigest()
            self.assertEqual((d / "response.txt").read_bytes(), self.rec.produced[sent].encode("utf-8"), c.cond_id)
        kinds = {hashlib.sha256(t.encode()).hexdigest() for t in self.rec.produced.values()}
        self.assertGreater(len(kinds), 3)
        self.assertTrue(any("\r\n" in t for t in self.rec.produced.values()))      # CRLF conservados
        self.assertTrue(any(t.startswith("```") for t in self.rec.produced.values()))
        self.assertTrue(any(t.startswith("\n\n") for t in self.rec.produced.values()))

    def test_integrity_verification_passes_and_recomputes(self):
        rep = self.orch.verify(recompute=True)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.warnings, [])
        self.assertEqual(rep.stats["sealed"], 72)

    def test_everything_is_marked_synthetic(self):
        n = 0
        for p in self.dir.path.rglob("*.json"):
            if p.name == O.MANIFEST:
                continue
            self.assertTrue(json.loads(p.read_bytes())["synthetic"], p)
            n += 1
        self.assertEqual(n, 72 * 3)                               # generation + format_metrics + (conversion|normalization)
        self.assertTrue(self.dir.path.name.startswith("simulacro_"))

    def test_summary_separates_stages_and_errors(self):
        s = self.orch.summary()
        self.assertEqual((s["stages"]["generation"], s["stages"]["format_metrics"], s["stages"]["conversion_E1"],
                          s["stages"]["normalization_O1"]), (72, 72, 36, 36))
        self.assertEqual((s["stages"]["applicability"], s["stages"]["resolution"]), ("pending_phase_3B",) * 2)
        self.assertEqual(s["statuses"], {"E1:patch_ready": 36, "O1:normalized": 36})
        self.assertEqual((s["model_output_errors"], s["not_evaluable_conditions"], s["n_excluded_pairs"]), ({}, [], 0))
        self.assertEqual(s["infrastructure"], {"api_failures": 0, "apply_retries": 0, "recovered_after_retry": 0})
        fenced = sum(1 for t in self.rec.produced.values() if t.startswith("```"))
        self.assertEqual(s["format"]["external_fences"], fenced)
        self.assertEqual((s["format"]["fences_union"], s["format"]["original_metric_a"]), (fenced, fenced))   # union = metrica original
        self.assertEqual(s["format"]["e1_with_fences_and_parseable"], sum(
            1 for c in self.orch.conditions if c.arm == "E1" and self.rec.produced[
                hashlib.sha256(self.orch.prompts[c.cond_id].encode()).hexdigest()].startswith("```")))
        self.assertEqual(s["format"]["e1_parseable"], 36)
        self.assertEqual(s["format"]["inner_fences"], 0)

    def test_conversion_and_normalization_records(self):
        e1 = self.dir.path / O.COND_DIR / self.orch.conditions[1].cond_id
        conv = json.loads((e1 / "conversion.json").read_bytes())
        self.assertEqual((conv["status"], conv["category"], conv["n_attempts"], conv["model_fault"]),
                         ("patch_ready", "ok", 1, False))
        self.assertEqual(hashlib.sha256((e1 / "diff.patch").read_bytes()).hexdigest(), conv["diff_sha256"])
        o1 = self.dir.path / O.COND_DIR / self.orch.conditions[0].cond_id
        norm = json.loads((o1 / "normalization.json").read_bytes())
        self.assertEqual((norm["status"], norm["changed"], norm["applicability"]), ("normalized", True, "pending_phase_3B"))
        self.assertNotEqual((o1 / "o1.patch").read_bytes(), (o1 / "o1n.patch").read_bytes())

    def test_event_log_is_complete_and_chained(self):
        events = O.EventLog.read(self.dir.path / O.EVENTS)
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "run_started")
        for t, n in (("prompt_written", 72), ("api_attempt_started", 72), ("api_response_received", 72),
                     ("generation_sealed", 72)):
            self.assertEqual(types.count(t), n, t)
        self.assertEqual(types.count("stage_written"), 72 * 2)

    def test_original_experiment_was_not_touched(self):
        self.assertEqual(self.before, self.after)
        self.assertFalse(str(self.dir.path).startswith(str(ROOT)))


class Resume(Base):
    def test_resume_after_partial_run_does_not_duplicate(self):
        client1, rec1 = fake_client()
        s1 = self.orch(client1).run(max_new_generations=5)
        self.assertEqual((s1["new_generations"], len(client1.calls)), (5, 5))
        client2, _ = fake_client()
        s2 = self.orch(client2).run()
        self.assertEqual((s2["new_generations"], s2["skipped_generations"], len(client2.calls)), (7, 5, 7))
        done = [c for c in self.orch().conditions]
        for c in done:
            self.assertTrue((self.run_dir.path / O.COND_DIR / c.cond_id / "generation.json").exists())
        called = {hashlib.sha256(x["prompt"].encode()).hexdigest() for x in client1.calls + client2.calls}
        self.assertEqual(len(called), 12)                          # ningun prompt se envio dos veces
        self.assertEqual(len(client1.calls) + len(client2.calls), 12)

    def test_resume_of_a_complete_run_makes_no_calls_and_changes_nothing(self):
        self.complete_run()
        before = self.digest()
        silent = FakeClient(script=[])
        stats = self.orch(silent).run()
        self.assertEqual((stats["new_generations"], stats["skipped_generations"], stats["derived_written"], silent.calls),
                         (0, 12, 0, []))
        self.assertEqual(self.digest(), before)
        events = [e["type"] for e in O.EventLog.read(self.run_dir.path / O.EVENTS)]
        self.assertEqual(events.count("run_resumed"), 1)

    def test_crash_mid_run_is_detected_and_not_repeated_automatically(self):
        responder = fake_client()[1]
        n = {"k": 0}

        def crashing(prompt):
            n["k"] += 1
            if n["k"] == 4:
                raise RuntimeError("caida simulada")
            return responder(prompt)

        with self.assertRaises(RuntimeError):
            self.orch(FakeClient(responder=crashing)).run()
        self.assertFalse((self.run_dir.path / O.LOCK).exists())             # el bloqueo se libera
        c2 = FakeClient(script=[])
        with self.assertRaises(O.InterruptedConditionError):                # por defecto: decision manual
            self.orch(c2).run()
        self.assertEqual(c2.calls, [])
        c3, _ = fake_client()
        stats = self.orch(c3, on_interrupted="retry").run()
        self.assertEqual((stats["skipped_generations"], stats["new_generations"], len(c3.calls)), (3, 9, 9))
        self.assertIn("interrupted_retry", [e["type"] for e in O.EventLog.read(self.run_dir.path / O.EVENTS)])
        self.assertTrue(self.orch(fake_client()[0]).verify(recompute=True).ok)

    def test_response_saved_but_not_sealed_is_recovered_without_calling_again(self):
        with mock.patch.object(O.Orchestrator, "_write_generation", side_effect=RuntimeError("caida")):
            with self.assertRaises(RuntimeError):
                self.orch().run()
        d = self.cond_dir(0)
        self.assertTrue((d / "response.txt").exists() and not (d / "generation.json").exists())
        client, _ = fake_client()
        stats = self.orch(client).run()
        self.assertEqual((len(client.calls), stats["new_generations"], stats["skipped_generations"]), (11, 11, 1))
        gen = json.loads((d / "generation.json").read_bytes())
        self.assertTrue(gen["recovered_from_event"])

    def test_stale_lock_blocks_a_second_run(self):
        self.orch().run(max_new_generations=1)
        (self.run_dir.path / O.LOCK).write_bytes(b"pid=1\n")
        with self.assertRaises(O.OrchestrationError):
            self.orch().run()

    def test_incompatible_configuration_is_refused(self):
        self.orch().run(max_new_generations=1)
        with self.assertRaises(O.IntegrityError):
            self.orch(task_ids=list(reversed(self.world.task_ids))).run()
        with self.assertRaises(O.IntegrityError):
            self.orch(max_apply_attempts=2).run()


class IntegrityDetection(Base):
    def setUp(self):
        super().setUp()
        self.complete_run()

    def assertRefused(self, fragment=""):
        with self.assertRaises(O.IntegrityError) as cm:
            self.orch(FakeClient(script=[])).run()
        self.assertIn(fragment, str(cm.exception))
        rep = self.orch().verify()
        self.assertFalse(rep.ok)

    def test_modified_response(self):
        p = self.cond_dir(0) / "response.txt"
        p.write_bytes(p.read_bytes() + b"x")
        self.assertRefused("response.txt")

    def test_deleted_response(self):
        (self.cond_dir(0) / "response.txt").unlink()
        self.assertRefused()

    def test_modified_generation_record(self):
        p = self.cond_dir(0) / "generation.json"
        d = json.loads(p.read_bytes())
        d["usage"]["total"] += 1
        p.write_bytes(O.canonical(d))
        self.assertRefused("generation.json")

    def test_modified_prompt(self):
        p = self.cond_dir(0) / "prompt.txt"
        p.write_bytes(p.read_bytes().replace(b"Issue", b"ISSUE", 1))
        self.assertRefused("prompt.txt")

    def test_modified_derived_stage(self):
        p = self.cond_dir(0) / "normalization.json"
        d = json.loads(p.read_bytes())
        d["response_sha256"] = "0" * 64
        p.write_bytes(O.canonical(d))
        self.assertRefused("normalization.json")

    def test_modified_diff(self):
        p = self.cond_dir(0, "E1") / "diff.patch"
        p.write_bytes(p.read_bytes() + b"\n")
        self.assertRefused("diff.patch")

    def test_truncated_event_log(self):
        p = self.run_dir.path / O.EVENTS
        p.write_bytes(p.read_bytes()[:-15])
        self.assertRefused("truncada")

    def test_broken_hash_chain(self):
        p = self.run_dir.path / O.EVENTS
        lines = p.read_bytes().split(b"\n")
        lines[5] = lines[5].replace(b"cond_id", b"cond_ib", 1)
        p.write_bytes(b"\n".join(lines))
        self.assertRefused("cadena")

    def test_missing_event_log(self):
        (self.run_dir.path / O.EVENTS).unlink()
        self.assertRefused()

    def test_altered_manifest(self):
        p = self.run_dir.path / O.MANIFEST
        d = json.loads(p.read_bytes())
        d["model"] = "otro-modelo"
        p.write_bytes(O.canonical(d))
        self.assertRefused()

    def test_unexpected_file_and_directory(self):
        (self.cond_dir(0) / "notas.txt").write_bytes(b"x")
        self.assertRefused("inesperado")
        (self.cond_dir(0) / "notas.txt").unlink()
        (self.run_dir.path / O.COND_DIR / "otra-condicion").mkdir()
        self.assertRefused("desconocido")

    def test_event_without_file(self):
        (self.cond_dir(1) / "generation.json").unlink()
        self.assertRefused()

    def test_incomplete_temporary_file_is_only_a_warning(self):
        (self.cond_dir(0) / "response.txt.123.abc.tmp").write_bytes(b"parcial")
        rep = self.orch().verify()
        self.assertTrue(rep.ok)
        self.assertTrue(any("temporal" in w for w in rep.warnings))
        self.orch(FakeClient(script=[])).run()                      # y la reanudacion continua

    def test_recompute_detects_a_forged_derived_file(self):
        p = self.cond_dir(0) / "format_metrics.json"
        d = json.loads(p.read_bytes())
        d["external_fence_lines"] = 99
        p.write_bytes(O.canonical(d))
        self.assertTrue(self.orch().verify().ok)                    # coherente en hashes...
        self.assertFalse(self.orch().verify(recompute=True).ok)     # ...pero no se reproduce


class NoOverwrite(Base):
    def test_write_new_refuses_to_overwrite(self):
        p = self.run_dir.path.parent / "x.bin"
        O.write_new(p, b"uno")
        with self.assertRaises(O.OverwriteError):
            O.write_new(p, b"dos")
        self.assertEqual(p.read_bytes(), b"uno")
        self.assertEqual([q.name for q in p.parent.glob("*.tmp")], [])

    def test_existing_artifacts_are_never_rewritten_on_resume(self):
        self.complete_run()
        stamps = {p: p.stat().st_mtime_ns for p in self.run_dir.path.rglob("*") if p.is_file() and p.name != O.EVENTS}
        self.orch(FakeClient(script=[])).run()
        for p, t in stamps.items():
            self.assertEqual(p.stat().st_mtime_ns, t, p)


class Errors(Base):
    def test_transient_errors_are_retried_with_the_original_waits_and_recorded(self):
        rec = Recorder()
        client = FakeClient(script=[APIError(503), APIError(429)], responder=rec)
        self.orch(client).run(max_new_generations=1)
        gen = json.loads((self.cond_dir(0) / "generation.json").read_bytes())
        self.assertEqual([(a["attempt"], a["outcome"]) for a in gen["attempts"]],
                         [(1, "api_error"), (2, "api_error"), (3, "response")])
        self.assertEqual(self.sleeps, [10, 20])
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(gen["category"], "ok")

    def test_exhausted_transient_errors_make_the_condition_not_evaluable_by_infrastructure(self):
        client = FakeClient(script=[], responder=fake_client()[1])
        client._script = [APIError(503), APIError(429), APIError(503)]
        # la primera condicion (O1 del par 0) se agota; el resto sigue
        o = self.orch(client)
        o.run()
        d = self.cond_dir(0)
        self.assertTrue((d / "generation_failed.json").exists() and not (d / "generation.json").exists())
        rec = json.loads((d / "generation_failed.json").read_bytes())
        self.assertEqual((rec["category"], rec["status"], len(rec["attempts"])), ("infrastructure_not_evaluable", "api_error", 3))
        s = o.summary()
        self.assertEqual(s["infrastructure"]["api_failures"], 3)
        self.assertEqual(s["not_evaluable_conditions"], [o.conditions[0].cond_id])
        self.assertEqual(s["n_excluded_pairs"], 1)                              # el par entero se excluye
        self.assertEqual(s["model_output_errors"], {})
        self.assertEqual(s["stages"]["generation"], 11)
        self.assertEqual(len(client.calls), 14)                                 # 3 intentos + 11 condiciones
        types = [e["type"] for e in O.EventLog.read(self.run_dir.path / O.EVENTS)]
        self.assertEqual(types.count("condition_not_evaluable"), 1)
        # reanudar no vuelve a intentar una condicion ya declarada no evaluable
        again = FakeClient(script=[])
        self.orch(again).run()
        self.assertEqual(again.calls, [])

    def test_permanent_error_is_not_retried(self):
        client = FakeClient(script=[APIError(400, "invalid")], responder=fake_client()[1])
        self.orch(client).run(max_new_generations=1)
        rec = json.loads((self.cond_dir(0) / "generation_failed.json").read_bytes())
        self.assertEqual((len(rec["attempts"]), rec["attempts"][0]["retryable"]), (1, False))
        self.assertEqual(self.sleeps, [])

    def test_empty_and_none_responses_are_model_output_errors_not_infrastructure(self):
        client = FakeClient(script=["", None, "   \n"], responder=fake_client()[1])
        o = self.orch(client)
        o.run()
        s = o.summary()
        self.assertEqual(s["model_output_errors"]["empty_response"], 3)
        self.assertEqual((s["not_evaluable_conditions"], s["infrastructure"]["api_failures"]), ([], 0))
        gen = json.loads((self.cond_dir(0) / "generation.json").read_bytes())
        self.assertEqual((gen["status"], gen["category"]), ("empty_response", "model_output_error"))
        self.assertEqual((self.cond_dir(0) / "response.txt").read_bytes(), b"")
        evs = [e for e in O.EventLog.read(self.run_dir.path / O.EVENTS) if e["type"] == "api_response_received"]
        self.assertTrue(evs[1]["text_was_none"])
        norm = json.loads((self.cond_dir(0) / "normalization.json").read_bytes())
        self.assertEqual(norm["status"], "unchanged_no_headers")
        conv = json.loads((self.cond_dir(1) / "conversion.json").read_bytes())
        self.assertEqual((conv["status"], conv["category"]), ("parse_error", "model_output_error"))

    def test_model_output_errors_are_not_retried_in_conversion(self):
        bad = {"search": "FILE: pkg/m1.py\n<<<<<<< SEARCH\nno existe\n=======\nx\n>>>>>>> REPLACE\n", "parse": "hola"}
        for kind, text in bad.items():
            with self.subTest(kind=kind):
                self.setUp()
                client = FakeClient(responder=lambda prompt, t=text: t if "SEARCH" in prompt.split("INSTRUCTIONS:")[-1]
                                    else synthetic_text(prompt))
                with mock.patch.object(O.A, "apply_text", wraps=A.apply_text) as ap:
                    o = self.orch(client)
                    o.run()
                self.assertEqual(ap.call_count, 6)                          # una sola aplicacion por condicion E1
                s = o.summary()
                self.assertEqual(s["infrastructure"]["apply_retries"], 0)
                self.assertEqual(s["not_evaluable_conditions"], [])
                self.assertEqual(sum(s["model_output_errors"].values()), 6)
                self.assertEqual(len(client.calls), 12)

    def test_infrastructure_errors_in_conversion_are_retried_up_to_three_times_with_the_same_response(self):
        n = {"k": 0}
        w = self.world

        def flaky(task_id):
            n["k"] += 1
            if n["k"] <= 2:
                raise A.SourceError("git no responde")
            return w.source_factory(task_id)

        client, rec = fake_client()
        o = self.orch(client, source_factory=flaky)
        o.run()
        conv = json.loads((self.cond_dir(0, "E1") / "conversion.json").read_bytes())
        self.assertEqual((conv["status"], conv["n_attempts"], conv["recovered_after_retry"], conv["category"]),
                         ("patch_ready", 3, True, "ok"))
        self.assertEqual([a["status"] for a in conv["attempts"]], ["environment_error", "environment_error", "patch_ready"])
        self.assertEqual(len(client.calls), 12)                                 # no se regenero nada
        s = o.summary()
        self.assertEqual((s["infrastructure"]["apply_retries"], s["infrastructure"]["recovered_after_retry"]), (2, 1))
        self.assertEqual(s["n_excluded_pairs"], 0)

    def test_persistent_infrastructure_errors_exclude_the_pair_and_are_not_model_errors(self):
        client, _ = fake_client()

        def broken(task_id):
            raise A.SourceError("disco no disponible")

        o = self.orch(client, source_factory=broken)
        o.run()
        s = o.summary()
        self.assertEqual(s["statuses"]["E1:not_evaluable_infrastructure"], 6)
        self.assertEqual(s["model_output_errors"], {})
        self.assertEqual(len(s["not_evaluable_conditions"]), 6)
        self.assertEqual(s["n_excluded_pairs"], 6)                              # un par por cada E1 no evaluable
        self.assertEqual(s["infrastructure"]["apply_retries"], 12)              # 3 intentos por condicion = 2 reintentos
        conv = json.loads((self.cond_dir(0, "E1") / "conversion.json").read_bytes())
        self.assertEqual((conv["n_attempts"], conv["category"], conv["model_fault"]), (3, "infrastructure_not_evaluable", False))
        self.assertEqual(len(client.calls), 12)

    def test_real_git_failure_during_conversion_is_infrastructure(self):
        repo = Path(self.run_dir._tmp.name) / "repo"
        commit = make_repo(repo, {"pkg/m1.py": b"a\n"})
        tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
        src = A.GitSource(repo, commit)
        obj = repo / ".git" / "objects" / tree[:2] / tree[2:]
        os.chmod(obj, stat.S_IWRITE)
        obj.unlink()
        client, _ = fake_client()
        o = self.orch(client, source_factory=lambda t: src)
        o.run()
        self.assertEqual(o.summary()["statuses"]["E1:not_evaluable_infrastructure"], 6)


class Isolation(unittest.TestCase):
    def test_forbidden_and_unsafe_output_dirs_are_rejected_without_creating_anything(self):
        for sub in ("src", "repos", "results", "logs", "diagnostics", "docs", "pilot_p1", "external"):
            with self.subTest(sub=sub):
                p = ROOT / sub / "simulacro_x"
                with self.assertRaises(O.OutputDirError):
                    O.validate_output_dir(p)
                self.assertFalse(p.exists())
        for bad in (ROOT, ROOT.parent, ROOT / "simulacro_x", ROOT / "otra" / "simulacro_x", "relativo/simulacro_x"):
            with self.subTest(bad=str(bad)), self.assertRaises(O.OutputDirError):
                O.validate_output_dir(bad)

    def test_only_the_dedicated_runs_folder_is_allowed_inside_the_project(self):
        p = O.RUNS_ROOT / "simulacro_ok"
        self.assertEqual(O.validate_output_dir(p), p.resolve())
        self.assertFalse(p.exists())                                       # validar no crea nada

    def test_name_prefix_distinguishes_simulations_from_real_runs(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(O.OutputDirError):
                O.validate_output_dir(Path(d) / "p1_run_1", synthetic=True)
            with self.assertRaises(O.OutputDirError):
                O.validate_output_dir(Path(d) / "simulacro_1", synthetic=False)
            O.validate_output_dir(Path(d) / "p1_run_1", synthetic=False)

    def test_git_trees_and_foreign_directories_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(Path(d) / "r", {"a": b"1\n"})
            with self.assertRaises(O.OutputDirError):
                O.validate_output_dir(Path(d) / "r" / "simulacro_x")
            ok = Path(d) / "simulacro_nuevo"
            self.assertEqual(O.validate_output_dir(ok), Path(os.path.realpath(ok)))      # no existe: valido
            f = Path(d) / "simulacro_file"
            f.write_bytes(b"x")
            with self.assertRaises(O.OutputDirError):
                O.validate_output_dir(f)
            g = Path(d) / "simulacro_lleno"
            g.mkdir()
            (g / "otro.txt").write_bytes(b"x")
            with self.assertRaises(O.OutputDirError):
                O.validate_output_dir(g)

    def test_real_clients_are_not_allowed_in_phase_3A(self):
        class Real:
            is_synthetic = False

            def generate(self, *a, **k):
                raise AssertionError("no debe llamarse")

        class NoFlag:
            def generate(self, *a, **k):
                raise AssertionError("no debe llamarse")

        with tempfile.TemporaryDirectory() as d:
            for cl in (Real(), NoFlag()):
                with self.assertRaises(O.RealClientNotAllowed):
                    O.Orchestrator(Path(d) / "simulacro_x", cl)

    def test_run_ids_do_not_collide_with_original_ones(self):
        with tempfile.TemporaryDirectory() as d:
            w = SyntheticWorld(Path(d), 1)
            o = O.Orchestrator(Path(d) / "simulacro_r", fake_client()[0], task_ids=w.task_ids, prompt_provider=w.prompt_provider,
                               source_factory=w.source_factory, sleep=lambda s: None)
            o.run(max_new_generations=1)
            rid = json.loads((o.out / O.MANIFEST).read_bytes())["run_id"]
        self.assertTrue(rid.startswith("p1-sim-"))
        originals = set()
        for sub in ("run_evaluation", "downstream"):
            p = ROOT / "logs" / sub
            if p.is_dir():
                originals.update(x.name for x in p.iterdir())
        self.assertNotIn(rid, originals)
        self.assertFalse(any(n.startswith("p1-") for n in originals))

    def test_no_original_artifact_is_written_during_a_simulation(self):
        with tempfile.TemporaryDirectory() as d:
            w = SyntheticWorld(Path(d), 1)
            before = FullSimulation._originals()
            O.Orchestrator(Path(d) / "simulacro_r", fake_client()[0], task_ids=w.task_ids, prompt_provider=w.prompt_provider,
                           source_factory=w.source_factory, sleep=lambda s: None).run()
            self.assertEqual(FullSimulation._originals(), before)
            self.assertFalse((ROOT / "pilot_p1_runs").exists() and any((ROOT / "pilot_p1_runs").iterdir()))


class RunsFolder(unittest.TestCase):
    def test_runs_folder_is_ignored_by_git_so_runs_cannot_be_added_by_accident(self):
        import subprocess
        for rel in ("pilot_p1_runs/simulacro_x/RUN_MANIFEST.json", "pilot_p1_runs/p1_run_1/conditions/c00/response.txt",
                    "pilot_p1_runs/x"):
            r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel])
            self.assertEqual(r.returncode, 0, rel)
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "pilot_p1/README.md"])
        self.assertEqual(r.returncode, 1)                                  # el paquete no queda ignorado

    def test_runs_folder_is_the_only_allowed_place_inside_the_project(self):
        self.assertEqual(O.RUNS_ROOT, ROOT / "pilot_p1_runs")
        self.assertNotIn("pilot_p1_runs", O.FORBIDDEN_TOP)
        for ok in ("simulacro_a", "p1_run_a"):
            O.validate_output_dir(O.RUNS_ROOT / ok, synthetic=ok.startswith("sim"))
        with self.assertRaises(O.OutputDirError):
            O.validate_output_dir(O.RUNS_ROOT, synthetic=True)                      # la carpeta en si no, y debe llamarse simulacro_*
        with self.assertRaises(O.OutputDirError):
            O.validate_output_dir(ROOT / "pilot_p1_runs" / ".." / "results" / "simulacro_x")

    def test_validation_alone_never_creates_the_runs_folder(self):
        existed = O.RUNS_ROOT.exists()
        O.validate_output_dir(O.RUNS_ROOT / "simulacro_a")
        self.assertEqual(O.RUNS_ROOT.exists(), existed)


class Interfaces(unittest.TestCase):
    def test_client_constants_match_the_original_generator(self):
        tree = ast.parse(GENERATION.read_text(encoding="utf-8"))
        vals = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
                try:
                    vals[n.targets[0].id] = ast.literal_eval(n.value)
                except ValueError:
                    pass
        self.assertEqual((C.MODEL, C.MAX_OUTPUT_TOKENS, C.THINKING_LEVEL, C.MAX_API_ATTEMPTS, set(C.RETRYABLE_API_CODES)),
                         (vals["MODEL"], vals["MAX_OUTPUT_TOKENS"], vals["THINKING_LEVEL"], vals["MAX_API_ATTEMPTS"],
                          vals["RETRYABLE_API_CODES"]))

    def test_fake_client_records_calls_and_raises_scripted_errors(self):
        fc = FakeClient(script=["a", APIError(503)])
        r = fc.generate("p", model="m", max_output_tokens=1, thinking_level="minimal")
        self.assertEqual((r.text, fc.calls[0]["prompt"]), ("a", "p"))
        with self.assertRaises(APIError):
            fc.generate("q", model="m", max_output_tokens=1, thinking_level="minimal")
        with self.assertRaises(AssertionError):
            fc.generate("r", model="m", max_output_tokens=1, thinking_level="minimal")
        self.assertTrue(fc.is_synthetic)
        self.assertEqual(len(fc.calls), 3)

    def test_no_real_api_client_exists_in_the_package(self):
        src = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "pilot_p1").glob("*.py"))
        self.assertNotIn("import google", src)
        self.assertNotIn("genai.Client", src)


if __name__ == "__main__":
    unittest.main()
