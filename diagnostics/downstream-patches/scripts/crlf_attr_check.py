"""Fase A (validacion 39) y Fase B (55) con reglas EOL del base_commit.
Solo lectura sobre proyecto/repos; reconstruye en un directorio temporal y escribe solo en output/. Sin checkout."""
import atexit, csv, json, pathlib, re, shutil, subprocess, sys, tempfile
from collections import Counter

# Raiz del proyecto: primer directorio ascendente que contiene results/final_tasks.csv
PROJ = next(p for p in pathlib.Path(__file__).resolve().parents if (p / 'results' / 'final_tasks.csv').exists())
DATA = PROJ / 'diagnostics' / 'downstream-patches' / 'data'      # datos de diagnostico originales (solo lectura)
OUT = PROJ / 'diagnostics' / 'downstream-patches' / 'output'     # salidas de nuevas ejecuciones (no sobrescribe DATA)
TMP = pathlib.Path(tempfile.mkdtemp(prefix='recon_attr_'))        # reconstrucciones temporales, fuera del proyecto
atexit.register(shutil.rmtree, TMP, True)


def git(*a, cwd=None, binary=False):
    return subprocess.run(['git', '--no-optional-locks', *a], capture_output=True, cwd=cwd,
                          **({} if binary else dict(text=True, encoding='utf-8', errors='replace')))


print('git', git('--version').stdout.strip())
prev = json.load(open(DATA / 'p0_reconstruccion_94.json', encoding='utf-8'))
tasks = {r['original_inst_id']: r for r in csv.DictReader(open(PROJ / 'results/final_tasks.csv', encoding='utf-8-sig'))}
rows = {(r['task_id'], r['retrieval_method']): r for r in map(json.loads, open(PROJ / 'results/downstream_results_final.jsonl', encoding='utf-8-sig'))}
norm = lambda e: re.sub(r'\s+', ' ', e)


def attrs(repo, commit, path):
    """text/eol segun .gitattributes del propio commit (--source), sin tocar el arbol de trabajo."""
    out = git('-C', str(repo), 'check-attr', '--source', commit, 'text', 'eol', '--', path).stdout
    a = {}
    for line in out.splitlines():
        m = re.match(r'.+: (text|eol): (.*)$', line)
        if m:
            a[m.group(1)] = m.group(2).strip()
    return a


def smudge(blob, a):
    """Reproduce lo que Git deja en el arbol de trabajo con core.autocrlf=true."""
    text, eol = a.get('text', 'unspecified'), a.get('eol', 'unspecified')
    if text in ('unset',) or b'\0' in blob:
        return blob, 'sin conversion (text unset / binario)'
    if eol == 'lf':
        return blob, 'LF (eol=lf)'
    if eol == 'crlf' or text in ('set', 'auto', 'unspecified'):
        if b'\r' in blob and eol != 'crlf':
            return blob, 'sin conversion (el blob ya contiene CR)'
        return re.sub(rb'(?<!\r)\n', b'\r\n', blob), 'CRLF'
    return blob, 'sin conversion'


def build(x, tk, repo, mode):
    d = TMP / (x['task'][:40] + '_' + x['method'])
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    info = {'files': [], 'missing_in_commit': [], 'unsafe': []}
    t = (PROJ / rows[(x['task'], x['method'])]['patch_path']).read_text(encoding='utf-8-sig')
    for p in re.findall(r'^--- (\S+)', t, re.M):
        pp = pathlib.PurePosixPath(p)
        if p == '/dev/null':
            continue
        if pp.is_absolute() or '..' in pp.parts:
            info['unsafe'].append(p); continue
        b = git('-C', str(repo), 'show', f"{tk['base_commit']}:{p}", binary=True)
        if b.returncode != 0:
            info['missing_in_commit'].append(p); continue
        data, why = smudge(b.stdout, attrs(repo, tk['base_commit'], p))
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_bytes(data)
        wt_equal = None
        if mode == 'validar':
            wt_equal = ((repo / p).read_bytes() == data)
        info['files'].append((p, why, wt_equal))
    return d, info


def apply_check(patch, cwd):
    p = git('apply', '--check', '-p0', str(patch), cwd=str(cwd))
    return p.returncode == 0, (p.stderr.strip() or p.stdout.strip())


# ---------------- FASE A ----------------
A = [x for x in prev if x['in_repo_head']]
res = []
for x in A:
    tk = tasks[x['task']]
    repo = PROJ / 'repos' / tk['repo'].replace('/', '__')
    patch = (PROJ / rows[(x['task'], x['method'])]['patch_path']).resolve()
    ref = apply_check(patch, repo)                      # referencia: repo real, solo lectura
    d, info = build(x, tk, repo, 'validar')
    rec = apply_check(patch, d)
    res.append(dict(task=x['task'], method=x['method'], ref_ok=ref[0], ref_err=ref[1], rec_ok=rec[0], rec_err=rec[1], info=info,
                    same_state=ref[0] == rec[0], same_exact=(ref[0] == rec[0] and norm(ref[1]) == norm(rec[1]))))
sa = sum(r['same_state'] for r in res); ea = sum(r['same_exact'] for r in res)
nfiles = sum(len(r['info']['files']) for r in res); eqwt = sum(1 for r in res for f in r['info']['files'] if f[2])
print(f'\nFASE A: mismo estado {sa}/39 | mismo estado y mensaje {ea}/39 | ficheros identicos al arbol de trabajo {eqwt}/{nfiles}')
for r in res:
    if not r['same_exact']:
        print('  DIFERENCIA', r['task'][:42], r['method'], '\n    repo :', r['ref_ok'], norm(r['ref_err'])[:140], '\n    recon:', r['rec_ok'], norm(r['rec_err'])[:140], '\n    ', r['info']['files'])
OUT.mkdir(parents=True, exist_ok=True)
json.dump(res, open(OUT / 'faseA_39.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if ea != 39:
    print('\nFASE A NO REPRODUCE 39/39 -> me detengo; no se ejecuta la fase B.')
    sys.exit(0)

# ---------------- FASE B ----------------
B = [x for x in prev if not x['in_repo_head']]
assert len(B) == 55
resB = []
for x in B:
    tk = tasks[x['task']]
    repo = PROJ / 'repos' / tk['repo'].replace('/', '__')
    patch = (PROJ / rows[(x['task'], x['method'])]['patch_path']).resolve()
    d, info = build(x, tk, repo, 'reconstruir')
    ok, err = apply_check(patch, d)
    resB.append(dict(task=x['task'], method=x['method'], ok=ok, err=err, info=info, orig=rows[(x['task'], x['method'])]['detail']))
json.dump(resB, open(OUT / 'faseB_55.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def cat(ok, e):
    if ok: return 'Pasa con -p0'
    for k, lab in [('corrupt patch', 'Corrupto'), ('patch failed', 'Falla por contexto/lineas'), ('without header', 'Fragmento sin cabecera'),
                   ('No valid patches', 'Sin diff valido'), ('No such file', 'Otro: fichero inexistente'), ('does not exist in index', 'Otro: fichero inexistente')]:
        if k in e: return lab
    return 'Otro: ' + (e.splitlines()[0][:60] if e else '')


cA = Counter(cat(r['rec_ok'], r['rec_err']) for r in res); cB = Counter(cat(r['ok'], r['err']) for r in resB)
labs = sorted(set(cA) | set(cB), key=lambda k: (k != 'Pasa con -p0', k))
print('\nCONSOLIDADO 94 (-p0)')
print(f'{"categoria":34}{"39 (repo real)":>16}{"55 (reconstr.)":>16}{"94":>6}')
for k in labs:
    print(f'{k:34}{cA[k]:>16}{cB[k]:>16}{cA[k] + cB[k]:>6}')
print(f'{"TOTAL":34}{sum(cA.values()):>16}{sum(cB.values()):>16}{94:>6}')
print('\nficheros del parche ausentes en el base_commit (55):', sum(1 for r in resB if r['info']['missing_in_commit']))
print('rutas inseguras descartadas:', sum(len(r['info']['unsafe']) for r in resB))
E = Counter()
for r in resB:
    for f in r['info']['files']: E[f[1]] += 1
print('conversion EOL aplicada a ficheros de los 55:', dict(E))
