"""Utilidades de prueba: repositorios git temporales (nunca los de repos/) y git apply real."""
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0")
CFG = ["-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "-c", "user.name=t", "-c", "user.email=t@t",
       "-c", "commit.gpgsign=false"]


def git(cwd, *args, check=True, input=None):
    p = subprocess.run(["git", *CFG, *args], cwd=str(cwd), capture_output=True, env=ENV, input=input)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {args} fallo: {p.stderr.decode(errors='replace')}")
    return p


def make_repo(root, files, extra_entries=()):
    """Crea un repo en ``root`` con ``files`` {ruta: bytes}; devuelve el hash del commit.
    ``extra_entries``: (modo, ruta, contenido_blob) para symlinks (120000) o submodulos (160000)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    for rel, data in files.items():
        p = root.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    git(root, "add", "-A")
    for mode, rel, content in extra_entries:
        if mode == "160000":
            sha = "1" * 40
        else:
            sha = git(root, "hash-object", "-w", "--stdin", input=content).stdout.decode().strip()
        git(root, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{rel}")
    git(root, "commit", "-q", "--allow-empty", "-m", "base")
    return git(root, "rev-parse", "HEAD").stdout.decode().strip()


def tree_digest(root):
    """Huella SHA-256 de TODOS los ficheros bajo ``root`` (incluido .git)."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*"), key=lambda q: q.as_posix()):
        if p.is_file() or p.is_symlink():
            h.update(p.relative_to(root).as_posix().encode())
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()


def git_apply_result(files, diff_bytes, rel_paths, strip=1):
    """Aplica ``diff_bytes`` con ``git apply -p1`` real sobre una copia de ``files`` y devuelve
    (returncode, stderr, {ruta: bytes|None})."""
    with tempfile.TemporaryDirectory(prefix="p1test_") as d:
        for rel, data in files.items():
            p = Path(d).joinpath(*rel.split("/"))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        pf = Path(d).parent / (Path(d).name + ".patch")
        pf.write_bytes(diff_bytes)
        try:
            chk = subprocess.run(["git", "apply", "--check", f"-p{strip}", str(pf)], cwd=d, capture_output=True, env=ENV)
            if chk.returncode != 0:
                return chk.returncode, chk.stderr.decode(errors="replace"), {}
            ap = subprocess.run(["git", "apply", f"-p{strip}", str(pf)], cwd=d, capture_output=True, env=ENV)
            out = {}
            for rel in rel_paths:
                p = Path(d).joinpath(*rel.split("/"))
                out[rel] = p.read_bytes() if p.is_file() else None
            return ap.returncode, ap.stderr.decode(errors="replace"), out
        finally:
            pf.unlink(missing_ok=True)
