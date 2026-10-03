import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    repository: str
    file_path: str
    symbol: str
    start_line: int
    end_line: int
    code: str


def chunk_python_file(
    repository: str,
    repo_root: Path,
    file_path: str,
) -> list[Chunk]:

    path = repo_root / file_path
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()

    tree = ast.parse(source)

    chunks: list[Chunk] = []

    def visit(node: ast.AST, scope: tuple[str, ...] = ()) -> None:
        if isinstance(node, ast.ClassDef):
            new_scope = (*scope, node.name)

            for child in node.body:
                visit(child, new_scope)

            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol = ".".join((*scope, node.name))

            start_line = node.lineno
            end_line = node.end_lineno

            code = "\n".join(
                lines[start_line - 1:end_line]
            )

            chunks.append(
                Chunk(
                    repository=repository,
                    file_path=file_path,
                    symbol=symbol,
                    start_line=start_line,
                    end_line=end_line,
                    code=code,
                )
            )

            # Seguimos recorriendo el cuerpo por si contiene
            # funciones anidadas.
            new_scope = (*scope, node.name)

            for child in node.body:
                visit(child, new_scope)

            return

        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree)

    return chunks

def chunk_python_repository(
    repository: str,
    repo_root: Path,
) -> list[Chunk]:

    chunks: list[Chunk] = []

    python_files = sorted(repo_root.rglob("*.py"))

    for path in python_files:
        if ".git" in path.parts:
            continue

        file_path = path.relative_to(repo_root).as_posix()

        try:
            file_chunks = chunk_python_file(
                repository=repository,
                repo_root=repo_root,
                file_path=file_path,
            )

            chunks.extend(file_chunks)

        except (SyntaxError, UnicodeDecodeError) as error:
            print(f"WARNING: no se pudo procesar {file_path}: {error}")

    return chunks

if __name__ == "__main__":
    repo_root = Path("repos/astropy")

    chunks = chunk_python_repository(
        repository="astropy/astropy",
        repo_root=repo_root,
    )

    print(f"\nTotal de chunks: {len(chunks)}")

    files = {chunk.file_path for chunk in chunks}
    print(f"Archivos con chunks: {len(files)}")

    target_chunks = [
        chunk
        for chunk in chunks
        if chunk.file_path == "astropy/modeling/separable.py"
    ]

    print("\nChunks de astropy/modeling/separable.py:")

    for chunk in target_chunks:
        print(
            f"{chunk.symbol}: "
            f"{chunk.start_line}-{chunk.end_line}"
        )