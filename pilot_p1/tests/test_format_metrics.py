import unittest
from unittest import mock

from pilot_p1 import format_metrics as F

S, M, R = "<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"
BLOCK = f"FILE: a.py\n{S}\nx\n{M}\ny\n{R}\n"
DIFF = "--- a.py\n+++ a.py\n@@ -1 +1 @@\n-x\n+y\n"


class Fences(unittest.TestCase):
    def test_clean_responses(self):
        for text, arm in ((BLOCK, "E1"), (DIFF, "O1")):
            m = F.fence_metrics(text, arm)
            self.assertEqual((m["external_fence_lines"], m["inner_fence_sequences"], m["wraps_response"]), (0, 0, False))

    def test_external_fences_wrapping_e1(self):
        m = F.fence_metrics("```\n" + BLOCK + "```\n", "E1")
        self.assertEqual((m["external_fence_lines"], m["wraps_response"], m["inner_fences_present"]), (2, True, False))

    def test_external_fence_with_language_and_indent(self):
        m = F.fence_metrics("  ```python\n" + BLOCK, "E1")
        self.assertEqual(m["external_fence_lines"], 1)
        self.assertFalse(m["wraps_response"])

    def test_fences_accompanying_prose(self):
        m = F.fence_metrics("Here is the fix:\n```\n" + BLOCK + "```\nDone.\n", "E1")
        self.assertEqual((m["external_fence_lines"], m["wraps_response"]), (2, False))

    def test_inner_fences_inside_edit_content(self):
        t = f"FILE: README.md\n{S}\n```bash\npip install x\n```\n{M}\n```bash\npip install y\n```\n{R}\n"
        m = F.fence_metrics(t, "E1")
        self.assertEqual((m["external_fence_lines"], m["inner_fence_lines"], m["inner_fence_sequences"]), (0, 4, 4))
        self.assertTrue(m["inner_fences_present"])
        self.assertFalse(m["external_fences_present"])

    def test_inner_sequence_in_the_middle_of_a_line(self):
        t = f"FILE: a.py\n{S}\ns = '```'\n{M}\ns = '````'\n{R}\n"
        m = F.fence_metrics(t, "E1")
        self.assertEqual((m["inner_fence_lines"], m["inner_fence_sequences"]), (0, 2))

    def test_external_and_inner_are_counted_separately(self):
        t = "```\n" + f"FILE: a.md\n{S}\n```\n{M}\n```x\n{R}\n" + "```\n"
        m = F.fence_metrics(t, "E1")
        self.assertEqual((m["external_fence_lines"], m["inner_fence_lines"]), (2, 2))

    def test_o1_diff_wrapped_and_inner(self):
        m = F.fence_metrics("```diff\n" + DIFF + "```\n", "O1")
        self.assertEqual((m["external_fence_lines"], m["wraps_response"], m["inner_fence_sequences"]), (2, True, 0))
        inner = "--- a.md\n+++ a.md\n@@ -1 +1 @@\n-```\n+```py\n"
        m = F.fence_metrics(inner, "O1")
        self.assertEqual((m["external_fence_lines"], m["inner_fence_lines"], m["inner_fence_sequences"]), (0, 2, 2))

    def test_unterminated_block_does_not_hide_fences(self):
        m = F.fence_metrics(f"FILE: a\n{S}\nx\n```\n", "E1")
        self.assertEqual((m["external_fence_lines"], m["inner_fence_lines"]), (0, 1))

    def test_crlf_input(self):
        m = F.fence_metrics(("```\n" + BLOCK + "```\n").replace("\n", "\r\n"), "E1")
        self.assertEqual(m["external_fence_lines"], 2)

    def test_unknown_arm(self):
        with self.assertRaises(ValueError):
            F.fence_metrics("x", "O0")


class UnionIndicator(unittest.TestCase):
    CASES = [("```\n" + BLOCK + "```\n", "E1"), (BLOCK, "E1"), (f"FILE: a.md\n{S}\n```x\n{M}\n```y\n{R}\n", "E1"),
             ("```\n" + f"FILE: a.md\n{S}\n```\n{M}\n```x\n{R}\n" + "```\n", "E1"), ("  ```\n" + BLOCK, "E1"),
             ("```diff\n" + DIFF + "```\n", "O1"), (DIFF, "O1")]

    def test_union_is_external_or_inner(self):
        for text, arm in self.CASES:
            m = F.fence_metrics(text, arm)
            self.assertEqual(m["fences_union_present"], m["external_fences_present"] or m["inner_fences_present"], (text, arm))

    def test_for_line_start_fences_the_union_equals_the_original_metric(self):
        for text, arm in self.CASES[:5]:
            m = F.fence_metrics(text, arm)
            self.assertEqual(m["fences_union_present"], m["original_metric_a_present"], text)

    def test_original_metric_is_any_line_starting_with_a_fence(self):
        self.assertFalse(F.fence_metrics(BLOCK, "E1")["original_metric_a_present"])
        self.assertTrue(F.fence_metrics("  ```\n" + BLOCK, "E1")["original_metric_a_present"])
        self.assertTrue(F.fence_metrics(f"FILE: a\n{S}\n```\n{M}\ny\n{R}\n", "E1")["original_metric_a_present"])

    def test_union_may_exceed_the_original_only_for_midline_sequences(self):
        t = f"FILE: a.py\n{S}\ns = '```'\n{M}\ns = 'x'\n{R}\n"
        m = F.fence_metrics(t, "E1")
        self.assertTrue(m["fences_union_present"] and not m["original_metric_a_present"])

    def test_fence_indicators_never_change_parseability(self):
        for text, arm in self.CASES:
            m = F.format_metrics(text, arm)
            if arm == "E1":
                try:
                    F.parse_edits(text)
                    direct = True
                except F.EditFormatError:
                    direct = False
                self.assertEqual(m["parse"]["parseable"], direct, text)
            else:
                self.assertIsNone(m["parse"]["parseable"])


class Parseability(unittest.TestCase):
    def test_parseable_unparseable_and_not_applicable(self):
        self.assertEqual(F.parseability(BLOCK, "E1")["parseable"], True)
        self.assertEqual(F.parseability("hola", "E1")["parseable"], False)
        self.assertIsNone(F.parseability(DIFF, "O1")["parseable"])
        self.assertFalse(F.parseability(DIFF, "O1")["applicable"])

    def test_fences_with_parseable_answer(self):
        m = F.format_metrics("```\n" + BLOCK + "```\n", "E1")
        self.assertTrue(m["parse"]["parseable"] and m["external_fences_present"] and m["fences_and_parseable"])

    def test_indented_fence_outside_block_is_a_parse_error_but_still_detected(self):
        m = F.format_metrics("  ```\n" + BLOCK, "E1")
        self.assertFalse(m["parse"]["parseable"])
        self.assertTrue(m["external_fences_present"])
        self.assertFalse(m["fences_and_parseable"])


class Independence(unittest.TestCase):
    def test_fence_detection_does_not_call_the_parser_or_modify_the_text(self):
        text = "```\n" + BLOCK + "```\n"
        keep = str(text)
        with mock.patch.object(F, "parse_edits", side_effect=AssertionError("el parser no debe usarse")):
            m = F.fence_metrics(text, "E1")
        self.assertEqual(m["external_fence_lines"], 2)
        self.assertEqual(text, keep)
        F.format_metrics(text, "E1")
        self.assertEqual(text, keep)


if __name__ == "__main__":
    unittest.main()
