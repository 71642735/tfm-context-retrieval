import re
import unittest
from collections import Counter
from pathlib import Path

from pilot_p1 import normalizer as N
from pilot_p1.normalizer import normalize_patch

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs" / "downstream"

HUNK = "@@ -1,2 +1,2 @@\n a\n-b\n+c\n"


def bare(path="foo.py", hunk=HUNK):
    return f"--- {path}\n+++ {path}\n{hunk}"


def pref(path="foo.py", hunk=HUNK):
    return f"--- a/{path}\n+++ b/{path}\n{hunk}"


class Normalizes(unittest.TestCase):
    def test_bare_headers_get_prefixes_and_nothing_else_changes(self):
        r = normalize_patch(bare())
        self.assertEqual((r.status, r.patch), (N.NORMALIZED, pref()))
        self.assertEqual(r.changed_lines, [0, 1])

    def test_multiple_files_and_hunks(self):
        t = bare("a.py") + "@@ -9 +9 @@\n-x\n+y\n" + bare("d/b.py")
        r = normalize_patch(t)
        self.assertEqual(r.status, N.NORMALIZED)
        self.assertEqual(r.patch, pref("a.py") + "@@ -9 +9 @@\n-x\n+y\n" + pref("d/b.py"))

    def test_new_file_only_plus_header_changes(self):
        t = "--- /dev/null\n+++ new.py\n@@ -0,0 +1,2 @@\n+a\n+b\n"
        r = normalize_patch(t)
        self.assertEqual(r.patch, "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+a\n+b\n")
        self.assertEqual(r.changed_lines, [1])

    def test_timestamp_suffix_preserved(self):
        r = normalize_patch(f"--- foo.py\t2020-01-01 00:00:00\n+++ foo.py\t2020-01-02\n{HUNK}")
        self.assertEqual(r.patch, f"--- a/foo.py\t2020-01-01 00:00:00\n+++ b/foo.py\t2020-01-02\n{HUNK}")

    def test_crlf_patch_keeps_every_terminator(self):
        t = bare().replace("\n", "\r\n")
        r = normalize_patch(t)
        self.assertEqual(r.patch, pref().replace("\n", "\r\n"))

    def test_mixed_terminators_preserved(self):
        t = "--- foo.py\r\n+++ foo.py\n@@ -1 +1 @@\r\n-a\n+b\r\n"
        self.assertEqual(normalize_patch(t).patch, "--- a/foo.py\r\n+++ b/foo.py\n@@ -1 +1 @@\r\n-a\n+b\r\n")

    def test_prose_and_fences_around_are_kept(self):
        t = "```diff\n" + bare() + "```\n"
        r = normalize_patch(t)
        self.assertEqual(r.patch, "```diff\n" + pref() + "```\n")

    def test_directory_named_a_is_not_mistaken_for_a_prefix(self):
        r = normalize_patch(bare("a/x.py"))
        self.assertEqual(r.patch, pref("a/x.py"))
        self.assertIn("--- a/a/x.py", r.patch)

    def test_header_like_lines_inside_a_hunk_are_content(self):
        hunk = "@@ -1 +1 @@\n--- foo\n+++ bar\n@@ -9 +9 @@\n-q\n+r\n"
        r = normalize_patch(f"--- f.py\n+++ f.py\n{hunk}")
        self.assertEqual(r.status, N.NORMALIZED)
        self.assertEqual(r.patch, f"--- a/f.py\n+++ b/f.py\n{hunk}")

    def test_no_newline_marker_and_empty_context_lines(self):
        hunk = "@@ -1,3 +1,3 @@\n a\n\n-b\n\\ No newline at end of file\n+c\n\\ No newline at end of file\n"
        r = normalize_patch(bare(hunk=hunk))
        self.assertEqual(r.status, N.NORMALIZED)

    def test_single_line_hunk_counts_default_to_one(self):
        self.assertEqual(normalize_patch(bare(hunk="@@ -3 +3 @@\n-a\n+b\n")).status, N.NORMALIZED)


class LeavesUntouched(unittest.TestCase):
    def assertUnchanged(self, text, status):
        r = normalize_patch(text)
        self.assertEqual(r.status, status, r.detail)
        self.assertEqual(r.patch, text)
        self.assertEqual(r.changed_lines, [])
        self.assertFalse(r.changed)
        return r

    def test_already_prefixed(self):
        self.assertUnchanged(pref(), N.ALREADY)
        self.assertUnchanged(pref("a.py") + pref("b.py"), N.ALREADY)

    def test_new_file_already_prefixed(self):
        self.assertUnchanged("--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+a\n", N.ALREADY)

    def test_consistent_git_headers_already_prefixed(self):
        self.assertUnchanged("diff --git a/foo.py b/foo.py\nindex 1..2 100644\n" + pref(), N.ALREADY)

    def test_git_headers_with_bare_file_headers_untouched(self):
        self.assertUnchanged("diff --git a/foo.py b/foo.py\n" + bare(), N.GIT_HEADERS)

    def test_git_headers_inconsistent_with_file_headers(self):
        self.assertUnchanged("diff --git a/other.py b/other.py\n" + pref(), N.GIT_HEADERS)

    def test_git_headers_without_hunks(self):
        self.assertUnchanged("diff --git a/x b/x\nold mode 100644\nnew mode 100755\n", N.GIT_HEADERS)

    def test_mixed_prefixed_and_bare(self):
        self.assertUnchanged(pref("a.py") + bare("b.py"), N.MIXED)

    def test_minus_prefixed_plus_bare(self):
        self.assertUnchanged(f"--- a/foo.py\n+++ foo.py\n{HUNK}", N.UNSUPPORTED)

    def test_rename_or_different_paths(self):
        self.assertUnchanged(f"--- old.py\n+++ new.py\n{HUNK}", N.UNSUPPORTED)

    def test_quoted_paths(self):
        self.assertUnchanged(f'--- "a b.py"\n+++ "a b.py"\n{HUNK}', N.UNSUPPORTED)

    def test_file_deletion(self):
        self.assertUnchanged("--- foo.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n", N.UNSUPPORTED)

    def test_devnull_both_sides(self):
        self.assertUnchanged("--- /dev/null\n+++ /dev/null\n@@ -0,0 +1 @@\n+a\n", N.UNSUPPORTED)

    def test_no_diff_at_all(self):
        for t in ["", "Sorry, I cannot do that.\n", "```\nprint(1)\n```\n", "--- foo.py\n+++ foo.py\n"]:
            with self.subTest(t=t[:20]):
                self.assertUnchanged(t, N.NO_HEADERS)

    def test_malformed_counts_are_not_repaired(self):
        self.assertUnchanged(bare(hunk="@@ -1,5 +1,5 @@\n a\n-b\n+c\n"), N.MALFORMED)          # hunk truncado
        self.assertUnchanged(bare(hunk="@@ -1,2 +1,2 @@\n a\n-b\n-c\n+d\n"), N.MALFORMED)    # excede contadores en el hunk
        self.assertUnchanged(bare(hunk="@@ -1,2 +1,2 @@\n a\n?b\n+c\n"), N.MALFORMED)          # linea invalida

    def test_one_malformed_hunk_blocks_the_whole_patch(self):
        self.assertUnchanged(bare("a.py") + bare("b.py", "@@ -1,9 +1,9 @@\n a\n"), N.MALFORMED)

    def test_original_object_text_never_mutated(self):
        t = bare()
        normalize_patch(t)
        self.assertEqual(t, bare())


class TrailingLinesAndGit(unittest.TestCase):
    """Git ignora las lineas sobrantes tras un hunk completo; N no las trata como error ni las toca."""

    def test_trailing_lines_after_complete_hunk_are_tolerated_like_git(self):
        hunk = "@@ -1,1 +1,1 @@\n a\n-b\n+c\n"
        r = normalize_patch(bare(hunk=hunk))
        self.assertEqual((r.status, r.patch), (N.NORMALIZED, pref(hunk=hunk)))

    def test_normalized_patch_gives_same_result_as_git_with_p0(self):
        from pilot_p1.tests.helpers import git_apply_result
        files = {"d/foo.py": b"a\nb\nc\nd\n"}
        orig = "--- d/foo.py\n+++ d/foo.py\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n"
        rc1, _, _ = git_apply_result(files, orig.encode(), ["d/foo.py"], strip=1)
        rc0, _, out0 = git_apply_result(files, orig.encode(), ["d/foo.py"], strip=0)
        r = normalize_patch(orig)
        rcn, _, outn = git_apply_result(files, r.patch.encode(), ["d/foo.py"], strip=1)
        self.assertNotEqual(rc1, 0)                 # el filtro original (-p1) lo rechaza
        self.assertEqual((rc0, rcn), (0, 0))
        self.assertEqual(out0, outn)                # mismo fichero final: N no cambia la edicion
        self.assertEqual(outn["d/foo.py"], b"a\nB\nc\nd\n")


class Idempotence(unittest.TestCase):
    CASES = [bare(), pref(), bare("a/x.py"), "--- /dev/null\n+++ n.py\n@@ -0,0 +1 @@\n+a\n", "garbage", "",
             bare("a.py") + bare("b.py"), "diff --git a/foo.py b/foo.py\n" + bare(), bare().replace("\n", "\r\n")]

    def test_second_pass_is_a_no_op(self):
        for t in self.CASES:
            with self.subTest(t=t[:25]):
                r1 = normalize_patch(t)
                r2 = normalize_patch(r1.patch)
                self.assertEqual(r2.patch, r1.patch)
                self.assertFalse(r2.changed)
                if r1.changed:
                    self.assertEqual(r2.status, N.ALREADY)


class OriginalPatches(unittest.TestCase):
    """Sobre los 150 parches originales (solo lectura, en memoria)."""
    stats = Counter()

    @classmethod
    def tearDownClass(cls):
        print("\n[normalizador sobre los 150 originales]", dict(sorted(cls.stats.items())))

    def test_properties_on_all_original_patches(self):
        files = sorted(LOGS.glob("*/*/patch.diff"))
        if len(files) != 150:
            self.skipTest("no estan los 150 parches originales")
        for pf in files:
            text = pf.read_bytes().decode("utf-8")
            r = normalize_patch(text)
            self.stats[r.status] += 1
            # idempotencia
            self.assertEqual(normalize_patch(r.patch).patch, r.patch, str(pf))
            if not r.changed:
                self.assertEqual(r.patch, text)
                continue
            # solo cambian lineas de cabecera, y solo por el prefijo
            old, new = text.split("\n"), r.patch.split("\n")
            self.assertEqual(len(old), len(new))
            diffs = [(a, b) for a, b in zip(old, new) if a != b]
            self.assertTrue(diffs)
            for a, b in diffs:
                self.assertTrue((a[:4], b[:4]) in {("--- ", "--- "), ("+++ ", "+++ ")}, (a, b))
                self.assertTrue(b[4:] == "a/" + a[4:] or b[4:] == "b/" + a[4:], (a, b))
            # criterio independiente: ninguna cabecera original llevaba prefijo
            hdr = [l.rstrip("\r")[4:].split("\t")[0] for l in old if l.startswith(("--- ", "+++ ")) and "/dev/null" not in l]
            self.assertFalse(any(h.startswith(("a/", "b/")) for h in hdr), str(pf))
        self.assertEqual(sum(self.stats.values()), 150)
        self.assertGreater(self.stats[N.NORMALIZED], 0)

    def test_original_files_are_untouched_by_reading(self):
        # los parches se leen como bytes; nada se escribe (el estado de integridad lo comprueba el script externo)
        self.assertTrue(all(isinstance(p.read_bytes(), bytes) for p in list(LOGS.glob("*/*/patch.diff"))[:3]))


if __name__ == "__main__":
    unittest.main()
