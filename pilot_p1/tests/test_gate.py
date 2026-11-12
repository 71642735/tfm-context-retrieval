"""Filtro comun G (fase 3B.1): solo repositorios sinteticos temporales y, en lectura, repos/ reales."""
import inspect
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pilot_p1 import applier as A
from pilot_p1 import gate as G
from pilot_p1.normalizer import normalize_patch
from pilot_p1.tests.helpers import ENV, git_apply_result, make_repo, tree_digest

ROOT = G.PROJECT_ROOT
OK = b"--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 3\n z = 4\n"
FILES = {"pkg/a.py": b"x = 1\ny = 2\nz = 4\n", "pkg/b.py": b"b = 1\n", "top": b"i am a file\n",
         "crlf.txt": b"one\r\ntwo\r\nthree\r\n"}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="p1gatetest_")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.commit = make_repo(self.repo, FILES)
        self.src = A.GitSource(self.repo, self.commit)
        self.before = tree_digest(self.repo)

    def tearDown(self):
        self.assertEqual(tree_digest(self.repo), self.before, "el repositorio sintetico fue modificado")


class Verdicts(Base):
    def test_valid_patch_is_applicable_and_everything_is_recorded(self):
        r = G.gate_check(OK, self.src)
        self.assertEqual((r.status, r.category, r.paths, len(r.attempts)), (G.APPLICABLE, "ok", ["pkg/a.py"], 1))
        a = r.attempts[0]
        self.assertEqual((a.command[:4], a.returncode, a.status), (["git", "apply", "--check", "-p1"], 0, G.APPLICABLE))
        self.assertTrue(r.git_version.startswith("git version"))
        self.assertEqual(len(r.patch_sha256), 64)

    def test_wrong_context_and_corrupt_and_empty_are_not_applicable_without_retry(self):
        cases = {"contexto": OK.replace(b"y = 2", b"y = 9"), "corrupto": OK[:-9], "vacio": b"", "basura": b"hola\n"}
        for name, patch in cases.items():
            with self.subTest(name), mock.patch.object(G, "_run_git", wraps=G._run_git) as run:
                r = G.gate_check(patch, self.src)
                self.assertEqual((r.status, r.category, len(r.attempts)), (G.NOT_APPLICABLE, "model_output_error", 1), r.reason)
                self.assertEqual(sum(1 for c in run.call_args_list if "--check" in c.args[0]), 1)

    def test_patch_without_prefixes_is_rejected_by_p1_but_applicable_once_normalized(self):
        bare = OK.replace(b"a/pkg", b"pkg").replace(b"b/pkg", b"pkg")
        self.assertEqual(G.gate_check(bare, self.src).status, G.NOT_APPLICABLE)
        n = normalize_patch(bare.decode())
        self.assertTrue(n.changed)
        self.assertEqual(G.gate_check(n.patch.encode(), self.src).status, G.APPLICABLE)

    def test_new_file_creation(self):
        new = b"--- /dev/null\n+++ b/pkg/new.py\n@@ -0,0 +1,2 @@\n+a\n+b\n"
        self.assertEqual(G.gate_check(new, self.src).status, G.APPLICABLE)
        existing = new.replace(b"pkg/new.py", b"pkg/b.py")
        r = G.gate_check(existing, self.src)
        self.assertEqual(r.status, G.NOT_APPLICABLE)
        self.assertIn("already exists", r.reason)

    def test_missing_target_and_ancestor_conflicts(self):
        self.assertEqual(G.gate_check(OK.replace(b"pkg/a.py", b"pkg/missing.py"), self.src).status, G.NOT_APPLICABLE)
        # 'top' es un fichero: `git apply --check` NO detecta este conflicto (G mide exactamente esa comprobacion); el aplicador
        # de E1 lo rechaza antes (unsafe_path) y el veredicto de G coincide con el de un arbol completo (ver mas abajo)
        clash = b"--- /dev/null\n+++ b/top/child.py\n@@ -0,0 +1 @@\n+x\n"
        self.assertEqual(G.gate_check(clash, self.src).status, G.APPLICABLE)

    def test_rename_is_handled(self):
        ren = (b"diff --git a/pkg/b.py b/pkg/c.py\nsimilarity index 100%\nrename from pkg/b.py\nrename to pkg/c.py\n")
        r = G.gate_check(ren, self.src)
        self.assertEqual((r.status, sorted(r.paths)), (G.APPLICABLE, ["pkg/b.py", "pkg/c.py"]))

    def test_crlf_native_file_is_judged_with_the_same_strictness_for_every_producer(self):
        e1 = A.apply_text("FILE: crlf.txt\n<<<<<<< SEARCH\ntwo\n=======\n2\n>>>>>>> REPLACE\n", self.src)
        self.assertTrue(e1.ok)
        self.assertIn(b"\r\n", e1.diff_bytes)
        self.assertEqual(G.gate_check(e1.diff_bytes, self.src).status, G.APPLICABLE)       # CRLF nativo: el aplicador lo respeta
        lf = b"--- a/crlf.txt\n+++ b/crlf.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+2\n three\n"
        self.assertEqual(G.gate_check(lf, self.src).status, G.NOT_APPLICABLE)               # sin correcciones adicionales

    def test_patch_bytes_are_passed_unmodified(self):
        seen = {}

        def spy(args, cwd, timeout):
            if "--check" in args:
                seen["bytes"] = Path(args[-1]).read_bytes()
            return G._run_git.__wrapped__(args, cwd, timeout) if hasattr(G._run_git, "__wrapped__") else real(args, cwd, timeout)

        real = G._run_git
        patch = OK.replace(b"\n", b"\r\n")
        with mock.patch.object(G, "_run_git", side_effect=spy):
            G.gate_check(patch, self.src)
        self.assertEqual(seen["bytes"], patch)


class SameTreatment(Base):
    def test_gate_has_no_notion_of_arm(self):
        self.assertNotIn("arm", inspect.signature(G.gate_check).parameters)
        src = inspect.getsource(G)
        for word in ("O1n", "E1", "arm"):
            self.assertNotIn(f'"{word}"', src)

    def test_identical_bytes_from_either_arm_get_identical_results(self):
        a, b = G.gate_check(OK, self.src), G.gate_check(bytes(OK), self.src)
        self.assertEqual(a.comparable(), b.comparable())
        bad = OK.replace(b"y = 2", b"y = 9")
        self.assertEqual(G.gate_check(bad, self.src).comparable(), G.gate_check(bytes(bad), self.src).comparable())

    def test_e1_diff_and_normalized_o1_patch_for_the_same_edit_are_both_applicable_and_equivalent(self):
        e1 = A.apply_text("FILE: pkg/a.py\n<<<<<<< SEARCH\ny = 2\n=======\ny = 3\n>>>>>>> REPLACE\n", self.src)
        o1_raw = b"--- pkg/a.py\n+++ pkg/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 3\n z = 4\n"
        o1n = normalize_patch(o1_raw.decode()).patch.encode()
        self.assertEqual((G.gate_check(e1.diff_bytes, self.src).status, G.gate_check(o1n, self.src).status),
                         (G.APPLICABLE, G.APPLICABLE))
        rc1, _, out1 = git_apply_result(FILES, e1.diff_bytes, ["pkg/a.py"])
        rc2, _, out2 = git_apply_result(FILES, o1n, ["pkg/a.py"])
        self.assertEqual((rc1, rc2, out1), (0, 0, out2))


class Infrastructure(Base):
    def test_source_failures_are_retried_up_to_three_times_and_recovered(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] <= 2:
                raise A.SourceError("git no responde")
            return self.src

        r = G.gate_check(OK, flaky)
        self.assertEqual((r.status, [a.status for a in r.attempts]), (G.APPLICABLE, [G.ENV_ERROR, G.ENV_ERROR, G.APPLICABLE]))

    def test_persistent_failures_stop_at_three_attempts_and_are_infrastructure(self):
        def broken():
            raise A.SourceError("disco")

        r = G.gate_check(OK, broken)
        self.assertEqual((r.status, r.category, len(r.attempts)), (G.ENV_ERROR, "infrastructure_not_evaluable", 3))
        self.assertEqual(len(G.gate_check(OK, broken, max_attempts=1).attempts), 1)

    def test_timeouts_missing_git_and_unknown_exit_codes_are_infrastructure(self):
        for name, effect in (("timeout", subprocess.TimeoutExpired("git", 1)), ("sin git", FileNotFoundError("git"))):
            with self.subTest(name), mock.patch.object(G, "_run_git", side_effect=effect):
                r = G.gate_check(OK, self.src)
                self.assertEqual((r.status, len(r.attempts)), (G.ENV_ERROR, 3))
        fake = subprocess.CompletedProcess([], 128, b"", b"fatal: unable to create temporary file")
        with mock.patch.object(G, "_run_git", return_value=fake):
            self.assertEqual(G.gate_check(OK, self.src).status, G.ENV_ERROR)
        fake = subprocess.CompletedProcess([], 128, b"", b"error: No valid patches in input")
        with mock.patch.object(G, "_run_git", return_value=fake):
            self.assertEqual(G.gate_check(OK, self.src).status, G.NOT_APPLICABLE)

    def test_environment_is_isolated_from_git_variables_and_global_config(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.repo / ".git"), "GIT_WORK_TREE": str(self.repo)}):
            env = G._clean_env()
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GIT_WORK_TREE", env)
        self.assertEqual((env["GIT_CONFIG_GLOBAL"], env["GIT_CONFIG_NOSYSTEM"]), (os.devnull, "1"))

    def test_unsafe_workdirs_are_refused(self):
        with self.assertRaises(G.GateWorkdirError):
            G.assert_safe_workdir(ROOT / "src")
        with self.assertRaises(G.GateWorkdirError):
            G.assert_safe_workdir(self.repo / "pkg")
        G.assert_safe_workdir(Path(self._tmp.name) / "fuera")

    def test_unsafe_paths_in_the_patch_never_write_outside_the_temporary_tree(self):
        evil = b"--- /dev/null\n+++ b/../evil.py\n@@ -0,0 +1 @@\n+x\n"
        r = G.gate_check(evil, self.src)
        self.assertEqual(r.status, G.NOT_APPLICABLE)
        self.assertFalse((Path(tempfile.gettempdir()) / "evil.py").exists())
        self.assertFalse((Path(self._tmp.name) / "evil.py").exists())


class PartialTreeEquivalence(Base):
    """Comparar con un arbol COMPLETO (git archive extraido en un temporal) para justificar el arbol parcial."""

    def full_tree_status(self, patch: bytes) -> str:
        with tempfile.TemporaryDirectory(prefix="p1full_") as d:
            tar = subprocess.run(["git", "-C", str(self.repo), "archive", "--format=tar", self.commit], capture_output=True,
                                 env=ENV).stdout
            tpath = Path(d) / "t.tar"
            tpath.write_bytes(tar)
            tree = Path(d) / "tree"
            tree.mkdir()
            with tarfile.open(tpath) as tf:
                tf.extractall(tree)
            pf = Path(d) / "p.patch"
            pf.write_bytes(patch)
            rc = subprocess.run(["git", "apply", "--check", "-p1", str(pf)], cwd=tree, capture_output=True, env=ENV).returncode
            return G.APPLICABLE if rc == 0 else G.NOT_APPLICABLE

    def test_same_verdict_as_a_full_tree(self):
        patches = {
            "valido": OK, "contexto": OK.replace(b"y = 2", b"y = 9"), "inexistente": OK.replace(b"pkg/a.py", b"pkg/zz.py"),
            "nuevo": b"--- /dev/null\n+++ b/pkg/n.py\n@@ -0,0 +1 @@\n+x\n",
            "nuevo_existente": b"--- /dev/null\n+++ b/pkg/b.py\n@@ -0,0 +1 @@\n+x\n",
            "antecesor_fichero": b"--- /dev/null\n+++ b/top/c.py\n@@ -0,0 +1 @@\n+x\n",
            "sin_prefijo": OK.replace(b"a/pkg", b"pkg").replace(b"b/pkg", b"pkg"), "vacio": b"",
        }
        for name, patch in patches.items():
            with self.subTest(name):
                self.assertEqual(G.gate_check(patch, self.src).status, self.full_tree_status(patch))


@unittest.skipUnless((ROOT / "repos").is_dir() and (ROOT / "logs" / "downstream").is_dir(), "datos originales no disponibles")
class OriginalRepositoriesAreOnlyRead(unittest.TestCase):
    def test_gate_on_real_tasks_never_touches_the_working_repositories(self):
        from pilot_p1 import orchestrator as O
        cases = [("psf__requests-5414", "hybrid"), ("pytest-dev__pytest-5809", "bm25")]
        repos = {}
        for t, _ in cases:
            info = O.default_task_info(t)
            repos[t] = ROOT / "repos" / info["repo"].replace("/", "__")
        before = {t: (tree_digest(r / ".git"), subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True,
                                                             text=True).stdout) for t, r in repos.items()}
        seen = []
        real = G._run_git

        def spy(args, cwd, timeout):
            seen.append((list(args), str(cwd)))
            return real(args, cwd, timeout)

        results = {}
        with mock.patch.object(G, "_run_git", side_effect=spy):
            for t, m in cases:
                # los originales se guardaron con CRLF por la traduccion de write_text en Windows; P1 guarda los bytes sin
                # traduccion, asi que aqui se emula con LF (con CRLF, G -estricto- los rechaza igual que el filtro original)
                raw = (ROOT / "logs" / "downstream" / t / m / "patch.diff").read_bytes().decode("utf-8").replace("\r\n", "\n")
                src = O.default_source_factory(t)
                results[(t, m)] = (G.gate_check(raw.encode("utf-8"), src).status,
                                   G.gate_check(normalize_patch(raw).patch.encode("utf-8"), src).status)
        self.assertEqual(results[("psf__requests-5414", "hybrid")], (G.NOT_APPLICABLE, G.APPLICABLE))   # N lo recupera
        crlf = (ROOT / "logs" / "downstream" / "psf__requests-5414" / "hybrid" / "patch.diff").read_bytes()
        self.assertIn(b"\r\n", crlf)                                         # tal como se guardo en Windows
        with mock.patch.object(G, "_run_git", side_effect=spy):
            n = normalize_patch(crlf.decode("utf-8")).patch.encode("utf-8")
            self.assertEqual(G.gate_check(n, O.default_source_factory("psf__requests-5414")).status, G.NOT_APPLICABLE)
        self.assertEqual(results[("pytest-dev__pytest-5809", "bm25")][0], G.APPLICABLE)                 # ya aplicable (prefijos a/ b/)
        self.assertTrue(seen)
        for args, cwd in seen:
            self.assertNotIn("repos", Path(cwd).parts)
            self.assertFalse(any(str(ROOT / "repos") in a for a in args), args)
            self.assertEqual(args[:2], ["git", "apply"] if "apply" in args[:2] else args[:2])
        self.assertTrue(all(c[0][1] in ("apply", "--version") for c in seen))
        after = {t: (tree_digest(r / ".git"), subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True,
                                                            text=True).stdout) for t, r in repos.items()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
