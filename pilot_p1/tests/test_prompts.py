import ast
import csv
import hashlib
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pilot_p1 import applier as A
from pilot_p1 import prompts as P
from pilot_p1 import select_tasks as S
from pilot_p1.edit_format import parse_edits

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs" / "downstream"
GENERATION = ROOT / "src" / "downstream" / "generation.py"
TASKS_CSV = ROOT / "results" / "final_tasks.csv"
HAVE_DATA = LOGS.is_dir() and GENERATION.is_file()


def original_build_prompt():
    """``build_prompt`` REAL del generador original, extraido por AST (sin importar google-genai ni src)."""
    src = GENERATION.read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "build_prompt")
    ns = {"Chunk": object}
    exec(compile(ast.Module([node], []), str(GENERATION), "exec"), ns)
    return ns["build_prompt"]


def stub_chunks(chunks):
    return [SimpleNamespace(file_path=c.file_path, start_line=c.start_line, end_line=c.end_line, symbol=c.symbol,
                            code=c.code) for c in chunks]


def tricky_prompt():
    """Prompt original con contenido adverso: CRLF internos, marcadores de apariencia de plantilla en issue y codigo."""
    chunks = [SimpleNamespace(file_path="pkg/a.py", start_line=1, end_line=4, symbol="f",
                              code="def f():\r\n    return 1\r\n# --- Chunk 9 ---\r\n"),
              SimpleNamespace(file_path="pkg/b.py", start_line=10, end_line=12, symbol="g",
                              code="x = '\\n\\nINSTRUCTIONS:'\nline\n")]
    issue = "Bug.\n\nRETRIEVED CONTEXT:\nnot really\r\nend"
    return original_build_prompt()(issue, chunks)


class FrozenInstructions(unittest.TestCase):
    def test_e1_instructions_hash_is_frozen(self):
        raw = P.E1_INSTRUCTIONS_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), P.E1_INSTRUCTIONS_SHA256)
        self.assertEqual(P.E1_INSTRUCTIONS_SHA256, "3577b64d079143810dd018d805677146fe515bc49904d2862dded53f8db293be")
        self.assertNotIn(b"\r", raw)

    def test_only_the_file_creation_rule_was_added_to_the_first_frozen_version(self):
        lines = P.e1_instructions().splitlines(keepends=True)
        added = [l for l in lines if l.startswith("- To create a new file")]
        self.assertEqual(len(added), 1)
        rest = "".join(l for l in lines if l not in added).encode("utf-8")
        self.assertEqual(hashlib.sha256(rest).hexdigest(),
                         "ae053cec644edcf53308bec657f68b2a687a1cc9ad27728780fdbf9ab29246a8")   # version sin la regla de creacion

    def test_file_creation_instruction_matches_what_the_parser_and_applier_accept(self):
        text = P.e1_instructions()
        rule = next(l for l in text.splitlines() if l.startswith("- To create a new file"))
        for needle in ("SEARCH section is empty", "complete content of the new file", "does not already exist"):
            self.assertIn(needle, rule)
        fix = Path(__file__).parent / "fixtures" / "basic" / "tree"
        # bloque tal como lo describe la regla: SEARCH vacio y contenido completo en REPLACE
        ok = "FILE: pkg/new_module.py\n<<<<<<< SEARCH\n=======\nX = 1\nY = 2\n>>>>>>> REPLACE\n"
        (blk,) = parse_edits(ok)
        self.assertEqual((blk.search, blk.replace), ((), ("X = 1", "Y = 2")))
        r = A.apply_text(ok, A.DirSource(fix))
        self.assertEqual(r.status, A.READY, r.detail)
        self.assertEqual(r.files["pkg/new_module.py"], b"X = 1\nY = 2\n")
        self.assertIn("new file mode", r.diff)
        # ...y "solo para una ruta que no existe": sobre un fichero existente el aplicador lo rechaza
        r2 = A.apply_text(ok.replace("pkg/new_module.py", "pkg/mod.py"), A.DirSource(fix))
        self.assertEqual(r2.status, A.INCONSISTENT)

    def test_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            alt = Path(d) / "x.txt"
            alt.write_bytes(P.E1_INSTRUCTIONS_PATH.read_bytes() + b"- extra\n")
            with mock.patch.object(P, "E1_INSTRUCTIONS_PATH", alt):
                with self.assertRaises(P.PromptError):
                    P.e1_instructions()

    def test_e1_keeps_the_information_sentences_of_the_original(self):
        e1 = P.e1_instructions().splitlines()
        o1 = P.O1_INSTRUCTIONS.splitlines()
        for line in o1[:4]:      # cabecera + tres frases de informacion
            self.assertIn(line, e1)
        self.assertIn("- Do not use Markdown code fences.", e1)
        self.assertNotIn("- Return only a unified diff patch.", e1)
        self.assertNotIn("- Do not include explanations before or after the patch.", e1)

    def test_e1_example_is_accepted_by_the_phase1_parser_and_applier(self):
        text = P.e1_instructions()
        a, b = text.index("FILE: "), text.index(">>>>>>> REPLACE") + len(">>>>>>> REPLACE")
        example = text[a:b]
        example = example.replace('<path exactly as shown in a "File:" line of the retrieved context>', "pkg/mod.py")
        example = example.replace("<text copied exactly from the retrieved context>", "def add(a, b):")
        example = example.replace("<replacement text>", "def add(a, b, c=0):")
        (blk,) = parse_edits(example)
        self.assertEqual((blk.path, blk.search, blk.replace), ("pkg/mod.py", ("def add(a, b):",), ("def add(a, b, c=0):",)))
        fix = Path(__file__).parent / "fixtures" / "basic" / "tree"
        r = A.apply_text(example, A.DirSource(fix))
        self.assertEqual(r.status, A.READY, r.detail)
        # el marcado del ejemplo es exactamente el que exige el parser
        for marker in ("<<<<<<< SEARCH", "\n=======\n", ">>>>>>> REPLACE"):
            self.assertIn(marker, text)

    def test_o1_instructions_equal_the_generator_template(self):
        src = GENERATION.read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "build_prompt")
        js = next(n for n in ast.walk(fn) if isinstance(n, ast.JoinedStr))
        template = "".join(v.value if isinstance(v, ast.Constant) else "{" + v.value.id + "}" for v in js.values)
        expected = P.HEAD + "{problem_statement}" + P.CONTEXT_MARKER + "{retrieved_context}" + "\n\n" + P.O1_INSTRUCTIONS
        self.assertEqual(template, expected)


class SyntheticPrompts(unittest.TestCase):
    def test_reconstruction_round_trip_with_crlf_inside(self):
        o = tricky_prompt()
        raw = P.windows_write_text_bytes(o)
        self.assertIn(b"\r\r\n", raw)                       # el CRLF interno se guardo como CR CR LF
        self.assertEqual(P.reconstruct_prompt(raw), o)
        self.assertIn("\r\n", P.reconstruct_prompt(raw))    # y se recupera como CRLF, sin normalizar

    def test_split_rebuilds_exactly_even_with_adversarial_text(self):
        o = tricky_prompt()
        parts = P.split_prompt(o)
        self.assertEqual([c.file_path for c in parts.chunks], ["pkg/a.py", "pkg/b.py"])
        self.assertEqual(P.rebuild_shared(parts.issue, parts.chunks) + parts.instructions, o)
        self.assertEqual(parts.chunks[0].code, "def f():\r\n    return 1\r\n# --- Chunk 9 ---\r\n")

    def test_real_build_prompt_matches_rebuild_on_synthetic_input(self):
        o = tricky_prompt()
        parts = P.split_prompt(o)
        self.assertEqual(original_build_prompt()(parts.issue, stub_chunks(parts.chunks)), o)

    def test_e1_differs_only_in_instructions_and_keeps_crlf(self):
        o = tricky_prompt()
        e = P.build_e1(P.build_o1(o))
        po, pe = P.split_prompt(o), P.split_prompt(e)
        self.assertEqual(po.shared, pe.shared)
        self.assertEqual(po.chunks, pe.chunks)
        self.assertEqual((po.instructions, pe.instructions), (P.O1_INSTRUCTIONS, P.e1_instructions()))
        self.assertEqual(e[:len(po.shared)], o[:len(po.shared)])
        self.assertEqual(e.count("\r\n"), o.count("\r\n"))
        self.assertEqual(P.context_fingerprint(o), P.context_fingerprint(e))

    def test_new_prompts_are_serialized_without_newline_translation(self):
        e = P.build_e1(tricky_prompt())
        raw = P.serialize_prompt(e)
        self.assertEqual(P.reconstruct_prompt(raw, windows_translated=False), e)
        self.assertNotIn(b"\r\r\n", raw)
        self.assertEqual(raw.count(b"\r\n"), e.count("\r\n"))

    def test_fingerprint_changes_if_any_context_part_changes(self):
        o = tricky_prompt()
        base = P.context_fingerprint(o)
        self.assertNotEqual(base, P.context_fingerprint(o.replace("return 1", "return 2")))
        self.assertNotEqual(base, P.context_fingerprint(o.replace("Bug.", "Bug!")))
        parts = P.split_prompt(o)
        swapped = P.rebuild_shared(parts.issue, [parts.chunks[1], parts.chunks[0]]) + parts.instructions
        with self.assertRaises(P.PromptError):               # el orden de rangos es obligatorio
            P.context_fingerprint(swapped)

    def test_rejections(self):
        o = tricky_prompt()
        with self.assertRaises(P.PromptError):
            P.reconstruct_prompt(o.encode())                 # LF sin CR: no es un fichero de Windows
        with self.assertRaises(P.PromptError):
            P.split_prompt("otro texto")
        with self.assertRaises(P.PromptError):
            P.build_o1(o.replace("Return only a unified diff patch.", "Return a diff."))
        with self.assertRaises(P.PromptError):
            P.build_o1(P.build_e1(o))                        # un prompt E1 no es O1
        with self.assertRaises(P.PromptError):
            P.build_e1(P.build_e1(o))                        # E1 no se reconstruye desde E1
        with self.assertRaises(P.PromptError):
            P.arm_record(o)                                  # solo 2 fragmentos: K debe ser 10

    def test_ambiguous_context_start_is_an_error_not_a_guess(self):
        parts = P.split_prompt(tricky_prompt())
        evil_issue = "x" + P.CONTEXT_MARKER + "--- Chunk 1 ---\nFile: z\n"
        o = P.rebuild_shared(evil_issue, parts.chunks) + P.O1_INSTRUCTIONS
        with self.assertRaises(P.PromptError):
            P.split_prompt(o)


@unittest.skipUnless(HAVE_DATA, "logs/downstream no disponible")
class OriginalConditions(unittest.TestCase):
    stats = Counter()
    PROMPTS = sorted(LOGS.glob("*/*/prompt.txt")) if HAVE_DATA else []

    @classmethod
    def tearDownClass(cls):
        print("\n[prompts sobre las condiciones originales]", dict(sorted(cls.stats.items())))

    def test_all_150_original_prompts_reconstruct_exactly(self):
        self.assertEqual(len(self.PROMPTS), 150)
        build = original_build_prompt()
        for pf in self.PROMPTS:
            raw = pf.read_bytes()
            o = P.reconstruct_prompt(raw)
            tag = f"{pf.parent.parent.name}/{pf.parent.name}"
            self.assertEqual(P.windows_write_text_bytes(o), raw, tag)                 # ida y vuelta exacta con write_text
            parts = P.split_prompt(o)
            self.assertEqual(len(parts.chunks), 10, tag)
            self.assertEqual(build(parts.issue, stub_chunks(parts.chunks)), o, tag)   # codigo original -> mismo prompt
            self.assertEqual(P.build_o1(o), o, tag)
            self.stats["prompts_reconstruidos"] += 1
            self.stats["con_CRLF_interno"] += b"\r\r\n" in raw
            self.stats["CRLF_internos_preservados"] += ("\r\n" in o) == (b"\r\r\n" in raw)

    def test_e1_has_identical_context_for_every_original_condition(self):
        records = {}
        for pf in self.PROMPTS:
            o = P.load_original_prompt(pf)
            e = P.build_e1(o)
            tag = f"{pf.parent.parent.name}/{pf.parent.name}"
            po, pe = P.split_prompt(o), P.split_prompt(e)
            self.assertEqual(po.shared, pe.shared, tag)
            self.assertEqual(po.chunks, pe.chunks, tag)
            self.assertEqual(po.issue, pe.issue, tag)
            self.assertEqual(e[:len(po.shared)].encode(), o[:len(po.shared)].encode(), tag)
            self.assertEqual(e.count("\r\n"), o.count("\r\n"), tag)
            self.assertEqual(pe.instructions, P.e1_instructions(), tag)
            rec = P.arm_record(o)
            self.assertTrue(rec["context_identical"], tag)
            self.assertNotEqual(rec["o1_prompt_sha256"], rec["e1_prompt_sha256"])
            records[tag] = rec
            self.stats["contexto_identico_O1_E1"] += 1
        self.assertEqual(len(records), 150)
        # arm_record es determinista
        some = self.PROMPTS[0]
        self.assertEqual(P.arm_record(P.load_original_prompt(some)), records[f"{some.parent.parent.name}/{some.parent.name}"])

    def test_pilot_selection_has_all_36_original_prompts(self):
        ids = S.verify_manifest(S.load_manifest())
        for task, method in S.conditions(ids):
            self.assertTrue((LOGS / task / method / "prompt.txt").is_file(), (task, method))
        self.stats["condiciones_piloto_con_prompt_original"] = 36

    def test_e1_file_paths_are_usable_by_the_applier(self):
        """Toda ruta 'File:' del contexto es segura y existe como fichero en el base_commit (solo lectura)."""
        if not (TASKS_CSV.is_file() and (ROOT / "repos").is_dir()):
            self.skipTest("sin repos/")
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            tasks = {r["original_inst_id"]: r for r in csv.DictReader(fh)}
        ids = S.verify_manifest(S.load_manifest())
        seen = {}
        for task, method in S.conditions(ids):
            row = tasks[task]
            repo = ROOT / "repos" / row["repo"].replace("/", "__")
            src = seen.setdefault(task, A.GitSource(repo, row["base_commit"]))
            parts = P.split_prompt(P.load_original_prompt(LOGS / task / method / "prompt.txt"))
            for c in parts.chunks:
                self.assertIsNone(A.path_problem(c.file_path), c.file_path)
                ent = src.entry(c.file_path)
                self.assertTrue(ent is not None and ent.kind == "file", (task, c.file_path))
                self.stats["rutas_File_verificadas"] += 1

    def test_copying_context_lines_yields_applicable_edits(self):
        """Respuesta E1 simulada (no del modelo): SEARCH = primeras lineas de codigo del primer fragmento."""
        if not (TASKS_CSV.is_file() and (ROOT / "repos").is_dir()):
            self.skipTest("sin repos/")
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            tasks = {r["original_inst_id"]: r for r in csv.DictReader(fh)}
        res = Counter()
        for task, method in S.conditions(S.verify_manifest(S.load_manifest())):
            row = tasks[task]
            src = A.GitSource(ROOT / "repos" / row["repo"].replace("/", "__"), row["base_commit"])
            c = P.split_prompt(P.load_original_prompt(LOGS / task / method / "prompt.txt")).chunks[0]
            lines = [l.rstrip("\r") for l in c.code.replace("\r\n", "\n").split("\n")]
            body = lines[:6]                                   # contiguas, tal como estan en el contexto
            if not any(l.strip() for l in body):
                continue
            answer = "\n".join([f"FILE: {c.file_path}", "<<<<<<< SEARCH", *body, "=======", *body, "# pilot-check",
                                ">>>>>>> REPLACE"]) + "\n"
            r = A.apply_text(answer, src)
            res[r.status] += 1
            self.assertIn(r.status, {A.READY, A.AMBIGUOUS}, f"{task}/{method}: {r.detail}")
        self.stats.update({f"simulada_{k}": v for k, v in res.items()})
        self.assertGreater(res[A.READY], 0)

    def test_context_chunks_are_the_exact_text_of_the_base_commit_files(self):
        """Procedencia del contexto: el codigo de cada fragmento (360 en las 36 condiciones) coincide con las lineas
        start..end del fichero en el base_commit (salvo espacios finales); por eso copiar contexto sirve como SEARCH."""
        if not (TASKS_CSV.is_file() and (ROOT / "repos").is_dir()):
            self.skipTest("sin repos/")
        with TASKS_CSV.open(encoding="utf-8", newline="") as fh:
            tasks = {r["original_inst_id"]: r for r in csv.DictReader(fh)}
        for task, method in S.conditions(S.verify_manifest(S.load_manifest())):
            row = tasks[task]
            src = A.GitSource(ROOT / "repos" / row["repo"].replace("/", "__"), row["base_commit"])
            for c in P.split_prompt(P.load_original_prompt(LOGS / task / method / "prompt.txt")).chunks:
                blob = src.read(src.entry(c.file_path)).decode("utf-8").replace("\r\n", "\n").split("\n")
                seg = [x.rstrip(" \t") for x in blob[c.start_line - 1:c.end_line]]
                code = [x.rstrip(" \t") for x in c.code.replace("\r\n", "\n").split("\n")[:len(seg)]]
                self.assertEqual(code, seg, (task, method, c.rank, c.file_path))
                self.stats["fragmentos_iguales_al_fichero"] += 1


if __name__ == "__main__":
    unittest.main()
