import subprocess
from pathlib import Path


REPOS_ROOT = Path("repos")


def run_git(args: list[str], cwd: Path | None = None) -> None:
    """
    Ejecuta un comando Git y detiene el experimento si falla.
    """
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
    )


def prepare_repository(
    repository: str,
    repo_url: str,
    base_commit: str,
) -> Path:
    """
    Prepara un repositorio en el commit exacto indicado por ContextBench.

    Si el repositorio no existe localmente, lo clona.
    Después sitúa el repositorio en base_commit.

    Devuelve la ruta local del repositorio.
    """
    repo_name = repository.replace("/", "__")
    repo_root = REPOS_ROOT / repo_name

    if not repo_root.exists():
        print(f"Clonando {repository}...")

        run_git([
            "clone",
            repo_url,
            str(repo_root),
        ])

    print(
        f"Preparando {repository} "
        f"en commit {base_commit[:12]}..."
    )

    run_git(
        ["fetch", "origin"],
        cwd=repo_root,
    )

    run_git(
        ["checkout", "--force", base_commit],
        cwd=repo_root,
    )

    return repo_root