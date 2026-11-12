"""Matriz factorial 2x2x2 de aplicabilidad de parches: finales de linea del parche x finales de linea del arbol x -p.

Fase 2 del diagnostico (docs/downstream-patch-diagnostics.md, seccion 12). SOLO LECTURA sobre el proyecto y los repos.

Que hace
    Para cada parche seleccionado reconstruye, en un directorio temporal fuera de cualquier repositorio, los ficheros
    del base_commit que el parche puede tocar (con finales de linea CRLF o LF) y ejecuta unicamente
    `git apply --check -p{0|1}` con el parche original (CRLF) o normalizado a LF (copia temporal).

Que NO hace
    No modifica repos/, results/, logs/ ni los patch.diff. No hace checkout/worktree/--reject/--3way. No llama al LLM.
    No ejecuta evaluadores oficiales. Una reconstruccion que pase la comprobacion NO demuestra que el evaluador
    oficial (Linux/Docker) acepte el parche, ni que resuelva la incidencia.

Uso (desde cualquier directorio; la raiz se localiza sola)
    python -I eol_prefix_matrix.py                       # PLAN: muestra seleccion y celdas; no ejecuta nada
    python -I eol_prefix_matrix.py --pilot --run         # piloto (~7 parches)
    python -I eol_prefix_matrix.py --run                 # matriz completa (150 parches, 8 celdas + 4 de robustez)
    python -I eol_prefix_matrix.py --only-baseline --run # solo la celda de linea base

Salida: diagnostics/downstream-patches/output/eol_prefix_matrix_<UTC>/ (directorio nuevo; nunca se reutiliza).
Codigos de salida: 0 correcto; 2 la linea base no reproduce lo original (se detiene); 3 la integridad cambio;
4 fallo de preparacion.

Historial: 1.0 (2026-11-11) primera version (piloto y linea base de 150). 1.1 (2026-11-12) SOLO REGISTRO: la configuracion
de Git del manifest se lista desde el directorio temporal (antes se listaba el .git/config del proyecto, con la URL del
remoto), solo con las claves relevantes, y se registra la configuracion efectiva de core.autocrlf de cada matriz.
No cambia la reconstruccion, las transformaciones, las opciones de git apply ni los criterios de comparacion.
1.2 (2026-11-12) SOLO SEGURIDAD: `git config` solo se permite con las dos consultas de lectura exactas que usa el script
(ALLOWED_CONFIG_ARGS); se rechaza cualquier otra combinacion de argumentos, incluidas las que mezclan lectura y escritura.
"""
import argparse
import atexit
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter

VERSION = '1.2'
ROOT = next(p for p in pathlib.Path(__file__).resolve().parents if (p / 'results' / 'final_tasks.csv').exists())
RESULTS = ROOT / 'results' / 'downstream_results_final.jsonl'
TASKS_CSV = ROOT / 'results' / 'final_tasks.csv'
REPOS = ROOT / 'repos'
OUT_BASE = ROOT / 'diagnostics' / 'downstream-patches' / 'output'

MAX_PATH_LEN = 240            # por debajo del limite clasico de Windows; si se supera, la celda es "no_evaluable"
GIT_MIN_VERSION = (2, 40)     # `git check-attr --source`
BASELINE = ('CRLF', 'CRLF', 1)                                                   # (parche, arbol, p) = condiciones originales
MAIN_CELLS = [(pe, te, p) for p in (1, 0) for pe in ('CRLF', 'LF') for te in ('CRLF', 'LF')]   # 8, autocrlf=true
ROBUST_CELLS = [(pe, 'LF', p) for p in (1, 0) for pe in ('CRLF', 'LF')]          # 4, autocrlf=false (replica aparte)
PILOT_EXPLICIT = [
    ('pytest-dev__pytest-5809', 'semantic'),                  # sin prefijo, "No such file"
    ('instance_ansible__ansible-39bd8b99', 'bm25'),           # sin prefijo, ruta larga, repo con .gitattributes
    ('instance_ansible__ansible-39bd8b99', 'semantic'),       # respuesta sin diff (control negativo)
    ('pylint-dev__pylint-4970', 'hybrid'),                    # paso -p0 en el repo real (observacion previa)
    ('huggingface__transformers-26752', 'hybrid'),            # fichero con eol=lf en .gitattributes
]
ALLOWED_GIT = {'cat-file', 'check-attr', 'ls-tree', 'rev-parse', 'config', 'apply'}   # lista blanca de subcomandos
# Claves de configuracion que se registran en el manifest (solo las que pueden afectar a la comprobacion).
CFG_REGEX = r'^(core\.(autocrlf|eol|safecrlf|whitespace|ignorecase|symlinks|longpaths|filemode)|apply\.)'
CFG_FORBIDDEN_IN_MANIFEST = ('remote.', 'github.com', 'user.email', 'user.name', '.git/config')
# `git config` solo se permite con EXACTAMENTE estas dos consultas de lectura (los argumentos tras `config`); cualquier
# otra combinacion se rechaza, aunque incluya una opcion de lectura (p. ej. `--get x --unset`).
ALLOWED_CONFIG_ARGS = {('--show-origin', '--get-regexp', CFG_REGEX), ('--get', 'core.autocrlf')}

DIFFERENCES_WITH_ORIGINAL = [
    'Arbol parcial: solo los ficheros candidatos de las cabeceras del parche (el original aplico sobre el repo completo).',
    'Ejecucion fuera de un repositorio: sin indice ni .gitattributes del arbol de trabajo; los atributos se leen con '
    '`git check-attr --source <base_commit>`.',
    'Configuracion de Git aislada (sin config global ni de sistema reales) con core.autocrlf fijado en -c; el original '
    'uso la configuracion real de la maquina.',
    'Localizacion fijada a LC_ALL=C para mensajes de Git deterministas.',
    'Los finales de linea del arbol se EMULAN con la regla de autocrlf/.gitattributes validada 39/39; no hay checkout real.',
    'Linux/Docker NO se reproduce: el arbol LF es una condicion de SENSIBILIDAD, no una equivalencia demostrada con el '
    'entorno de los evaluadores oficiales.',
    'La version de Git del original no esta registrada; solo se registra la version actual.',
]


# ----------------------------------------------------------------------------------------------------------------------
# utilidades puras (sin git ni ficheros): se pueden probar con datos sinteticos
# ----------------------------------------------------------------------------------------------------------------------
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(pathlib.Path(p).read_bytes())


def norm_msg(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def categorize(rc, msg):
    """Misma prioridad que classify_invalid_patches.py."""
    if rc == 0:
        return 'aplica'
    for key, label in [('No valid patches', 'sin_diff_valido'), ('corrupt patch', 'corrupt_patch'),
                       ('without header', 'fragmento_sin_cabecera'), ('No such file', 'fichero_inexistente'),
                       ('patch failed', 'contexto_no_coincide')]:
        if key in msg:
            return label
    return 'otro'


def parse_headers(text):
    """Rutas de las cabeceras `---`, `+++` y `diff --git` (sin /dev/null)."""
    minus = [h for h in re.findall(r'^--- (\S+)', text, re.M) if h != '/dev/null']
    plus = [h for h in re.findall(r'^\+\+\+ (\S+)', text, re.M) if h != '/dev/null']
    git_names = []
    for a, b in re.findall(r'^diff --git (\S+) (\S+)', text, re.M):
        git_names += [a, b]
    return minus, plus, git_names


def prefix_group(minus, plus):
    """(grupo, -p natural). Mismo criterio de grupos que classify_invalid_patches.py, comprobando tambien `+++`."""
    allp = minus + plus
    if not allp:
        return 'sin_cabeceras', None
    m_ok = all(h.startswith('a/') for h in minus)
    p_ok = all(h.startswith('b/') for h in plus)
    if m_ok and p_ok:
        return 'todo_a/', 1
    if not any(h.startswith(('a/', 'b/')) for h in allp):
        return 'sin_prefijo', 0
    return 'indeterminado', None


def strip_components(path, p):
    """Quita p componentes iniciales (semantica de -p). None si no queda ruta."""
    parts = [c for c in path.split('/') if c != '']
    return '/'.join(parts[p:]) if len(parts) > p else None


def candidate_targets(paths):
    """Rutas candidatas: cada cabecera con -p0 y -p1. Se descartan absolutas, con '..' o vacias."""
    out = []
    for h in paths:
        for p in (0, 1):
            t = strip_components(h, p)
            if t and not t.startswith('/') and '..' not in t.split('/') and not re.match(r'^[A-Za-z]:', t) and t not in out:
                out.append(t)
    return out


def normalize_patch(raw):
    """CRLF -> LF en bytes. Devuelve (bytes_LF | None, anomalias). Exige perdida cero (ida y vuelta identica)."""
    anomalies = []
    if raw.startswith(b'\xef\xbb\xbf'):
        anomalies.append('BOM')
    n_crlf = raw.count(b'\r\n')
    if raw.count(b'\n') - n_crlf:
        anomalies.append('lineas_LF_puro')
    if re.search(rb'\r(?!\n)', raw):
        anomalies.append('CR_aislado')
    if b'\r\r\n' in raw:
        anomalies.append('CR_CR_LF')
    lf = raw.replace(b'\r\n', b'\n')
    if lf.replace(b'\n', b'\r\n') != raw:
        anomalies.append('ida_y_vuelta_falla')
    return (None if anomalies else lf), anomalies


def smudge_crlf_tree(blob, a):
    """Emula lo que Git deja en el arbol de trabajo con core.autocrlf=true (regla validada 39/39)."""
    text, eol = a.get('text', 'unspecified'), a.get('eol', 'unspecified')
    if text == 'unset' or b'\0' in blob:
        return blob, 'sin_conversion(text_unset_o_binario)'
    if eol == 'lf':
        return blob, 'LF(eol=lf)'
    if eol == 'crlf' or text in ('set', 'auto', 'unspecified'):
        if b'\r' in blob and eol != 'crlf':
            return blob, 'sin_conversion(blob_con_CR)'
        return re.sub(rb'(?<!\r)\n', b'\r\n', blob), 'CRLF'
    return blob, 'sin_conversion'


def smudge_lf_tree(blob, a):
    """Arbol LF: blob tal cual, salvo `eol=crlf` explicito (un checkout en Linux tambien lo respetaria)."""
    text, eol = a.get('text', 'unspecified'), a.get('eol', 'unspecified')
    if eol == 'crlf' and text != 'unset' and b'\0' not in blob:
        if b'\r' in blob:
            return blob, 'LF(blob_con_CR)'
        return re.sub(rb'(?<!\r)\n', b'\r\n', blob), 'CRLF(eol=crlf)'
    return blob, 'LF'


def roundtrip_ok(original_blob, converted):
    """Si el blob no tenia CR, convertir de vuelta debe devolver el blob; si lo tenia, no se convierte."""
    if b'\r' in original_blob:
        return converted == original_blob
    return converted.replace(b'\r\n', b'\n') == original_blob


def tree_digest(root):
    h = hashlib.sha256()
    for p in sorted(pathlib.Path(root).rglob('*')):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode('utf-8'))
            h.update(sha256_file(p).encode('ascii'))
    return h.hexdigest()


def is_under(path, base):
    try:
        pathlib.Path(path).resolve().relative_to(pathlib.Path(base).resolve())
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------------------------------------------------------------
# ejecucion de git (lista blanca; nunca se aplica sobre repos/)
# ----------------------------------------------------------------------------------------------------------------------
class Git:
    def __init__(self, tmp_root):
        self.tmp_root = pathlib.Path(tmp_root)
        self.empty_cfg = self.tmp_root / 'empty.gitconfig'
        self.empty_cfg.write_bytes(b'')

    def run(self, sub, *args, repo=None, cwd=None, config=None, isolated=True, timeout=120, use_ceiling=True):
        if sub not in ALLOWED_GIT:
            raise RuntimeError(f'subcomando git no permitido: {sub}')
        if sub == 'apply':
            if '--check' not in args or repo is not None:
                raise RuntimeError('apply solo se permite con --check y sin -C repositorio')
            if cwd is None or not is_under(cwd, self.tmp_root):
                raise RuntimeError('apply solo se permite dentro del directorio temporal')
        if sub == 'config' and tuple(args) not in ALLOWED_CONFIG_ARGS:
            raise RuntimeError('config solo con las consultas de lectura que usa el script')
        cmd = ['git', '--no-optional-locks']
        if repo is not None:
            cmd += ['-C', str(repo)]
        for k, v in (config or {}).items():
            cmd += ['-c', f'{k}={v}']
        cmd += [sub, *args]
        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        env['LANG'] = 'C'
        env.pop('LANGUAGE', None)
        if use_ceiling:
            env['GIT_CEILING_DIRECTORIES'] = self.tmp_root.resolve().as_posix()
        else:
            env.pop('GIT_CEILING_DIRECTORIES', None)
        if isolated:
            env['GIT_CONFIG_NOSYSTEM'] = '1'
            env['GIT_CONFIG_GLOBAL'] = str(self.empty_cfg)
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr


def dec(b):
    return b.decode('utf-8', errors='replace')


def git_version():
    txt = dec(subprocess.run(['git', '--version'], capture_output=True).stdout).strip()
    m = re.search(r'(\d+)\.(\d+)', txt)
    return txt, ((int(m.group(1)), int(m.group(2))) if m else (0, 0))


def sanitize_lines(lines):
    """Sustituye el directorio personal por `~` en lo que se guarda en el manifest."""
    home = pathlib.Path.home().as_posix()
    return [l.replace(home, '~') for l in lines]


def config_snapshot(git, cwd, isolated):
    """Configuracion relevante de Git vista DESDE `cwd` (el temporal, fuera de cualquier repositorio).
    Con isolated=True es lo que ve `git apply` (sin config global ni de sistema; el -c de autocrlf se registra aparte).
    Devuelve None si git falla (rc 1 solo significa 'sin coincidencias')."""
    rc, out, _ = git.run('config', '--show-origin', '--get-regexp', CFG_REGEX, cwd=cwd, isolated=isolated)
    return sanitize_lines(dec(out).splitlines()) if rc in (0, 1) else None


def effective_autocrlf(git, cwd, value):
    """Valor efectivo de core.autocrlf cuando se pasa `-c core.autocrlf=<value>` (como en las comprobaciones)."""
    rc, out, _ = git.run('config', '--get', 'core.autocrlf', cwd=cwd, isolated=True, config={'core.autocrlf': value})
    return dec(out).strip() if rc == 0 else None


# ----------------------------------------------------------------------------------------------------------------------
# datos y reconstruccion
# ----------------------------------------------------------------------------------------------------------------------
def patch_file_of(row):
    return ROOT / pathlib.PureWindowsPath(row['patch_path']).as_posix()


def load_rows():
    rows = [json.loads(l) for l in open(RESULTS, encoding='utf-8-sig') if l.strip()]
    if len(rows) != 150:
        raise RuntimeError(f'se esperaban 150 filas y hay {len(rows)}')
    rows.sort(key=lambda r: (r['task_id'], r['retrieval_method']))
    tasks = {r['original_inst_id']: r for r in csv.DictReader(open(TASKS_CSV, encoding='utf-8-sig'))}
    return rows, tasks


def select_rows(rows, args):
    inv = [r for r in rows if r['status'] == 'invalid_patch']
    app = [r for r in rows if r['status'] != 'invalid_patch']
    if len(inv) != 141 or len(app) != 9:
        raise RuntimeError(f'se esperaban 141 invalid_patch y 9 aplicables; hay {len(inv)} y {len(app)}')
    if not args.pilot:
        return inv + app
    chosen = []
    for prefix, method in PILOT_EXPLICIT:
        m = [r for r in rows if r['task_id'].startswith(prefix) and r['retrieval_method'] == method]
        if len(m) != 1:
            raise RuntimeError(f'piloto: {prefix}/{method} no identifica exactamente una fila ({len(m)})')
        chosen.append(m[0])
    # una con cabeceras a/ b/ y una aplicable (control), elegidas por regla y no a mano
    for r in inv:
        t = patch_file_of(r).read_bytes().decode('utf-8', 'replace')
        if prefix_group(*parse_headers(t)[:2])[0] == 'todo_a/' and r not in chosen:
            chosen.append(r)
            break
    for r in app:
        if r['status'] == 'resolved' and r not in chosen:
            chosen.append(r)
            break
    return chosen


def analyze(row, tasks):
    raw = patch_file_of(row).read_bytes()
    text = raw.decode('utf-8', errors='replace')
    minus, plus, git_names = parse_headers(text)
    group, nat = prefix_group(minus, plus)
    lf, anomalies = normalize_patch(raw)
    tk = tasks[row['task_id']]
    return dict(row=row, task_id=row['task_id'], method=row['retrieval_method'], status=row['status'],
                orig_detail=row.get('detail'), raw=raw, lf=lf, lf_anomalies=anomalies, group=group, natural_p=nat,
                targets=candidate_targets(minus + plus + git_names), base_commit=tk['base_commit'],
                repo_dir=tk['repo'].replace('/', '__'),
                no_diff_original=('No valid patches' in (row.get('detail') or '')),
                path=patch_file_of(row))


class Reconstructor:
    def __init__(self, git):
        self.git = git
        self.cache = {}

    def blob_info(self, repo_dir, commit, path):
        key = (repo_dir, commit, path)
        if key in self.cache:
            return self.cache[key]
        repo = REPOS / repo_dir
        rc, out, _ = self.git.run('ls-tree', commit, '--', path, repo=repo)
        info = None
        if rc == 0 and out.strip():
            head, _, _ = dec(out).partition('\t')
            parts = head.split()
            if len(parts) == 3:
                mode, typ, _sha = parts
                if typ == 'blob' and mode in ('100644', '100755'):
                    rc2, blob, _ = self.git.run('cat-file', 'blob', f'{commit}:{path}', repo=repo)
                    rc3, attrs_out, _ = self.git.run('check-attr', '--source', commit, 'text', 'eol', '--', path, repo=repo)
                    attrs = {}
                    for line in dec(attrs_out).splitlines():
                        bits = line.rsplit(': ', 2)
                        if len(bits) == 3:
                            attrs[bits[1]] = bits[2].strip()
                    info = {'blob': blob, 'attrs': attrs, 'mode': mode} if rc2 == 0 and rc3 == 0 else {'skip': 'lectura_fallida'}
                else:
                    info = {'skip': 'enlace_simbolico_o_submodulo' if mode in ('120000', '160000') else f'tipo_{typ}'}
        self.cache[key] = info
        return info

    def build(self, ana, tree_eol, tmp_root):
        """Crea el arbol temporal. Devuelve (ruta, resumen, motivo_no_evaluable | None)."""
        root = pathlib.Path(tempfile.mkdtemp(prefix='t_', dir=tmp_root))
        files, missing, skipped, lowered = [], [], [], {}
        reason = None
        for t in ana['targets']:
            bi = self.blob_info(ana['repo_dir'], ana['base_commit'], t)
            if bi is None:
                missing.append(t)
                continue
            if 'skip' in bi:
                skipped.append({'path': t, 'motivo': bi['skip']})
                continue
            conv = smudge_crlf_tree if tree_eol == 'CRLF' else smudge_lf_tree
            data, why = conv(bi['blob'], bi['attrs'])
            if not roundtrip_ok(bi['blob'], data):
                reason = reason or f'ida_y_vuelta_falla:{t}'
            dest = root / t
            if len(str(dest)) > MAX_PATH_LEN:
                reason = reason or f'ruta_demasiado_larga:{t}'
                continue
            low = t.lower()
            if low in lowered and lowered[low] != t:
                reason = reason or f'colision_mayusculas:{t}|{lowered[low]}'
                continue
            lowered[low] = t
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            files.append({'path': t, 'attrs': bi['attrs'], 'conversion': why, 'sha256_blob': sha256_bytes(bi['blob']),
                          'sha256_escrito': sha256_bytes(data)})
        return root, {'ficheros': files, 'ausentes_en_commit': missing, 'omitidos': skipped}, reason


# ----------------------------------------------------------------------------------------------------------------------
# ejecucion de celdas
# ----------------------------------------------------------------------------------------------------------------------
def run_cell(git, ana, tree, patch_path, p, autocrlf, timeout=60):
    t0 = time.time()
    try:
        rc, out, err = git.run('apply', '--check', f'-p{p}', str(patch_path), cwd=tree,
                               config={'core.autocrlf': autocrlf}, isolated=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'rc': -9, 'mensaje': 'timeout', 'categoria': 'otro', 'ms': int((time.time() - t0) * 1000)}
    msg = (dec(err).strip() or dec(out).strip()) if rc != 0 else ''
    if rc != 0 and not msg:
        msg = 'git apply --check failed'
    return {'rc': rc, 'mensaje': msg, 'categoria': categorize(rc, msg), 'ms': int((time.time() - t0) * 1000)}


def cell_row(ana, matrix, patch_eol, tree_eol, p, autocrlf, res, recon, not_eval):
    return {
        'matriz': matrix, 'task_id': ana['task_id'], 'estrategia': ana['method'], 'estado_original': ana['status'],
        'grupo_prefijo': ana['group'], 'p_natural': ana['natural_p'], 'ambiguo_ab': ana.get('ambiguo_ab', False),
        'sin_diff_original': ana['no_diff_original'],
        'parche_eol': patch_eol, 'arbol_eol': tree_eol, 'p': p, 'autocrlf': autocrlf,
        'es_celda_natural': (ana['natural_p'] == p) if ana['natural_p'] is not None else None,
        'es_linea_base': (patch_eol, tree_eol, p) == BASELINE and matrix == 'principal',
        'parche_usado': 'original' if patch_eol == 'CRLF' else 'normalizado_LF(copia_temporal)',
        'no_evaluable': not_eval,
        'aplica': (res['rc'] == 0) if res else None,
        'categoria': 'no_evaluable' if not_eval else res['categoria'],
        'git_rc': res['rc'] if res else None, 'git_mensaje': res['mensaje'] if res else None,
        'ms': res['ms'] if res else None,
        'reconstruccion': recon,
    }


def expected_baseline(ana):
    """La linea base se compara con el RESULTADO ORIGINAL DE `git apply --check` (no con el estado final del evaluador):
    un parche con estado distinto de invalid_patch paso esa comprobacion; uno invalid_patch la fallo con `detail`."""
    return (ana['status'] != 'invalid_patch'), (None if ana['status'] != 'invalid_patch' else ana['orig_detail'])


def compare_baseline(ana, row):
    exp_ok, exp_msg = expected_baseline(ana)
    if row['no_evaluable']:
        return {'tipo': 'no_evaluable', 'esperado_aplica': exp_ok, 'obtenido': row['reconstruccion'].get('motivo_no_evaluable')}
    if row['aplica'] != exp_ok:
        return {'tipo': 'resultado_distinto', 'esperado_aplica': exp_ok, 'obtenido_aplica': row['aplica'],
                'mensaje_esperado': exp_msg, 'mensaje_obtenido': row['git_mensaje']}
    if not exp_ok and norm_msg(exp_msg) != norm_msg(row['git_mensaje']):
        return {'tipo': 'mensaje_distinto', 'mensaje_esperado': exp_msg, 'mensaje_obtenido': row['git_mensaje']}
    return None


def snapshot(rows, repo_dirs, git):
    snap = {'patches': {r['patch_path']: sha256_file(patch_file_of(r)) for r in rows},
            'results_jsonl': sha256_file(RESULTS), 'final_tasks_csv': sha256_file(TASKS_CSV), 'repos': {}}
    for rd in sorted(repo_dirs):
        repo = REPOS / rd
        rc, out, _ = git.run('rev-parse', 'HEAD', repo=repo)
        idx = repo / '.git' / 'index'
        snap['repos'][rd] = {'HEAD': dec(out).strip() if rc == 0 else None,
                             'index_sha256': sha256_file(idx) if idx.is_file() else None}
    return snap


# ----------------------------------------------------------------------------------------------------------------------
# principal
# ----------------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', action='store_true', help='ejecuta las comprobaciones (sin esta opcion solo muestra el plan)')
    ap.add_argument('--pilot', action='store_true', help='solo ~7 parches representativos')
    ap.add_argument('--only-baseline', action='store_true', help='solo la celda de linea base')
    ap.add_argument('--no-robustness', action='store_true', help='omite la replica con core.autocrlf=false')
    ap.add_argument('--tmp-root', default=None, help='directorio base para temporales (por defecto el del sistema)')
    args = ap.parse_args()

    rows_all, tasks = load_rows()
    selected = select_rows(rows_all, args)
    anas = [analyze(r, tasks) for r in selected]
    n_cells_main = 1 if args.only_baseline else len(MAIN_CELLS)
    n_rob = 0 if (args.only_baseline or args.no_robustness) else len(ROBUST_CELLS)
    print(f'eol_prefix_matrix v{VERSION} | raiz: {ROOT}')
    print(f'parches seleccionados: {len(anas)} ({"piloto" if args.pilot else "completo"}) | celdas principales por parche: '
          f'{n_cells_main} | celdas de robustez (autocrlf=false): {n_rob}')
    print('grupos de prefijo:', dict(Counter(a['group'] for a in anas)))
    print('estados originales:', dict(Counter(a['status'] for a in anas)))
    print('sin diff (original):', sum(a['no_diff_original'] for a in anas))
    print('parches no normalizables a LF:', [(a['task_id'][:30], a['method'], a['lf_anomalies']) for a in anas if a['lf'] is None])
    if args.pilot:
        for a in anas:
            print('  piloto:', a['task_id'][:60], a['method'], a['status'], a['group'])
    if not args.run:
        print('\nMODO PLAN: no se ha ejecutado ninguna comprobacion. Use --run para ejecutar.')
        return 0

    # --- preparacion -----------------------------------------------------------------------------------------------
    out_dir = OUT_BASE / ('eol_prefix_matrix_' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + ('_piloto' if args.pilot else ''))
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=False, exist_ok=False)              # nunca se reutiliza un directorio
    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix='eolm_', dir=args.tmp_root))
    atexit.register(shutil.rmtree, tmp_root, True)
    git = Git(tmp_root)
    log_f = open(out_dir / 'run.log', 'x', encoding='utf-8')

    def log(msg):
        print(msg)
        log_f.write(msg + '\n')
        log_f.flush()

    ver_txt, ver = git_version()
    if ver < GIT_MIN_VERSION:
        log(f'ERROR: se requiere git >= {GIT_MIN_VERSION}; hay {ver_txt}')
        return 4
    rc, _, _ = git.run('rev-parse', '--git-dir', cwd=tmp_root, use_ceiling=False)   # sin techo: detecta un repo ascendente
    if rc == 0:
        log('ERROR: el directorio temporal esta dentro de un repositorio git; use --tmp-root')
        return 4
    for a in anas:                                              # los commits deben existir antes de empezar
        rc, _, _ = git.run('cat-file', '-e', f"{a['base_commit']}^{{commit}}", repo=REPOS / a['repo_dir'])
        if rc != 0:
            log(f"ERROR: commit {a['base_commit']} ausente en repos/{a['repo_dir']}")
            return 4
    cfg_real = config_snapshot(git, tmp_root, isolated=False)      # sistema y usuario reales (no usados), vistos desde el temporal
    cfg_iso = config_snapshot(git, tmp_root, isolated=True)        # lo que ve git apply en las comprobaciones
    eff_main = effective_autocrlf(git, tmp_root, 'true')
    eff_rob = effective_autocrlf(git, tmp_root, 'false')
    leaks = [k for k in CFG_FORBIDDEN_IN_MANIFEST if k in json.dumps([cfg_real, cfg_iso])]
    if cfg_real is None or cfg_iso is None or eff_main != 'true' or eff_rob != 'false' or leaks:
        log(f'ERROR de configuracion de git: autocrlf efectivo principal={eff_main!r} robustez={eff_rob!r}; '
            f'datos no deseados en el registro={leaks}')
        return 4
    repo_dirs = {a['repo_dir'] for a in anas}
    before = snapshot(rows_all, repo_dirs, git)
    manifest = {'script': 'eol_prefix_matrix.py', 'version': VERSION, 'args': vars(args), 'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'python': sys.version, 'plataforma': platform.platform(), 'git': ver_txt,
                'manifest_esquema': 2,
                'nota_esquema': 'Esquema 2 (2026-11-12). Los manifiestos del piloto y de la linea base de 150 (esquema 1) listaban por '
                                'error el .git/config del proyecto en config_git_aislada(usada); solo era un fallo de registro: '
                                'git apply se ejecuta en un directorio temporal fuera de cualquier repositorio.',
                'config_git_sistema_y_usuario_reales(no usada)': cfg_real,
                'config_git_aislada(visible_para_git_apply)': cfg_iso,
                'config_efectiva_matriz_principal': {'core.autocrlf': eff_main, 'como': '-c core.autocrlf=true en cada git apply',
                                                     'celdas': 'matriz principal (arboles CRLF y LF)'},
                'config_efectiva_replica_robustez': {'core.autocrlf': eff_rob, 'como': '-c core.autocrlf=false en cada git apply',
                                                     'celdas': 'replica de robustez (solo arboles LF)'},
                'diferencias_con_el_entorno_original': DIFFERENCES_WITH_ORIGINAL,
                'interpretacion': ['Los resultados originales no se modifican.',
                                   'Normalizar un parche no demuestra que el modelo resuelva la tarea.',
                                   'Que git apply --check funcione en la reconstruccion no garantiza que el evaluador oficial lo acepte.',
                                   'LF sobre LF es una prueba de sensibilidad, no una reproduccion demostrada de Linux/Docker.'],
                'seleccion': [{'task_id': a['task_id'], 'estrategia': a['method']} for a in anas],
                'integridad_antes': before}
    rec = Reconstructor(git)
    cells_f = open(out_dir / 'cells.jsonl', 'x', encoding='utf-8')                               # matriz principal
    rob_f = open(out_dir / 'cells_robustez_autocrlf_false.jsonl', 'x', encoding='utf-8')        # replica, separada
    all_rows = []

    def emit(row):
        all_rows.append(row)
        (cells_f if row['matriz'] == 'principal' else rob_f).write(json.dumps(row, ensure_ascii=False) + '\n')
        cells_f.flush()
        rob_f.flush()

    def prepare_patch_files(ana):
        pdir = pathlib.Path(tempfile.mkdtemp(prefix='p_', dir=tmp_root))
        orig = ana['path']                                      # el parche original se pasa por su ruta, en solo lectura
        lf_path = None
        if ana['lf'] is not None:
            lf_path = pdir / 'patch_LF.diff'
            lf_path.write_bytes(ana['lf'])
        return orig, lf_path, pdir

    def execute(ana, tree_eol, cells, matrix, autocrlf):
        root, recon, reason = rec.build(ana, tree_eol, tmp_root)
        if tree_eol == 'CRLF':       # la ambiguedad a/ b/ se detecta una sola vez, con los candidatos -p0
            ana['ambiguo_ab'] = ana['natural_p'] == 1 and any(f['path'].startswith(('a/', 'b/')) for f in recon['ficheros'])
        digest_before = tree_digest(root)
        orig, lf_path, pdir = prepare_patch_files(ana)
        for pe, te, p in cells:
            not_eval, res, rc_extra = None, None, dict(recon)
            if reason:
                not_eval = reason
            elif pe == 'LF' and lf_path is None:
                not_eval = 'parche_no_normalizable:' + ','.join(ana['lf_anomalies'])
            if not not_eval:
                res = run_cell(git, ana, root, orig if pe == 'CRLF' else lf_path, p, autocrlf)
            rc_extra['motivo_no_evaluable'] = not_eval
            emit(cell_row(ana, matrix, pe, te, p, autocrlf, res, rc_extra, bool(not_eval)))
        if tree_digest(root) != digest_before:
            raise RuntimeError(f'un arbol temporal cambio durante la comprobacion: {ana["task_id"]}')
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(pdir, ignore_errors=True)

    # --- fase 1: linea base (puerta) ---------------------------------------------------------------------------------
    log(f'FASE 1: linea base {BASELINE} sobre {len(anas)} parches')
    discrepancies = []
    for ana in anas:
        execute(ana, 'CRLF', [BASELINE], 'principal', 'true')
        d = compare_baseline(ana, all_rows[-1])
        if d:
            discrepancies.append({'task_id': ana['task_id'], 'estrategia': ana['method'], **d})
    controls = {'control_1_linea_base': {'parches': len(anas), 'coinciden': len(anas) - len(discrepancies),
                                         'discrepancias': discrepancies,
                                         'criterio': 'resultado y mensaje de `git apply --check` originales, no el estado final del evaluador'}}
    if discrepancies:
        log(f'LINEA BASE NO REPRODUCE: {len(discrepancies)} discrepancias de {len(anas)}. Me detengo.')
        (out_dir / 'baseline_discrepancias.json').write_text(json.dumps(discrepancies, ensure_ascii=False, indent=1), encoding='utf-8')
        code = 2
    elif args.only_baseline:
        log('Solo linea base: sin discrepancias.')
        code = 0
    else:
        # --- fase 2: resto de celdas ------------------------------------------------------------------------------
        log('FASE 2: resto de celdas de la matriz principal (autocrlf=true)')
        for ana in anas:
            execute(ana, 'CRLF', [c for c in MAIN_CELLS if c[1] == 'CRLF' and c != BASELINE], 'principal', 'true')
            execute(ana, 'LF', [c for c in MAIN_CELLS if c[1] == 'LF'], 'principal', 'true')
            if not args.no_robustness:
                execute(ana, 'LF', ROBUST_CELLS, 'robustez_autocrlf_false', 'false')
        code = 0

    # --- controles 2-4 y resumenes ---------------------------------------------------------------------------------
    main_rows = [r for r in all_rows if r['matriz'] == 'principal']
    base = {(r['task_id'], r['estrategia']): r for r in main_rows if r['es_linea_base']}
    controls['control_2_aplicables_pasan_en_linea_base'] = {
        'n': sum(1 for a in anas if a['status'] != 'invalid_patch'),
        'fallan': [k for k, r in base.items() if r['estado_original'] != 'invalid_patch' and not r['aplica']]}
    if not args.only_baseline and code == 0:
        controls['control_3_sin_diff_fallan_en_todas_las_celdas'] = {
            'violaciones': [(r['task_id'], r['estrategia'], r['parche_eol'], r['arbol_eol'], r['p']) for r in all_rows
                            if r['sin_diff_original'] and r['aplica']]}
        crossed = [r for r in main_rows if r['es_celda_natural'] is False and not r['no_evaluable']]
        controls['control_4_celdas_cruzadas_de_p'] = {
            'n': len(crossed), 'aplican_(anomalia)': [(r['task_id'], r['estrategia'], r['parche_eol'], r['arbol_eol'], r['p']) for r in crossed if r['aplica']],
            'categorias': dict(Counter(r['categoria'] for r in crossed))}
    (out_dir / 'controls.json').write_text(json.dumps(controls, ensure_ascii=False, indent=1), encoding='utf-8')

    def write_summaries(rows, suffix):
        """Resumen por celda y transiciones desde la linea base. La replica de robustez va en ficheros aparte."""
        cats = sorted({r['categoria'] for r in rows})
        with open(out_dir / f'summary_by_cell{suffix}.csv', 'x', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['matriz', 'parche_eol', 'arbol_eol', 'p', 'autocrlf', 'poblacion', 'n', 'aplican', *cats])
            keys = sorted({(r['matriz'], r['parche_eol'], r['arbol_eol'], r['p'], r['autocrlf']) for r in rows})
            for k in keys:
                cell = [r for r in rows if (r['matriz'], r['parche_eol'], r['arbol_eol'], r['p'], r['autocrlf']) == k]
                pops = {'invalid_originales': [r for r in cell if r['estado_original'] == 'invalid_patch'],
                        'invalid_p_natural': [r for r in cell if r['estado_original'] == 'invalid_patch' and r['es_celda_natural'] and not r['ambiguo_ab']],
                        'aplicables_originales(control)': [r for r in cell if r['estado_original'] != 'invalid_patch']}
                for name, sub in pops.items():
                    c = Counter(r['categoria'] for r in sub)
                    w.writerow([*k, name, len(sub), c.get('aplica', 0), *[c.get(x, 0) for x in cats]])
        with open(out_dir / f'transitions_vs_baseline{suffix}.csv', 'x', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['matriz', 'parche_eol', 'arbol_eol', 'p', 'autocrlf', 'poblacion', 'desde_linea_base', 'hasta_esta_celda', 'n'])
            trans = Counter()
            for r in rows:
                if r['es_linea_base'] or r['estado_original'] != 'invalid_patch':
                    continue
                b = base.get((r['task_id'], r['estrategia']))
                if not b:
                    continue
                pop = 'p_natural' if (r['es_celda_natural'] and not r['ambiguo_ab']) else 'otras'
                trans[(r['matriz'], r['parche_eol'], r['arbol_eol'], r['p'], r['autocrlf'], pop, b['categoria'], r['categoria'])] += 1
            for k, n in sorted(trans.items()):
                w.writerow([*k, n])

    write_summaries(main_rows, '')                                            # matriz principal (autocrlf=true)
    rob_rows = [r for r in all_rows if r['matriz'] != 'principal']
    if rob_rows:
        write_summaries(rob_rows, '_robustez_autocrlf_false')                 # replica, claramente separada

    # --- integridad despues -------------------------------------------------------------------------------------
    after = snapshot(rows_all, repo_dirs, git)
    unchanged = after == before
    manifest.update({'integridad_despues': after, 'integridad_sin_cambios': unchanged, 'codigo_salida': code if unchanged else 3,
                     'controles': controls})
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    log(f'integridad (150 parches, jsonl, csv, HEAD e indices de {len(repo_dirs)} repos): {"SIN CAMBIOS" if unchanged else "CAMBIOS DETECTADOS"}')
    log(f'salida: {out_dir}')
    cells_f.close()
    rob_f.close()
    log_f.close()
    return code if unchanged else 3


if __name__ == '__main__':
    sys.exit(main())
