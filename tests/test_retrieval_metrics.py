import tempfile
import unittest
from pathlib import Path

from src.chunking import Chunk
from src.evaluation.retrieval_metrics import evaluate_retrieval


class TestRetrievalMetrics(unittest.TestCase):

    def create_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        symbol: str = "test_symbol",
    ) -> Chunk:
        return Chunk(
            repository="test/repo",
            file_path=file_path,
            symbol=symbol,
            start_line=start_line,
            end_line=end_line,
            code="",
        )

    def test_perfect_match(self):
        """
        El chunk recuperado coincide exactamente con el gold.
        """

        gold_context = [
            {
                "file": "example.py",
                "start_line": 10,
                "end_line": 20,
            }
        ]

        predicted_chunks = [
            self.create_chunk(
                file_path="example.py",
                start_line=10,
                end_line=20,
            )
        ]

        metrics = evaluate_retrieval(
            predicted_chunks,
            gold_context,
        )

        self.assertEqual(
            metrics["file"]["coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["file"]["precision"],
            1.0,
        )
        self.assertEqual(
            metrics["line"]["coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["line"]["precision"],
            1.0,
        )
        self.assertEqual(
            metrics["line"]["f1"],
            1.0,
        )

    def test_no_line_overlap(self):
        """
        Se recupera el fichero correcto,
        pero no las líneas correctas.
        """

        gold_context = [
            {
                "file": "example.py",
                "start_line": 10,
                "end_line": 20,
            }
        ]

        predicted_chunks = [
            self.create_chunk(
                file_path="example.py",
                start_line=30,
                end_line=40,
            )
        ]

        metrics = evaluate_retrieval(
            predicted_chunks,
            gold_context,
        )

        self.assertEqual(
            metrics["file"]["coverage"],
            1.0,
        )
        self.assertEqual(
            metrics["file"]["precision"],
            1.0,
        )
        self.assertEqual(
            metrics["line"]["coverage"],
            0.0,
        )
        self.assertEqual(
            metrics["line"]["precision"],
            0.0,
        )
        self.assertEqual(
            metrics["line"]["f1"],
            0.0,
        )

    def test_partial_line_overlap(self):
        """
        Solo una parte del chunk coincide con el gold.
        """

        gold_context = [
            {
                "file": "example.py",
                "start_line": 10,
                "end_line": 20,
            }
        ]

        predicted_chunks = [
            self.create_chunk(
                file_path="example.py",
                start_line=15,
                end_line=25,
            )
        ]

        metrics = evaluate_retrieval(
            predicted_chunks,
            gold_context,
        )

        # Gold 10-20 = 11 líneas.
        # Predicción 15-25 = 11 líneas.
        # Intersección 15-20 = 6 líneas.

        expected = 6 / 11

        self.assertAlmostEqual(
            metrics["line"]["coverage"],
            expected,
        )
        self.assertAlmostEqual(
            metrics["line"]["precision"],
            expected,
        )
        self.assertAlmostEqual(
            metrics["line"]["f1"],
            expected,
        )

    def test_perfect_symbol_match(self):
        """
        El chunk recuperado contiene exactamente
        el símbolo considerado gold.
        """

        source_code = (
            "def funcion_correcta():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def funcion_incorrecta():\n"
            "    return 2\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            file_path = repo_root / "example.py"

            file_path.write_text(
                source_code,
                encoding="utf-8",
            )

            gold_context = [
                {
                    "file": "example.py",
                    "start_line": 1,
                    "end_line": 2,
                }
            ]

            predicted_chunks = [
                self.create_chunk(
                    file_path="example.py",
                    start_line=1,
                    end_line=2,
                    symbol="funcion_correcta",
                )
            ]

            metrics = evaluate_retrieval(
                predicted_chunks,
                gold_context,
                repo_root=repo_root,
            )

            self.assertEqual(
                metrics["symbol"]["coverage"],
                1.0,
            )
            self.assertEqual(
                metrics["symbol"]["precision"],
                1.0,
            )
            self.assertEqual(
                metrics["symbol"]["f1"],
                1.0,
            )


if __name__ == "__main__":
    unittest.main()