import unittest

from pilot_p1.edit_format import EditFormatError, parse_edits

S, M, R = "<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"


def blk(path, search, replace):
    return "\n".join([f"FILE: {path}", S, *search, M, *replace, R]) + "\n"


class ParserAccepts(unittest.TestCase):
    def test_basic(self):
        (b,) = parse_edits(blk("a/b.py", ["x = 1"], ["x = 2"]))
        self.assertEqual((b.path, b.search, b.replace, b.index), ("a/b.py", ("x = 1",), ("x = 2",), 0))

    def test_multiline_and_blank_lines_preserved(self):
        (b,) = parse_edits(blk("f.py", ["a", "", "  b"], ["", "c"]))
        self.assertEqual(b.search, ("a", "", "  b"))
        self.assertEqual(b.replace, ("", "c"))

    def test_several_blocks_same_file(self):
        t = f"FILE: f.py\n{S}\na\n{M}\nb\n{R}\n\n{S}\nc\n{M}\nd\n{R}\n"
        bs = parse_edits(t)
        self.assertEqual([(x.path, x.search) for x in bs], [("f.py", ("a",)), ("f.py", ("c",))])
        self.assertEqual([x.index for x in bs], [0, 1])

    def test_several_files(self):
        bs = parse_edits(blk("a.py", ["1"], ["2"]) + blk("b.py", ["3"], ["4"]))
        self.assertEqual([x.path for x in bs], ["a.py", "b.py"])

    def test_empty_replace_is_deletion(self):
        (b,) = parse_edits(blk("f.py", ["old"], []))
        self.assertEqual(b.replace, ())

    def test_empty_search_is_creation_request(self):
        (b,) = parse_edits(blk("new.py", [], ["print(1)"]))
        self.assertEqual(b.search, ())

    def test_crlf_and_cr_input_normalised(self):
        t = blk("f.py", ["a", "b"], ["c"]).replace("\n", "\r\n")
        (b,) = parse_edits(t)
        self.assertEqual((b.search, b.replace), (("a", "b"), ("c",)))
        (b,) = parse_edits(blk("f.py", ["a", "b"], ["c"]).replace("\n", "\r"))
        self.assertEqual(b.search, ("a", "b"))

    def test_markdown_fences_and_blank_lines_outside_allowed(self):
        (b,) = parse_edits("```\n\n" + blk("f.py", ["a"], ["b"]) + "\n```\n")
        self.assertEqual(b.path, "f.py")

    def test_trailing_whitespace_on_markers_and_file_line(self):
        t = f"FILE:   f.py  \n{S}  \na\n{M}\t\nb\n{R}   \n"
        (b,) = parse_edits(t)
        self.assertEqual((b.path, b.search, b.replace), ("f.py", ("a",), ("b",)))

    def test_no_final_newline_in_instruction(self):
        (b,) = parse_edits(blk("f.py", ["a"], ["b"]).rstrip("\n"))
        self.assertEqual(b.replace, ("b",))

    def test_marker_like_text_inside_line_is_content(self):
        (b,) = parse_edits(blk("f.py", ["x = '======='", "# <<<<<<< SEARCH"], ["y"]))
        self.assertEqual(b.search, ("x = '======='", "# <<<<<<< SEARCH"))

    def test_trailing_spaces_and_tabs_in_content_preserved(self):
        (b,) = parse_edits(blk("f.py", ["a \t", "\tb"], ["c"]))
        self.assertEqual(b.search, ("a \t", "\tb"))

    def test_path_with_spaces_inside(self):
        (b,) = parse_edits(blk("dir/my file.py", ["a"], ["b"]))
        self.assertEqual(b.path, "dir/my file.py")

    def test_block_line_number_recorded(self):
        bs = parse_edits(blk("a", ["1"], ["2"]) + blk("b", ["3"], ["4"]))
        self.assertEqual([x.line for x in bs], [2, 8])


class ParserRejects(unittest.TestCase):
    def assertBad(self, text, fragment=""):
        with self.assertRaises(EditFormatError) as cm:
            parse_edits(text)
        self.assertIn(fragment, cm.exception.message)
        return cm.exception

    def test_empty_and_whitespace(self):
        self.assertBad("", "ningun bloque")
        self.assertBad("  \n\n", "ningun bloque")

    def test_not_text(self):
        with self.assertRaises(EditFormatError):
            parse_edits(None)

    def test_prose_only(self):
        self.assertBad("Here is my fix: change x to y.", "fuera de un bloque")

    def test_prose_between_blocks(self):
        self.assertBad(blk("a", ["1"], ["2"]) + "Now the other file\n" + blk("b", ["3"], ["4"]), "fuera de un bloque")

    def test_unified_diff_is_not_accepted(self):
        self.assertBad("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n", "fuera de un bloque")

    def test_search_without_file(self):
        self.assertBad(f"{S}\na\n{M}\nb\n{R}\n", "sin FILE")

    def test_file_without_path(self):
        self.assertBad(f"FILE:\n{S}\na\n{M}\nb\n{R}\n", "sin ruta")

    def test_file_lowercase_rejected(self):
        self.assertBad(f"file: f.py\n{S}\na\n{M}\nb\n{R}\n", "fuera de un bloque")

    def test_file_without_block_then_file(self):
        self.assertBad("FILE: a.py\n" + blk("b.py", ["1"], ["2"]), "sin ningun bloque")

    def test_file_without_block_at_end(self):
        self.assertBad(blk("a.py", ["1"], ["2"]) + "FILE: b.py\n", "sin ningun bloque")

    def test_unterminated_search(self):
        e = self.assertBad(f"FILE: f.py\n{S}\na\n", "sin separador")
        self.assertEqual(e.line, 2)

    def test_unterminated_replace(self):
        self.assertBad(f"FILE: f.py\n{S}\na\n{M}\nb\n", "sin cierre")

    def test_missing_separator_closing_marker_in_search(self):
        self.assertBad(f"FILE: f.py\n{S}\na\n{R}\n", "inesperado dentro de SEARCH")

    def test_nested_search_marker(self):
        self.assertBad(f"FILE: f.py\n{S}\na\n{S}\nb\n{M}\nc\n{R}\n", "inesperado dentro de SEARCH")

    def test_duplicate_separator(self):
        self.assertBad(f"FILE: f.py\n{S}\na\n{M}\nb\n{M}\nc\n{R}\n", "inesperado dentro de REPLACE")

    def test_search_marker_inside_replace(self):
        self.assertBad(f"FILE: f.py\n{S}\na\n{M}\n{S}\n{R}\n", "inesperado dentro de REPLACE")

    def test_wrong_marker_lengths(self):
        self.assertBad(f"FILE: f.py\n<<<<<< SEARCH\na\n{M}\nb\n{R}\n", "fuera de un bloque")

    def test_error_in_second_block_reports_line(self):
        e = self.assertBad(blk("a", ["1"], ["2"]) + f"FILE: b\n{S}\nx\n", "sin separador")
        self.assertEqual(e.line, 8)


if __name__ == "__main__":
    unittest.main()
