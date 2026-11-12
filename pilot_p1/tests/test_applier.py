import tempfile
import unittest
from pathlib import Path

from pilot_p1 import applier as A
from pilot_p1.applier import DirSource, GitSource, SourceError, apply_text, path_problem
from pilot_p1.tests.helpers import git_apply_result, make_repo, tree_digest

S, M, R = "<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"
FIX = Path(__file__).parent / "fixtures" / "basic"


def edit(path, search, replace):
    return "\n".join([f"FILE: {path}", S, *search, M, *replace, R]) + "\n"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="p1repo_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"

    def repo(self, files, extra=()):
        commit = make_repo(self.root, files, extra)
        self.before = tree_digest(self.root)
        return GitSource(self.root, commit)

    def run_ok(self, files, text, **kw):
        """Aplica, exige patch_ready y que el diff reproduzca EXACTAMENTE lo que hace git apply real."""
        src = self.repo(files)
        r = apply_text(text, src, **kw)
        self.assertEqual(r.status, A.READY, r.detail)
        rc, err, got = git_apply_result(files, r.diff_bytes, list(r.files))
        self.assertEqual(rc, 0, err)
        for rel, data in r.files.items():
            self.assertEqual(got[rel], data, rel)
        self.assertEqual(tree_digest(self.root), self.before, "el repositorio fue modificado")
        return r

    def run_bad(self, files, text, status, extra=()):
        src = self.repo(files, extra)
        r = apply_text(text, src)
        self.assertEqual(r.status, status, r.detail)
        self.assertEqual((r.diff, r.files), ("", {}), "un fallo no debe producir diff")
        self.assertEqual(tree_digest(self.root), self.before, "el repositorio fue modificado")
        return r


class Accepted(Base):
    F = {"m.py": b"import os\n\n\ndef f(x):\n    return x + 1\n\n\ndef g():\n    pass\n"}

    def test_simple_replace(self):
        r = self.run_ok(self.F, edit("m.py", ["    return x + 1"], ["    return x + 2"]))
        self.assertIn(b"x + 2", r.files["m.py"])
        self.assertEqual(r.outcomes[0].match_level, 1)
        self.assertEqual(r.outcomes[0].start_line, 5)

    def test_multiline_block(self):
        self.run_ok(self.F, edit("m.py", ["def f(x):", "    return x + 1"], ["def f(x, y=0):", "    return x + y"]))

    def test_two_edits_same_file(self):
        t = edit("m.py", ["    return x + 1"], ["    return x"]) + edit("m.py", ["    pass"], ["    return None"])
        self.run_ok(self.F, t)

    def test_adjacent_edits_do_not_overlap(self):
        t = edit("m.py", ["def f(x):"], ["def f(x, y):"]) + edit("m.py", ["    return x + 1"], ["    return y"])
        self.run_ok(self.F, t)

    def test_two_files(self):
        files = {"a.py": b"a = 1\n", "d/b.py": b"b = 1\n"}
        r = self.run_ok(files, edit("d/b.py", ["b = 1"], ["b = 2"]) + edit("a.py", ["a = 1"], ["a = 2"]))
        self.assertLess(r.diff.index("a/a.py"), r.diff.index("a/d/b.py"), "orden por ruta")

    def test_pure_deletion(self):
        self.run_ok(self.F, edit("m.py", ["", "", "def g():", "    pass"], []))

    def test_pure_insertion_by_extending_block(self):
        self.run_ok(self.F, edit("m.py", ["import os"], ["import os", "import sys"]))

    def test_first_and_last_line(self):
        self.run_ok(self.F, edit("m.py", ["import os"], ["import re"]) + edit("m.py", ["    pass"], ["    ..."]))

    def test_new_file(self):
        r = self.run_ok(self.F, edit("pkg/new.py", [], ["x = 1", "y = 2"]))
        self.assertEqual(r.files["pkg/new.py"], b"x = 1\ny = 2\n")
        self.assertIn("new file mode 100644", r.diff)

    def test_no_final_newline_edit_last_line(self):
        r = self.run_ok({"n.txt": b"a\nb\nc"}, edit("n.txt", ["c"], ["d"]))
        self.assertEqual(r.files["n.txt"], b"a\nb\nd")
        self.assertIn("\\ No newline at end of file", r.diff)

    def test_no_final_newline_edit_middle_keeps_it(self):
        r = self.run_ok({"n.txt": b"a\nb\nc"}, edit("n.txt", ["a"], ["z"]))
        self.assertEqual(r.files["n.txt"], b"z\nb\nc")

    def test_no_final_newline_delete_last_line(self):
        r = self.run_ok({"n.txt": b"a\nb\nc"}, edit("n.txt", ["c"], []))
        self.assertEqual(r.files["n.txt"], b"a\nb\n")

    def test_crlf_file_preserved_with_lf_model_text(self):
        r = self.run_ok({"w.py": b"a = 1\r\nb = 2\r\nc = 3\r\n"}, edit("w.py", ["b = 2"], ["b = 20", "b2 = 21"]))
        self.assertEqual(r.files["w.py"], b"a = 1\r\nb = 20\r\nb2 = 21\r\nc = 3\r\n")

    def test_crlf_in_model_text_on_lf_file(self):
        t = edit("m.py", ["    return x + 1"], ["    return x + 2"]).replace("\n", "\r\n")
        r = self.run_ok(self.F, t)
        self.assertNotIn(b"\r", r.files["m.py"])

    def test_crlf_file_without_final_newline(self):
        r = self.run_ok({"w.py": b"a\r\nb"}, edit("w.py", ["b"], ["c"]))
        self.assertEqual(r.files["w.py"], b"a\r\nc")

    def test_trailing_whitespace_in_file_ignored_for_match(self):
        r = self.run_ok({"t.py": b"x = 1   \ny = 2\n"}, edit("t.py", ["x = 1"], ["x = 5"]))
        self.assertEqual(r.files["t.py"], b"x = 5\ny = 2\n")

    def test_bom_preserved(self):
        r = self.run_ok({"b.py": b"\xef\xbb\xbfa = 1\nb = 2\n"}, edit("b.py", ["a = 1"], ["a = 9"]))
        self.assertTrue(r.files["b.py"].startswith(b"\xef\xbb\xbf"))

    def test_level2_indent_added(self):
        files = {"i.py": b"class A:\n    def f(self):\n        return 1\n"}
        r = self.run_ok(files, edit("i.py", ["def f(self):", "    return 1"], ["def f(self):", "    return 2"]))
        self.assertEqual(r.outcomes[0].match_level, 2)
        self.assertEqual(r.files["i.py"], b"class A:\n    def f(self):\n        return 2\n")

    def test_level2_indent_removed_tabs(self):
        files = {"i.py": b"def f():\n\treturn 1\n"}
        r = self.run_ok(files, edit("i.py", ["        def f():", "        \treturn 1"], ["        def f():", "        \treturn 3"]))
        self.assertEqual(r.files["i.py"], b"def f():\n\treturn 3\n")

    def test_tabs_and_unicode(self):
        r = self.run_ok({"u.py": "s = 'canción'\n\tx = 1\n".encode()}, edit("u.py", ["s = 'canción'"], ["s = 'señal'"]))
        self.assertIn("señal".encode(), r.files["u.py"])

    def test_empty_file_gets_no_match_but_other_file_ok(self):
        self.run_ok({"e.py": b"", "o.py": b"k = 1\n"}, edit("o.py", ["k = 1"], ["k = 2"]))

    def test_noop_block_next_to_real_one(self):
        t = edit("m.py", ["import os"], ["import os"]) + edit("m.py", ["    pass"], ["    ..."])
        r = self.run_ok(self.F, t)
        self.assertEqual(r.diff.count("@@"), 2)

    def test_deterministic_and_matches_golden_fixture(self):
        text = (FIX / "edits.txt").read_text(encoding="utf-8")
        outs = [apply_text(text, DirSource(FIX / "tree")) for _ in range(3)]
        self.assertTrue(all(o.ok for o in outs))
        self.assertEqual(len({o.diff_sha256 for o in outs}), 1)
        self.assertEqual(outs[0].diff_bytes, (FIX / "expected.diff").read_bytes())

    def test_same_diff_from_git_and_dir_source(self):
        text = edit("m.py", ["    return x + 1"], ["    return x + 2"])
        src = self.repo(self.F)
        d = Path(self._tmp.name) / "plain"
        d.mkdir()
        (d / "m.py").write_bytes(self.F["m.py"])
        self.assertEqual(apply_text(text, src).diff, apply_text(text, DirSource(d)).diff)

    def test_keep_copies_option_keeps_copies_in_new_subdir(self):
        wd = Path(self._tmp.name) / "wd"
        wd.mkdir()
        r = self.run_ok(self.F, edit("m.py", ["    pass"], ["    ..."]), keep_copies_in=wd)
        self.assertEqual((Path(r.workdir) / "m.py").read_bytes(), r.files["m.py"])


class Rejected(Base):
    F = Accepted.F

    def test_search_not_found(self):
        self.run_bad(self.F, edit("m.py", ["    return x + 99"], ["pass"]), A.SEARCH_NOT_FOUND)

    def test_search_not_found_when_only_blank_line_differs(self):
        self.run_bad(self.F, edit("m.py", ["import os", "", "def f(x):"], ["x"]), A.SEARCH_NOT_FOUND)

    def test_ambiguous_exact(self):
        r = self.run_bad({"d.py": b"x = 1\ny = 2\nx = 1\n"}, edit("d.py", ["x = 1"], ["x = 3"]), A.AMBIGUOUS)
        self.assertIn("2 coincidencias", r.detail)

    def test_ambiguous_loose(self):
        files = {"d.py": b"if a:\n    x = 1\nif b:\n        x = 1\n"}
        self.run_bad(files, edit("d.py", ["  x = 1"], ["x = 3"]), A.AMBIGUOUS)

    def test_exact_match_preferred_over_loose_candidates(self):
        files = {"d.py": b"x = 1\n    x = 1\n"}
        r = self.run_ok(files, edit("d.py", ["x = 1"], ["x = 3"]))
        self.assertEqual((r.outcomes[0].match_level, r.files["d.py"]), (1, b"x = 3\n    x = 1\n"))

    def test_file_not_found(self):
        self.run_bad(self.F, edit("nope.py", ["a"], ["b"]), A.FILE_NOT_FOUND)

    def test_empty_search_on_existing_file(self):
        self.run_bad(self.F, edit("m.py", [], ["x"]), A.INCONSISTENT)

    def test_create_twice(self):
        self.run_bad(self.F, edit("n.py", [], ["a"]) + edit("n.py", [], ["b"]), A.INCONSISTENT)

    def test_create_and_edit_same_new_file(self):
        self.run_bad(self.F, edit("n.py", [], ["a"]) + edit("n.py", ["a"], ["b"]), A.FILE_NOT_FOUND)

    def test_new_empty_file(self):
        self.run_bad(self.F, edit("n.py", [], []), A.INCONSISTENT)

    def test_overlapping_blocks(self):
        t = edit("m.py", ["def f(x):", "    return x + 1"], ["a"]) + edit("m.py", ["    return x + 1", ""], ["b"])
        self.run_bad(self.F, t, A.OVERLAPPING)

    def test_identical_blocks_overlap(self):
        t = edit("m.py", ["    pass"], ["a"]) * 2
        self.run_bad(self.F, t, A.OVERLAPPING)

    def test_blank_search(self):
        self.run_bad(self.F, edit("m.py", ["", ""], ["x"]), A.BLANK_SEARCH)

    def test_all_edits_identity_gives_empty_diff(self):
        self.run_bad(self.F, edit("m.py", ["import os"], ["import os"]), A.EMPTY_DIFF)

    def test_atomic_one_bad_block_rejects_all(self):
        t = edit("m.py", ["import os"], ["import re"]) + edit("m.py", ["inexistente"], ["x"])
        r = self.run_bad(self.F, t, A.SEARCH_NOT_FOUND)
        self.assertEqual([o.status for o in r.outcomes], [A.READY, A.SEARCH_NOT_FOUND])

    def test_level2_reindent_impossible(self):
        files = {"i.py": b"  a = 1\n  b = 2\n"}
        self.run_bad(files, edit("i.py", ["      a = 1", "      b = 2"], ["a = 3"]), A.SEARCH_NOT_FOUND)

    def test_level2_inconsistent_indent_not_matched(self):
        files = {"i.py": b"    a = 1\n b = 2\n"}
        self.run_bad(files, edit("i.py", ["a = 1", "b = 2"], ["c"]), A.SEARCH_NOT_FOUND)

    def test_parse_error_reported(self):
        r = apply_text("hola", DirSource(FIX / "tree"))
        self.assertEqual(r.status, A.PARSE_ERROR)

    def test_binary_file(self):
        self.run_bad({"b.bin": b"a\0b\n"}, edit("b.bin", ["a"], ["c"]), A.UNSUPPORTED_FILE)

    def test_invalid_utf8(self):
        self.run_bad({"l.txt": b"caf\xe9\n"}, edit("l.txt", ["x"], ["c"]), A.UNSUPPORTED_FILE)

    def test_mixed_line_endings(self):
        self.run_bad({"x.txt": b"a\r\nb\nc\r\n"}, edit("x.txt", ["a"], ["z"]), A.UNSUPPORTED_FILE)

    def test_lone_cr(self):
        self.run_bad({"x.txt": b"a\rb\n"}, edit("x.txt", ["a"], ["z"]), A.UNSUPPORTED_FILE)

    def test_symlink_entry(self):
        self.run_bad(self.F, edit("lnk", ["m.py"], ["x"]), A.UNSUPPORTED_FILE, extra=[("120000", "lnk", b"m.py")])

    def test_submodule_entry(self):
        self.run_bad(self.F, edit("sub", ["x"], ["y"]), A.UNSUPPORTED_FILE, extra=[("160000", "sub", b"")])

    def test_directory_target(self):
        self.run_bad({"d/f.py": b"a\n"}, edit("d", ["a"], ["b"]), A.UNSUPPORTED_FILE)

    def test_new_file_under_a_file_parent(self):
        self.run_bad(self.F, edit("m.py/child.py", [], ["x"]), A.UNSAFE_PATH)

    def test_new_file_under_symlink_parent(self):
        self.run_bad(self.F, edit("lnk/new.py", [], ["x"]), A.UNSAFE_PATH, extra=[("120000", "lnk", b"m.py")])


class UnsafePaths(Base):
    BAD = ["/etc/passwd", "../x.py", "a/../../x.py", "a/../b.py", "C:/x.py", "C:x.py", "c:\\x.py", "a\\b.py", ".git/config",
           "a/.git/hooks/x", ".gitmodules", "a//b.py", "./a.py", "a/./b.py", "dir/", "", " a.py", "a.py ", "~/x.py",
           "a\0b.py", "a\nb.py", "file.txt:stream", "dir./x.py"]

    def test_path_problem_table(self):
        for p in self.BAD:
            with self.subTest(path=p):
                self.assertIsNotNone(path_problem(p))

    def test_good_paths(self):
        for p in ["a.py", "pkg/mod.py", ".github/workflows/ci.yml", "a b/c d.py", ".gitignore", "x/.hidden"]:
            with self.subTest(path=p):
                self.assertIsNone(path_problem(p))

    def test_applier_rejects_before_touching_anything(self):
        for p in ["../evil.py", "/abs.py", ".git/config", "C:/x.py"]:
            with self.subTest(path=p):
                self.run_bad({"m.py": b"a\n"}, edit(p, [], ["x"]), A.UNSAFE_PATH)

    def test_no_file_created_outside_temp_dir(self):
        outside = Path(self._tmp.name) / "evil.py"
        self.run_bad({"m.py": b"a\n"}, edit("../evil.py", [], ["x"]), A.UNSAFE_PATH)
        self.assertFalse(outside.exists())


class ReadOnlyGuarantees(Base):
    def test_git_source_only_allows_read_commands(self):
        src = self.repo({"a.py": b"a\n"})
        for cmd in ["checkout", "fetch", "reset", "apply", "config"]:
            with self.assertRaises(SourceError):
                src._run(cmd)

    def test_bad_commit_rejected(self):
        self.repo({"a.py": b"a\n"})
        for c in ["HEAD", "main; rm -rf", "--help", "", "0" * 40]:
            with self.subTest(commit=c), self.assertRaises(SourceError):
                GitSource(self.root, c)

    def test_repo_digest_unchanged_after_many_runs(self):
        src = self.repo({"a.py": b"a = 1\n"})
        for t in [edit("a.py", ["a = 1"], ["a = 2"]), edit("a.py", ["zz"], ["y"]), "basura", edit("../x", [], ["a"])]:
            apply_text(t, src)
        self.assertEqual(tree_digest(self.root), self.before)

    def test_dirsource_directory_unchanged(self):
        d = Path(self._tmp.name) / "plain"
        d.mkdir()
        (d / "a.py").write_bytes(b"a = 1\n")
        before = tree_digest(d)
        apply_text(edit("a.py", ["a = 1"], ["a = 2"]), DirSource(d))
        self.assertEqual(tree_digest(d), before)


if __name__ == "__main__":
    unittest.main()
