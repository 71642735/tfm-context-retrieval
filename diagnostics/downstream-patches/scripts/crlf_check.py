"""Diagnostico LF vs CRLF sobre los 39 casos con repo real en su base_commit.
Solo lectura sobre el proyecto/repos. Reconstruye en un directorio temporal y escribe solo en output/."""
import atexit, csv, json, pathlib, re, shutil, subprocess, tempfile
from collections import Counter

# Raiz del proyecto: primer directorio ascendente que contiene results/final_tasks.csv
PROJ = next(p for p in pathlib.Path(__file__).resolve().parents if (p / 'results' / 'final_tasks.csv').exists())
DATA = PROJ / 'diagnostics' / 'downstream-patches' / 'data'      # datos de diagnostico originales (solo lectura)
OUT = PROJ / 'diagnostics' / 'downstream-patches' / 'output'     # salidas de nuevas ejecuciones (no sobrescribe DATA)
TMP = pathlib.Path(tempfile.mkdtemp(prefix='recon_crlf_'))        # reconstrucciones temporales, fuera del proyecto
atexit.register(shutil.rmtree, TMP, True)


def git(*a, cwd=None, binary=False):
    return subprocess.run(['git', '--no-optional-locks', *a], capture_output=True, cwd=cwd,
                          **({} if binary else dict(text=True, encoding='utf-8', errors='replace')))


prev = json.load(open(DATA / 'p0_reconstruccion_94.json', encoding='utf-8'))
cases = [x for x in prev if x['in_repo_head']]
assert len(cases) == 39
tasks = {r['original_inst_id']: r for r in csv.DictReader(open(PROJ / 'results/final_tasks.csv', encoding='utf-8-sig'))}
rows = {(r['task_id'], r['retrieval_method']): r for r in map(json.loads, open(PROJ / 'results/downstream_results_final.jsonl', encoding='utf-8-sig'))}

# --- 1. configuracion de EOL ---
print('core.autocrlf (origen):', git('config', '--show-origin', '--get-all', 'core.autocrlf').stdout.strip().replace('\n', ' | '))
print('core.eol:', git('config', '--get', 'core.eol').stdout.strip() or '(sin definir)')
print('core.safecrlf:', git('config', '--get', 'core.safecrlf').stdout.strip() or '(sin definir)')
print('apply.whitespace:', git('config', '--get', 'apply.whitespace').stdout.strip() or '(sin definir)')
print('apply.ignorewhitespace:', git('config', '--get', 'apply.ignorewhitespace').stdout.strip() or '(sin definir)')
ga = Counter()
for repo in sorted({tasks[x['task']]['repo'].replace('/', '__') for x in cases}):
    rp = PROJ / 'repos' / repo
    in_wt = (rp / '.gitattributes').exists()
    cfg_repo = git('-C', str(rp), 'config', '--local', '--get', 'core.autocrlf').stdout.strip()
    ga[repo] = (in_wt, cfg_repo)
print('\n.gitattributes en arbol de trabajo / autocrlf local por repo:')
for k, v in ga.items():
    print(f'  {k:32} .gitattributes={v[0]}  autocrlf_local={v[1] or "(sin definir)"}')


def to_crlf(b):
    if b'\0' in b:
        return b
    return re.sub(rb'(?<!\r)\n', b'\r\n', b)


def build(x, variant):
    tk = tasks[x['task']]
    repo = PROJ / 'repos' / tk['repo'].replace('/', '__')
    d = TMP / variant / (x['task'][:40] + '_' + x['method'])
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    info = []
    for p in x['recon_info']['files']:
        blob = git('-C', str(repo), 'show', f"{tk['base_commit']}:{p}", binary=True).stdout
        wt = (repo / p).read_bytes()
        if variant == 'LF':
            data = blob
        elif variant == 'CRLF_regla':          # regla: convertir a CRLF como haria autocrlf=true al hacer checkout
            data = to_crlf(blob)
        else:                                   # 'WT_copia': bytes exactos del arbol de trabajo (control)
            data = wt
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_bytes(data)
        info.append((p, blob == wt, to_crlf(blob) == wt))
    return d, info


def run(x, d):
    patch = (PROJ / rows[(x['task'], x['method'])]['patch_path']).resolve()
    p = git('apply', '--check', '-p0', str(patch), cwd=str(d))
    return p.returncode == 0, (p.stderr.strip() or p.stdout.strip())


norm = lambda e: re.sub(r'\s+', ' ', e)
out = []
for x in cases:
    tk = tasks[x['task']]
    repo = PROJ / 'repos' / tk['repo'].replace('/', '__')
    patch = (PROJ / rows[(x['task'], x['method'])]['patch_path']).resolve()
    p = git('-C', str(repo), 'apply', '--check', '-p0', str(patch))
    ref = (p.returncode == 0, (p.stderr.strip() or p.stdout.strip()))
    rec = {'task': x['task'], 'method': x['method'], 'ref_ok': ref[0], 'ref_err': ref[1]}
    for v in ('LF', 'CRLF_regla', 'WT_copia'):
        d, info = build(x, v)
        ok, err = run(x, d)
        rec[v] = {'ok': ok, 'err': err, 'match_status': ok == ref[0], 'match_exact': ok == ref[0] and norm(err) == norm(ref[1])}
        if v == 'LF':
            rec['files_info'] = info   # (ruta, blob==WT, CRLF(blob)==WT)
    out.append(rec)

print('\nREPRODUCCION DE LOS 39 RESULTADOS DEL REPO REAL')
print(f'{"variante":12} {"mismo estado":>13} {"mismo estado+mensaje":>21} {"distintos":>10}')
for v in ('LF', 'CRLF_regla', 'WT_copia'):
    s = sum(r[v]['match_status'] for r in out); e = sum(r[v]['match_exact'] for r in out)
    print(f'{v:12} {s:>10}/39 {e:>18}/39 {39 - e:>10}')

nf = sum(len(r['files_info']) for r in out)
print(f'\nFicheros reconstruidos: {nf}')
print('  blob == arbol de trabajo (sin conversion):', sum(i[1] for r in out for i in r['files_info']))
print('  CRLF(blob) == arbol de trabajo (regla autocrlf):', sum(i[2] for r in out for i in r['files_info']))
print('  ninguno de los dos:', sum((not i[1]) and (not i[2]) for r in out for i in r['files_info']))

print('\nCasos donde CRLF_regla NO reproduce exactamente:')
for r in out:
    if not r['CRLF_regla']['match_exact']:
        print(f"  {r['task'][:42]} {r['method']}\n    repo : ok={r['ref_ok']} {norm(r['ref_err'])[:130]}\n    crlf : ok={r['CRLF_regla']['ok']} {norm(r['CRLF_regla']['err'])[:130]}\n    wt   : ok={r['WT_copia']['ok']} {norm(r['WT_copia']['err'])[:130]}")
OUT.mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT / 'crlf_validacion_39.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
