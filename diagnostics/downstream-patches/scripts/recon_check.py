"""Diagnostico de solo lectura: git apply --check -p0 sobre reconstruccion temporal.
No modifica el proyecto ni los repos. Reconstruye en un directorio temporal y escribe solo en output/."""
import atexit, csv, json, pathlib, re, shutil, subprocess, sys, tempfile
from collections import Counter

# Raiz del proyecto: primer directorio ascendente que contiene results/final_tasks.csv
PROJ = next(p for p in pathlib.Path(__file__).resolve().parents if (p / 'results' / 'final_tasks.csv').exists())
DATA = PROJ / 'diagnostics' / 'downstream-patches' / 'data'      # datos de diagnostico originales (solo lectura)
OUT = PROJ / 'diagnostics' / 'downstream-patches' / 'output'     # salidas de nuevas ejecuciones (no sobrescribe DATA)
TMP = pathlib.Path(tempfile.mkdtemp(prefix='recon_'))        # reconstrucciones temporales, fuera del proyecto
atexit.register(shutil.rmtree, TMP, True)


def git(*a, cwd=None, binary=False):
    return subprocess.run(['git', *a], capture_output=True, cwd=cwd,
                          **({} if binary else dict(text=True, encoding='utf-8', errors='replace')))


rows = [json.loads(l) for l in open(PROJ / 'results/downstream_results_final.jsonl', encoding='utf-8-sig')]
tasks = {r['original_inst_id']: r for r in csv.DictReader(open(PROJ / 'results/final_tasks.csv', encoding='utf-8-sig'))}

sel = []
for r in rows:
    if r['status'] != 'invalid_patch':
        continue
    t = pathlib.Path(PROJ / r['patch_path']).read_text(encoding='utf-8-sig')
    hs = re.findall(r'^--- (\S+)', t, re.M)
    if hs and not any(h.startswith('a/') for h in hs):
        sel.append(r)
assert len(sel) == 94


def safe(p):
    pp = pathlib.PurePosixPath(p)
    return not pp.is_absolute() and '..' not in pp.parts and p != '/dev/null'


def reconstruct(r, tk, repo):
    """Devuelve (dir, info). Escribe los ficheros 'antiguos' del patch desde base_commit."""
    d = TMP / (r['task_id'][:40] + '_' + r['retrieval_method'])
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    t = (PROJ / r['patch_path']).read_text(encoding='utf-8-sig')
    olds = [m for m in re.findall(r'^--- (\S+)', t, re.M)]
    info = {'files': [], 'missing_in_commit': [], 'unsafe': []}
    for p in olds:
        if p == '/dev/null':
            continue
        if not safe(p):
            info['unsafe'].append(p); continue
        blob = git('-C', str(repo), 'show', f"{tk['base_commit']}:{p}", binary=True)
        if blob.returncode != 0:
            info['missing_in_commit'].append(p); continue   # fichero inexistente en el commit (o nuevo)
        out = d / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob.stdout)
        info['files'].append(p)
    return d, info


def check(r, d):
    p = git('apply', '--check', '-p0', str((PROJ / r['patch_path']).resolve()), cwd=str(d))
    return p.returncode == 0, (p.stderr.strip() or p.stdout.strip())


def norm(e):
    return re.sub(r'\s+', ' ', e)


results = []
for r in sel:
    tk = tasks[r['task_id']]
    repo = PROJ / 'repos' / tk['repo'].replace('/', '__')
    head = git('-C', str(repo), 'rev-parse', 'HEAD').stdout.strip()
    in_repo = (head == tk['base_commit'])
    res = {'task': r['task_id'], 'method': r['retrieval_method'], 'in_repo_head': in_repo,
           'orig_error': r['detail']}
    if in_repo:
        ok, err = check(r, repo)          # referencia: repo real (solo lectura)
        res['repo_ok'], res['repo_err'] = ok, err
    d, info = reconstruct(r, tk, repo)
    ok, err = check(r, d)
    res.update(recon_ok=ok, recon_err=err, recon_info=info)
    results.append(res)

# --- validacion de equivalencia sobre los casos con repo real ---
val = [x for x in results if x['in_repo_head']]
same = sum(1 for x in val if x['repo_ok'] == x['recon_ok'] and norm(x['repo_err']) == norm(x['recon_err']))
print(f'VALIDACION: {same}/{len(val)} casos con repo real dan el mismo resultado y el mismo mensaje en la reconstruccion')
for x in val:
    if not (x['repo_ok'] == x['recon_ok'] and norm(x['repo_err']) == norm(x['recon_err'])):
        print('  DIFERENCIA', x['task'][:40], x['method'], '| repo:', x['repo_err'][:100], '| recon:', x['recon_err'][:100])


def cat(x):
    if x['recon_ok']:
        return 'PASA'
    e = x['recon_err']
    for k, lab in [('corrupt patch', 'corrupt patch'), ('patch failed', 'contexto no coincide (patch failed)'),
                   ('without header', 'fragment sin header'), ('No valid patches', 'sin diff valido'),
                   ('No such file', 'fichero inexistente'), ('does not exist in index', 'fichero inexistente'),
                   ('already exists', 'ya existe')]:
        if k in e:
            return lab
    return 'otro: ' + e.splitlines()[0][:70] if e else 'otro'


pend = [x for x in results if not x['in_repo_head']]
for name, grp in [('55 PENDIENTES (reconstruccion)', pend), ('39 YA EJECUTADOS (reconstruccion)', val), ('94 CONSOLIDADOS', results)]:
    print(f'\n== {name}: {len(grp)}')
    for k, v in Counter(cat(x) for x in grp).most_common():
        print(f'  {v:3d}  {k}')
print('\nficheros no encontrados en el commit (en los 94):',
      sum(1 for x in results if x['recon_info']['missing_in_commit']))
print('rutas inseguras descartadas:', sum(len(x['recon_info']['unsafe']) for x in results))
OUT.mkdir(parents=True, exist_ok=True)
json.dump(results, open(OUT / 'p0_reconstruccion_94.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
