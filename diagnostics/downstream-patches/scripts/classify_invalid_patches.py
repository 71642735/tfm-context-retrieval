"""Clasificacion de los 150 parches downstream (solo lectura).

Reproduce los analisis que se hicieron inicialmente en linea:
  - estado original por estrategia,
  - causa de cada invalid_patch segun el stderr de `git apply --check` (campo `detail`),
  - prefijos de ruta (a/ b/) de las cabeceras `---`,
  - finales de linea (CRLF/LF) de cada patch.diff.

Ejecutar desde la raiz del proyecto:
    python -I diagnostics/downstream-patches/scripts/classify_invalid_patches.py

Solo LEE results/downstream_results_final.jsonl y logs/downstream/**/patch.diff.
Escribe unicamente diagnostics/downstream-patches/data/invalid_patches_classification.csv
"""
import csv
import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path.cwd()
RESULTS = ROOT / 'results' / 'downstream_results_final.jsonl'
OUT = ROOT / 'diagnostics' / 'downstream-patches' / 'data' / 'invalid_patches_classification.csv'

rows = [json.loads(l) for l in open(RESULTS, encoding='utf-8-sig')]


def cause(detail):
    d = detail or ''
    for key, label in [('No valid patches', 'sin_diff_valido'), ('corrupt patch', 'corrupt_patch'),
                       ('without header', 'fragmento_sin_cabecera'), ('No such file', 'fichero_inexistente'),
                       ('patch failed', 'contexto_no_coincide')]:
        if key in d:
            return label
    return 'otro'


def prefix_kind(text):
    hs = re.findall(r'^--- (\S+)', text, re.M)
    if not hs:
        return 'sin_cabeceras'
    if all(h.startswith('a/') or h == '/dev/null' for h in hs):
        return 'todo_a/'
    if not any(h.startswith('a/') for h in hs):
        return 'sin_prefijo'
    return 'mixto'


def eol_kind(raw):
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    return 'CRLF' if crlf and not lf else ('mixto' if crlf else 'LF')


out = []
for r in rows:
    raw = pathlib.Path(r['patch_path']).read_bytes()
    text = raw.decode('utf-8-sig', errors='replace')
    out.append(dict(task_id=r['task_id'], method=r['retrieval_method'], status=r['status'],
                    cause=cause(r['detail']) if r['status'] == 'invalid_patch' else '',
                    prefix=prefix_kind(text), eol=eol_kind(raw),
                    git_error=(r['detail'] or '').replace('\r', '').replace('\n', ' | ')))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

print('Filas:', len(out))
print('\n1) Estado original:', dict(Counter(o['status'] for o in out)))
print('   por estrategia (invalid_patch):', dict(Counter(o['method'] for o in out if o['status'] == 'invalid_patch')))
print('\n2) Causa de los invalid_patch:')
for k, v in Counter(o['cause'] for o in out if o['status'] == 'invalid_patch').most_common():
    print(f'   {v:3d}  {k}')
print('\n3) Prefijo de ruta por estado:')
for k, v in sorted(Counter((o['status'], o['prefix']) for o in out).items()):
    print('  ', k, v)
print('\n4) invalid_patch "fichero_inexistente" por prefijo:',
      dict(Counter(o['prefix'] for o in out if o['cause'] == 'fichero_inexistente')))
print('\n5) Finales de linea de patch.diff:', dict(Counter(o['eol'] for o in out)))
print('\nCSV escrito en', OUT)
