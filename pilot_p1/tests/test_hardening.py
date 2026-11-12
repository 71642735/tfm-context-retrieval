"""Pruebas de cierre de la fase 1: workdir seguro, errores de git, espacios, timeouts, fixtures, creacion."""
import hashlib
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pilot_p1 import applier as A
from pilot_p1.applier import DirSource, GitSource, PROJECT_ROOT, SourceError, WorkdirError, apply_text, check_keep_dir
from pilot_p1.edit_format import EditFormatError, parse_edits
from pilot_p1.tests.helpers import ENV, git, make_repo, tree_digest
from pilot_p1.tests.test_applier import Base, edit

S, M, R = "<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"
FIXDIR = Path(__file__).parent / "fixtures"


class KeepCopiesDir(Base):
    F = {"m.py": b"a = 1\nb = 2\n"}

    def src(self):
        return self.repo(self.F)

    def test_copies_go_to_a_new_subdirectory_and_nothing_existing_is_overwritten(self):
        keep = Path(self._tmp.name) / "keep"
        keep.mkdir()
        (keep / "m.py").write_bytes(b"SENTINEL")
        (keep / "otro.txt").write_bytes(b"x")
        before = tree_digest(keep)
        r1 = apply_text(edit("m.py", ["a = 1"], ["a = 9"]), self.src(), keep_copies_in=keep)
        r2 = apply_text(edit("m.py", ["a = 1"], ["a = 9"]), self.src(), keep_copies_in=keep)
        self.assertTrue(r1.ok and r2.ok)
        self.assertNotEqual(r1.workdir, r2.workdir)
        for r in (r1, r2):
            self.assertEqual(Path(r.workdir).parent, keep.resolve())
            self.assertEqual((Path(r.workdir) / "m.py").read_bytes(), r.files["m.py"])
        self.assertEqual((keep / "m.py").read_bytes(), b"SENTINEL")
        self.assertEqual((keep / "otro.txt").read_bytes(), b"x")
        self.assertEqual(tree_digest(self.root), self.before)

    def test_default_leaves_nothing_behind(self):
        r = apply_text(edit("m.py", ["a = 1"], ["a = 9"]), self.src())
        self.assertIsNone(r.workdir)

    def _reject(self, path, source=None):
        with self.assertRaises(WorkdirError, msg=str(path)):
            check_keep_dir(path, source)

    def test_project_zones_are_rejected(self):
        for sub in ["", "src", "repos", "results", "logs", "diagnostics", "pilot_p1", "pilot_p1/tests"]:
            with self.subTest(sub=sub):
                d = PROJECT_ROOT / sub if sub else PROJECT_ROOT
                if d.is_dir():
                    self._reject(d)

    def test_a_real_repository_under_repos_is_rejected_without_touching_it(self):
        repos = PROJECT_ROOT / "repos"
        first = next((p for p in sorted(repos.iterdir()) if (p / ".git").exists()), None) if repos.is_dir() else None
        if first is None:
            self.skipTest("no hay repos/")
        before = sorted(os.listdir(first))
        src = self.src()
        for d in (first, first / ".git"):
            with self.assertRaises(WorkdirError):
                apply_text(edit("m.py", ["a = 1"], ["a = 9"]), src, keep_copies_in=d)
        self.assertEqual(sorted(os.listdir(first)), before)

    def test_source_repo_and_its_subdirs_are_rejected(self):
        src = self.src()
        (self.root / "sub").mkdir()
        for d in (self.root, self.root / ".git", self.root / "sub"):
            with self.subTest(d=d.name):
                self._reject(d, src)

    def test_any_directory_inside_another_git_tree_is_rejected(self):
        other = Path(self._tmp.name) / "other"
        make_repo(other, {"x": b"1\n"})
        (other / "deep").mkdir()
        self._reject(other)
        self._reject(other / "deep")

    def test_dirsource_root_is_rejected(self):
        d = Path(self._tmp.name) / "plain"
        (d / "inner").mkdir(parents=True)
        (d / "m.py").write_bytes(b"a = 1\n")
        before = tree_digest(d)
        for k in (d, d / "inner"):
            with self.assertRaises(WorkdirError):
                apply_text(edit("m.py", ["a = 1"], ["a = 2"]), DirSource(d), keep_copies_in=k)
        self.assertEqual(tree_digest(d), before)

    def test_relative_missing_and_file_paths_are_rejected(self):
        f = Path(self._tmp.name) / "f.txt"
        f.write_bytes(b"x")
        for bad in [".", "keep", "..", Path(self._tmp.name) / "nope", f]:
            with self.subTest(bad=str(bad)):
                self._reject(bad)

    def test_symlink_into_the_project_is_rejected(self):
        link = Path(self._tmp.name) / "lnk"
        try:
            os.symlink(PROJECT_ROOT / "src", link, target_is_directory=True)
        except (OSError, NotImplementedError):
            # Windows sin privilegio de symlink: una union de directorios (junction) se resuelve igual
            ok = os.name == "nt" and subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(PROJECT_ROOT / "src")],
                                                    capture_output=True).returncode == 0
            if not ok:
                self.skipTest("no se pueden crear symlinks ni junctions en este entorno")
        self.addCleanup(lambda: os.rmdir(link) if os.path.lexists(link) and not link.is_symlink() else link.unlink(missing_ok=True))
        self._reject(link)

    def test_rejection_happens_before_any_work(self):
        with mock.patch.object(A, "_apply", side_effect=AssertionError("no debe ejecutarse")):
            with self.assertRaises(WorkdirError):
                apply_text(edit("m.py", ["a"], ["b"]), self.src(), keep_copies_in=PROJECT_ROOT / "src")
        before = {p: (PROJECT_ROOT / p).stat().st_mtime_ns for p in ("src", "repos", "results")
                  if (PROJECT_ROOT / p).exists()}
        self.assertTrue(before)


class GitErrors(Base):
    F = {"m.py": b"a = 1\n", "d/f.py": b"x\n"}

    def test_missing_file_is_a_model_fault(self):
        src = self.repo(self.F)
        self.assertIsNone(src.entry("nope.py"))
        self.assertIsNone(src.entry("m.py/child.py"))      # bajo un fichero: tampoco existe
        r = apply_text(edit("nope.py", ["a"], ["b"]), src)
        self.assertEqual(r.status, A.FILE_NOT_FOUND)
        self.assertTrue(r.model_fault)

    def test_real_git_failure_is_not_reported_as_missing_file(self):
        src = self.repo(self.F)
        tree = git(self.root, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
        obj = self.root / ".git" / "objects" / tree[:2] / tree[2:]
        os.chmod(obj, stat.S_IWRITE)
        obj.unlink()                                           # repositorio corrupto (solo el temporal)
        with self.assertRaises(SourceError):
            src.entry("m.py")
        r = apply_text(edit("m.py", ["a = 1"], ["a = 2"]), src)
        self.assertEqual(r.status, A.ENV_ERROR)
        self.assertFalse(r.model_fault)
        self.assertEqual((r.diff, r.files), ("", {}))
        self.assertNotEqual(r.status, A.FILE_NOT_FOUND)

    def test_blob_read_failure_is_environment_error(self):
        src = self.repo(self.F)
        with mock.patch.object(GitSource, "read", side_effect=SourceError("disco")):
            r = apply_text(edit("m.py", ["a = 1"], ["a = 2"]), src)
        self.assertEqual((r.status, r.model_fault), (A.ENV_ERROR, False))

    def test_timeout_is_environment_error(self):
        src = self.repo(self.F)
        with mock.patch.object(A.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 1)):
            r = apply_text(edit("m.py", ["a = 1"], ["a = 2"]), src)
        self.assertEqual((r.status, r.model_fault), (A.ENV_ERROR, False))
        self.assertIn("limite", r.detail)

    def test_real_tiny_timeout(self):
        src = self.repo(self.F)
        src.timeout = 1e-6
        r = apply_text(edit("m.py", ["a = 1"], ["a = 2"]), src)
        self.assertEqual(r.status, A.ENV_ERROR)

    def test_timeout_in_constructor(self):
        self.repo(self.F)
        with self.assertRaises(SourceError):
            GitSource(self.root, "a" * 40, timeout=1e-6)

    def test_git_not_installed(self):
        src = self.repo(self.F)
        with mock.patch.object(A.subprocess, "run", side_effect=FileNotFoundError("git")):
            r = apply_text(edit("m.py", ["a = 1"], ["a = 2"]), src)
        self.assertEqual((r.status, r.model_fault), (A.ENV_ERROR, False))

    def test_default_timeout_is_set_and_reasonable(self):
        src = self.repo(self.F)
        self.assertEqual(src.timeout, A.GIT_TIMEOUT_S)
        self.assertTrue(10 <= A.GIT_TIMEOUT_S <= 300)

    def test_model_fault_flag(self):
        self.assertFalse(A.ApplyResult(A.READY).model_fault)
        self.assertFalse(A.ApplyResult(A.ENV_ERROR).model_fault)
        for st in (A.PARSE_ERROR, A.SEARCH_NOT_FOUND, A.AMBIGUOUS, A.UNSAFE_PATH, A.FILE_NOT_FOUND):
            self.assertTrue(A.ApplyResult(st).model_fault)

    def test_list_dir(self):
        src = self.repo(self.F)
        self.assertEqual(sorted(src.list_dir("")), ["d", "m.py"])
        self.assertEqual(src.list_dir("d"), ["f.py"])
        self.assertEqual(src.list_dir("nope"), [])


class WhitespaceNormalisation(Base):
    def test_only_space_and_tab_are_ignored_at_line_end(self):
        for trailing, ok in [("", True), (" ", True), ("\t", True), (" \t ", True),
                             ("\x0c", False), ("\xa0", False), (" ", False), ("\x1c", False), ("\x0b", False)]:
            with self.subTest(trailing=repr(trailing)):
                files = {"t.py": ("x = 1" + trailing + "\ny = 2\n").encode()}
                src = self.repo(files) if not hasattr(self, "_n") else self.repo(files)
                r = apply_text(edit("t.py", ["x = 1"], ["x = 5"]), src)
                self.assertEqual(r.status, A.READY if ok else A.SEARCH_NOT_FOUND, r.detail)
                self.setUp()   # repositorio nuevo para el siguiente caso

    def test_trailing_special_whitespace_in_search_is_significant(self):
        src = self.repo({"t.py": b"x = 1\n"})
        r = apply_text(edit("t.py", ["x = 1\x0c"], ["x = 5"]), src)
        self.assertEqual(r.status, A.SEARCH_NOT_FOUND)

    def test_unicode_space_is_not_indentation(self):
        src = self.repo({"t.py": " x = 1\n".encode()})
        r = apply_text(edit("t.py", ["x = 1"], ["x = 5"]), src)
        self.assertEqual(r.status, A.SEARCH_NOT_FOUND)

    def test_line_with_only_formfeed_is_not_blank(self):
        src = self.repo({"t.py": b"a\n\x0c\nb\n"})
        r = apply_text(edit("t.py", ["a", "", "b"], ["z"]), src)
        self.assertEqual(r.status, A.SEARCH_NOT_FOUND)
        self.setUp()
        src = self.repo({"t.py": b"a\n\x0c\nb\n"})
        self.assertEqual(apply_text(edit("t.py", ["\x0c"], ["z"]), src).status, A.READY)

    def test_parser_markers_ignore_only_space_and_tab(self):
        self.assertEqual(len(parse_edits(f"FILE: f\n{S} \t\na\n{M}\t \nb\n{R} \t\n")), 1)
        with self.assertRaises(EditFormatError):
            parse_edits(f"FILE: f\n{S}\x0c\na\n{M}\nb\n{R}\n")          # marcador con FF: texto fuera de bloque
        with self.assertRaises(EditFormatError):
            parse_edits(f"FILE: f\n{S}\na\n{M}\nb\n{R}\x0c\n")          # no cierra el bloque
        with self.assertRaises(EditFormatError):
            parse_edits(f"FILE: f\n{S}\na\n{M}\x0c\nb\n{R}\n")

    def test_parser_rejects_nul(self):
        with self.assertRaises(EditFormatError):
            parse_edits(f"FILE: f\n{S}\na\0\n{M}\nb\n{R}\n")


class FixtureReproducibility(unittest.TestCase):
    SHA = {
        "basic/edits.txt": "a24aecf8b777c0e10d2f36e2fc4056faa766fcd4fc04c5d46712c70122194242",
        "basic/expected.diff": "f5522200078681f8c58cbda1244b24f8f16688838edec21f77272dd939914e7f",
        "basic/tree/pkg/mod.py": "2fb1c9dd00e6bd4525959f4b74c68eef63a1c459953c40ed9e5cecbe9a6fa239",
    }

    def test_fixture_bytes_are_the_expected_ones(self):
        for rel, sha in self.SHA.items():
            with self.subTest(rel=rel):
                data = (FIXDIR / rel).read_bytes()
                self.assertNotIn(b"\r", data)
                self.assertEqual(hashlib.sha256(data).hexdigest(), sha)

    def test_fixtures_are_marked_binary_for_git(self):
        self.assertTrue((FIXDIR / ".gitattributes").is_file())
        out = subprocess.run(["git", "-C", str(PROJECT_ROOT), "check-attr", "text", "eol", "--",
                              *[f"pilot_p1/tests/fixtures/{r}" for r in self.SHA]],
                             capture_output=True, text=True).stdout
        self.assertEqual(out.count("text: unset"), 3, out)

    def _round_trip(self, with_attributes):
        with tempfile.TemporaryDirectory(prefix="p1fix_") as d:
            repo = Path(d) / "r"
            repo.mkdir()
            cfg = ["-c", "core.autocrlf=true", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
            run = lambda *a: subprocess.run(["git", *cfg, *a], cwd=repo, capture_output=True, env=ENV, check=True)
            run("init", "-q")
            for rel, _ in self.SHA.items():
                dst = repo / "f" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes((FIXDIR / rel).read_bytes())
            if with_attributes:
                (repo / "f" / ".gitattributes").write_bytes((FIXDIR / ".gitattributes").read_bytes())
            run("add", "-A")
            run("commit", "-q", "-m", "x")
            for rel in self.SHA:
                (repo / "f" / rel).unlink()
            run("checkout", "--", ".")                          # el 'checkout' ocurre en el repo temporal
            return {rel: (repo / "f" / rel).read_bytes() for rel in self.SHA}

    def test_autocrlf_true_does_not_alter_protected_fixtures(self):
        got = self._round_trip(True)
        for rel, sha in self.SHA.items():
            self.assertEqual(hashlib.sha256(got[rel]).hexdigest(), sha, rel)

    def test_control_without_attributes_would_be_converted(self):
        got = self._round_trip(False)
        self.assertTrue(any(b"\r\n" in v for v in got.values()), "el control no demuestra la conversion")


class FileCreation(Base):
    F = {"d/f.py": b"x = 1\n", "Pkg/Mod.py": b"y = 1\n", "m.py": b"z = 1\n"}

    def test_nested_new_directories(self):
        r = self.run_ok(self.F, edit("n1/n2/n3/new.py", [], ["a = 1"]))
        self.assertEqual(r.files["n1/n2/n3/new.py"], b"a = 1\n")

    def test_new_file_next_to_existing_in_existing_dir(self):
        self.run_ok(self.F, edit("d/g.py", [], ["g = 1"]))

    def test_create_and_edit_different_files(self):
        self.run_ok(self.F, edit("n.py", [], ["n = 1"]) + edit("m.py", ["z = 1"], ["z = 2"]))

    def test_trailing_blank_lines_and_tabs_preserved(self):
        r = self.run_ok(self.F, edit("n.txt", [], ["a\t", "", ""]))
        self.assertEqual(r.files["n.txt"], b"a\t\n\n\n")

    def test_content_that_looks_like_a_diff(self):
        r = self.run_ok(self.F, edit("n.txt", [], ["--- a/x", "+++ b/x", "@@ -1 +1 @@", "-a", "+b", " c", "\\ No newline"]))
        self.assertIn(b"@@ -1 +1 @@", r.files["n.txt"])

    def test_unicode_content(self):
        self.run_ok(self.F, edit("n.txt", [], ["canción", "日本語"]))

    def test_blank_or_whitespace_only_new_file_rejected(self):
        for content in ([""], ["", ""], ["  "], ["\t", " "], []):
            with self.subTest(content=content):
                self.run_bad(self.F, edit("n.txt", [], content), A.INCONSISTENT)
                self.setUp()

    def test_create_over_existing_directory(self):
        self.run_bad(self.F, edit("d", [], ["x"]), A.UNSUPPORTED_FILE)

    def test_case_clash_with_existing_file(self):
        r = self.run_bad(self.F, edit("pkg/mod.py", [], ["x"]), A.INCONSISTENT)
        self.assertIn("mayusculas", r.detail)

    def test_case_clash_with_existing_file_same_dir(self):
        self.run_bad(self.F, edit("M.py", [], ["x"]), A.INCONSISTENT)

    def test_case_clash_in_parent_directory(self):
        self.run_bad(self.F, edit("PKG/other.py", [], ["x"]), A.INCONSISTENT)

    def test_two_new_files_differing_only_in_case(self):
        self.run_bad(self.F, edit("n.py", [], ["a"]) + edit("N.py", [], ["b"]), A.INCONSISTENT)

    def test_new_file_and_new_directory_with_same_name(self):
        self.run_bad(self.F, edit("n", [], ["a"]) + edit("n/x.py", [], ["b"]), A.INCONSISTENT)

    def test_new_file_under_existing_file(self):
        self.run_bad(self.F, edit("m.py/x.py", [], ["a"]), A.UNSAFE_PATH)

    def test_reserved_windows_names_and_long_paths(self):
        for p in ["con.py", "CON", "aux/x.py", "d/nul.txt", "com1.txt", "LPT9.log", "a" * 256, "/".join(["ab"] * 400)]:
            with self.subTest(path=p[:30]):
                self.assertIsNotNone(A.path_problem(p))
        for p in ["console.py", "a" * 255, "xcon.py", "d/auxiliary.py", "com10.txt"]:
            with self.subTest(path=p[:30]):
                self.assertIsNone(A.path_problem(p))

    def test_nul_inside_new_file_content_rejected_by_parser(self):
        self.assertEqual(apply_text(edit("n.txt", [], ["a\0b"]), DirSource(FIXDIR / "basic" / "tree")).status, A.PARSE_ERROR)


if __name__ == "__main__":
    unittest.main()
