"""Analisis descriptivo de una ejecucion de eol_prefix_matrix.py (solo lectura de la salida).

Uso (desde cualquier directorio):
    python -I analyze_eol_prefix_matrix.py <directorio_de_salida>

Lee cells.jsonl, cells_robustez_autocrlf_false.jsonl, controls.json y manifest.json del directorio indicado y escribe
`analisis.md` y `analisis.json` en ese mismo directorio (modo exclusivo 'x': no sobrescribe). No toca el proyecto.

Segundo modo (analisis exploratorio a nivel de fichero, solo lectura):
    python -I analyze_eol_prefix_matrix.py <directorio_con_cells.jsonl> --ficheros-contexto
Para cada parche, compara los ficheros que modifica (cabeceras `---`, tras quitar su `-p` natural) con los ficheros del
contexto recuperado que se dio al modelo (`File:` de logs/downstream/<tarea>/<estrategia>/prompt.txt, versionado).
Escribe `analisis_ficheros_contexto.json` en el directorio indicado (modo exclusivo 'x'). Reproduce el dato "46 de 96" y la
comprobacion "10 de 11". No es a nivel de linea ni frente al gold context.

Tercer modo (viabilidad de un formato de edicion anclado por contenido, solo lectura):
    python -I analyze_eol_prefix_matrix.py <directorio_con_cells.jsonl> --anclaje-contenido
Para cada parche con contexto o corrupt (los 96), los 11 recuperables y los 9 controles, comprueba si el bloque "antiguo" de
cada hunk (contexto + lineas eliminadas) aparece contiguo en el fichero del `base_commit` (leido con `git cat-file`, solo
lectura), ignorando los numeros de linea. Es una cota del tipo de reparacion que haria un formato SEARCH/REPLACE; NO genera ni
aplica parches ni mide resolucion. Escribe `analisis_anclaje_contenido.json` (modo exclusivo 'x').

Cuarto modo (comparacion con la solucion de referencia de ContextBench, solo analisis posterior, offline):
    <python del entorno virtual del proyecto, que tiene `datasets`> -I analyze_eol_prefix_matrix.py <directorio_con_cells.jsonl> --referencia
Usa el dataset local en cache (sin red) para obtener la fuente (Verified/Poly/Pro) y el parche de referencia de cada tarea; comprueba
si cada parche edita el mismo fichero que la referencia y si sus hunks solapan con los de ella. La referencia NO se dio al modelo.
Es un indicador de plausibilidad, no de resolucion. Escribe `analisis_referencia.json` (modo exclusivo 'x').

Que mide: APLICABILIDAD (si `git apply --check` acepta el parche en una reconstruccion temporal). No mide resolucion
funcional ni equivale a la aceptacion del evaluador oficial. Todo es descriptivo; no se extrapola.
"""
import csv
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter, defaultdict

STRAT = {'bm25': 'BM25', 'semantic': 'UniXcoder', 'hybrid': 'RRF'}
MAIN_COMBOS = [('CRLF', 'CRLF'), ('LF', 'CRLF'), ('CRLF', 'LF'), ('LF', 'LF')]            # (parche, arbol)
ABBR = {('CRLF', 'CRLF'): 'CC', ('LF', 'CRLF'): 'LC', ('CRLF', 'LF'): 'CL', ('LF', 'LF'): 'LL'}


def load(path):
    p = pathlib.Path(path)
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()] if p.exists() else []


def project_root():
    return next(p for p in pathlib.Path(__file__).resolve().parents if (p / 'results' / 'final_tasks.csv').exists())


def file_context_status(task_id, strategy, p, root):
    """(estado, ficheros_del_parche, ficheros_en_contexto) para un parche. Solo lectura de prompt.txt y patch.diff."""
    base = root / 'logs' / 'downstream' / task_id / strategy
    prompt = (base / 'prompt.txt').read_text(encoding='utf-8', errors='replace')
    ctx = set(re.findall(r'^File: (\S+)', prompt, re.M))
    text = (base / 'patch.diff').read_bytes().decode('utf-8', 'replace')
    files = sorted({'/'.join(h.split('/')[p:]) for h in re.findall(r'^--- (\S+)', text, re.M) if h != '/dev/null'})
    inside = [f for f in files if f in ctx]
    if files and len(inside) == len(files):
        status = 'todos en contexto'
    elif inside:
        status = 'parcial'
    elif files:
        status = 'ninguno en contexto'
    else:
        status = 'sin cabeceras'
    return status, files, sorted(ctx)


def ficheros_contexto(d):
    """Analisis exploratorio a nivel de fichero; escribe analisis_ficheros_contexto.json en `d`."""
    root = project_root()
    rows = load(d / 'cells.jsonl')
    by = defaultdict(dict)
    for r in rows:
        by[(r['task_id'], r['estrategia'])][(r['parche_eol'], r['arbol_eol'], r['p'])] = r
    base = lambda k: by[k][('CRLF', 'CRLF', 1)]
    INV = [k for k in by if base(k)['estado_original'] == 'invalid_patch']
    CTRL = [k for k in by if k not in INV]
    nat = [k for k in INV if base(k)['p_natural'] is not None and not base(k)['ambiguo_ab']]
    ll = lambda k: by[k][('LF', 'LF', base(k)['p_natural'])]
    S96 = [k for k in nat if ll(k)['categoria'] in ('contexto_no_coincide', 'corrupt_patch')]
    A11 = [k for k in nat if ll(k)['aplica']]
    det = {}

    def classify(keys, pfun, name):
        out = []
        for k in keys:
            st, files, ctx = file_context_status(k[0], k[1], pfun(k), root)
            out.append({'task_id': k[0], 'estrategia': k[1], 'categoria_LL': ll(k)['categoria'] if k in nat else None,
                        'estado_original': base(k)['estado_original'], 'estado_contexto': st, 'ficheros_del_parche': files})
        det[name] = out
        return Counter(o['estado_contexto'] for o in out), out

    c96, l96 = classify(S96, lambda k: base(k)['p_natural'], 'detalle_96')
    c11, _ = classify(A11, lambda k: base(k)['p_natural'], 'detalle_11')
    cc, _ = classify(CTRL, lambda k: 1, 'detalle_controles')
    por_cat = Counter((o['categoria_LL'], o['estado_contexto']) for o in l96)
    res = {
        'nota': 'Exploratorio a nivel de fichero; no es a nivel de linea ni frente al gold context. Aplicabilidad no es resolucion.',
        'origen': d.name,
        'n_96_contexto_o_corrupt_en_LL_con_p_natural': len(S96),
        'estado_contexto_de_los_96': dict(c96),
        'al_menos_un_fichero_no_visto_en_los_96': c96['ninguno en contexto'] + c96['parcial'],
        'por_categoria_y_estado': {f'{a}|{b}': n for (a, b), n in sorted(por_cat.items())},
        'n_11_que_aplican_en_LL_con_p_natural': len(A11),
        'estado_contexto_de_los_11': dict(c11),
        'estado_contexto_de_los_9_controles': dict(cc),
        **det}
    path = d / 'analisis_ficheros_contexto.json'
    path.open('x', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if not k.startswith('detalle')}, ensure_ascii=False, indent=1))
    print(f'[escrito: {path}]')


def parse_hunks(text, strip):
    """[(fichero, [lineas_antiguas], [lineas_eliminadas], n_sin_prefijo)] por hunk. Tolerante: una linea sin prefijo cuenta como contexto."""
    lines = text.replace('\r\n', '\n').split('\n')
    out, cur, i = [], None, 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            name = ln[4:].split('\t')[0].strip()
            cur = None if name == '/dev/null' else '/'.join(name.split('/')[strip:])
            i += 2
            continue
        if re.match(r'^@@ -\d+(,\d+)? \+\d+(,\d+)? @@', ln) and cur:
            old, rem, noprefix = [], [], 0
            i += 1
            while i < len(lines) and not lines[i].startswith('@@ ') and not lines[i].startswith('diff --git') \
                    and not lines[i].startswith('```') \
                    and not (lines[i].startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ ')):
                l = lines[i]
                if l.startswith('\\'):
                    pass
                elif l.startswith('+'):
                    pass
                elif l.startswith('-'):
                    old.append(l[1:].rstrip()); rem.append(l[1:].rstrip())
                elif l.startswith(' '):
                    old.append(l[1:].rstrip())
                else:
                    old.append(l.rstrip()); noprefix += 1 if l else 0
                i += 1
            while old and old[0] == '':
                old.pop(0)
            while old and old[-1] == '':
                old.pop()
            out.append((cur, old, rem, noprefix))
            continue
        i += 1
    return out


def contiguous(block, lines, norm=lambda s: s):
    if not block:
        return False
    b = [norm(x) for x in block]
    n = len(b)
    return any([norm(x) for x in lines[j:j + n]] == b for j in range(len(lines) - n + 1))


def anclaje_contenido(d):
    root = project_root()
    tasks = {r['original_inst_id']: r for r in csv.DictReader(open(root / 'results' / 'final_tasks.csv', encoding='utf-8-sig'))}
    rows = load(d / 'cells.jsonl')
    by = defaultdict(dict)
    for r in rows:
        by[(r['task_id'], r['estrategia'])][(r['parche_eol'], r['arbol_eol'], r['p'])] = r
    base = lambda k: by[k][('CRLF', 'CRLF', 1)]
    INV = [k for k in by if base(k)['estado_original'] == 'invalid_patch']
    CTRL = [k for k in by if k not in INV]
    nat = [k for k in INV if base(k)['p_natural'] is not None and not base(k)['ambiguo_ab']]
    ll = lambda k: by[k][('LF', 'LF', base(k)['p_natural'])]
    sets = {'96_contexto_o_corrupt': [k for k in nat if ll(k)['categoria'] in ('contexto_no_coincide', 'corrupt_patch')],
            '11_recuperables': [k for k in nat if ll(k)['aplica']], '9_controles': CTRL}
    cache = {}

    def file_lines(k, path):
        tk = tasks[k[0]]
        key = (tk['repo'], tk['base_commit'], path)
        if key not in cache:
            repo = root / 'repos' / tk['repo'].replace('/', '__')
            p = subprocess.run(['git', '--no-optional-locks', '-C', str(repo), 'cat-file', 'blob', f"{tk['base_commit']}:{path}"],
                               capture_output=True)
            cache[key] = None if p.returncode else [x.rstrip() for x in p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n').split('\n')]
        return cache[key]

    res, detail = {}, {}
    for name, keys in sets.items():
        cnt = Counter()
        det = []
        for k in keys:
            strip = base(k)['p_natural'] if k in INV else 1
            text = (root / 'logs' / 'downstream' / k[0] / k[1] / 'patch.diff').read_bytes().decode('utf-8', 'replace')
            hs = parse_hunks(text, strip)
            st = []
            for (f, old, rem, _np) in hs:
                fl = file_lines(k, f)
                if fl is None:
                    st.append('fichero_no_existe')
                elif not old:
                    st.append('solo_anade_sin_bloque_antiguo')          # ni contexto ni lineas eliminadas: no se puede anclar
                elif contiguous(old, fl):
                    st.append('bloque_completo_exacto')                  # contexto (+ eliminadas) contiguos y exactos
                elif contiguous(old, fl, lambda s: s.strip()):
                    st.append('bloque_completo_sin_indentacion')
                elif rem and contiguous(rem, fl):
                    st.append('solo_lineas_eliminadas_exactas')
                else:
                    st.append('no_ancla')
            if not st:
                pat = 'sin_hunks_analizables'
            elif all(s in ('bloque_completo_exacto', 'bloque_completo_sin_indentacion') for s in st):
                pat = 'todos_los_hunks_anclan_con_su_bloque_completo'
            elif all(s in ('bloque_completo_exacto', 'bloque_completo_sin_indentacion', 'solo_lineas_eliminadas_exactas') for s in st):
                pat = 'todos_anclan_al_menos_por_sus_lineas_eliminadas'
            elif any(s == 'solo_anade_sin_bloque_antiguo' for s in st) and not any(s in ('no_ancla', 'fichero_no_existe') for s in st):
                pat = 'incluye_hunks_solo_anade_no_verificables'
            elif any(s in ('bloque_completo_exacto', 'bloque_completo_sin_indentacion', 'solo_lineas_eliminadas_exactas') for s in st):
                pat = 'anclan_algunos_hunks'
            else:
                pat = 'ningun_hunk_ancla'
            cnt[pat] += 1
            vis = None
            if name == '96_contexto_o_corrupt':
                vis = file_context_status(k[0], k[1], strip, root)[0]
            det.append({'task_id': k[0], 'estrategia': k[1], 'categoria_LL': ll(k)['categoria'] if k in nat else None,
                        'estado_original': base(k)['estado_original'], 'visibilidad_de_ficheros': vis, 'hunks': st, 'resultado': pat})
        res[name] = dict(cnt)
        detail[name] = det
    cruce = Counter((x['visibilidad_de_ficheros'], x['resultado']) for x in detail['96_contexto_o_corrupt'])
    # Cumplimiento de la instruccion "no usar bloques Markdown": parches con lineas que empiezan por ``` (los 150)
    fences = Counter()
    for k in by:
        text = (root / 'logs' / 'downstream' / k[0] / k[1] / 'patch.diff').read_bytes().decode('utf-8', 'replace')
        fences[(base(k)['estado_original'] == 'invalid_patch', bool(re.search(r'^```', text, re.M)))] += 1
    out = {'nota': 'Cota exploratoria: ancla por contenido, ignorando numeros de linea; no genera ni aplica parches, no mide resolucion.',
           'origen': d.name, 'resumen': res,
           'parches_con_bloque_markdown_```_de_los_150': {'invalid_patch_con': fences[(True, True)], 'invalid_patch_sin': fences[(True, False)],
                                                          'aplicables_con': fences[(False, True)], 'aplicables_sin': fences[(False, False)]},
           'cruce_96_visibilidad_x_anclaje': {f'{a}|{b}': n for (a, b), n in sorted(cruce.items())}, **{f'detalle_{k}': v for k, v in detail.items()}}
    path = d / 'analisis_anclaje_contenido.json'
    path.open('x', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if not k.startswith('detalle')}, ensure_ascii=False, indent=1))
    print(f'[escrito: {path}]')


def hunk_ranges(text, strip):
    """{fichero: [(inicio, fin)]} con el rango antiguo de cada hunk (segun sus cabeceras @@)."""
    out, cur = defaultdict(list), None
    for ln in text.replace('\r\n', '\n').split('\n'):
        m = re.match(r'^--- (\S+)', ln)
        if m and m.group(1) != '/dev/null':
            cur = '/'.join(m.group(1).split('/')[strip:])
            continue
        m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@', ln)
        if m and cur is not None:
            a = int(m.group(1)); n = int(m.group(2)) if m.group(2) is not None else 1
            out[cur].append((a, a + max(n, 1) - 1))
    return out


def referencia(d):
    import os
    os.environ.setdefault('HF_DATASETS_OFFLINE', '1')
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    from datasets import load_dataset
    root = project_root()
    meta = {r['original_inst_id']: r for r in load_dataset('Contextbench/ContextBench')['train']}
    rows = load(d / 'cells.jsonl')
    by = defaultdict(dict)
    for r in rows:
        by[(r['task_id'], r['estrategia'])][(r['parche_eol'], r['arbol_eol'], r['p'])] = r
    base = lambda k: by[k][('CRLF', 'CRLF', 1)]
    INV = [k for k in by if base(k)['estado_original'] == 'invalid_patch']
    CTRL = [k for k in by if k not in INV]
    nat = [k for k in INV if base(k)['p_natural'] is not None and not base(k)['ambiguo_ab']]
    ll = lambda k: by[k][('LF', 'LF', base(k)['p_natural'])]
    sets = {'96_contexto_o_corrupt': [k for k in nat if ll(k)['categoria'] in ('contexto_no_coincide', 'corrupt_patch')],
            '11_recuperables': [k for k in nat if ll(k)['aplica']], '9_controles': CTRL}

    def proxy(k, strip):
        text = (root / 'logs' / 'downstream' / k[0] / k[1] / 'patch.diff').read_bytes().decode('utf-8', 'replace')
        mh = hunk_ranges(text, strip)
        gold = defaultdict(list)
        cur = None
        for ln in meta[k[0]]['patch'].replace('\r\n', '\n').split('\n'):
            m = re.match(r'^--- a/(\S+)', ln)
            if m:
                cur = m.group(1); continue
            m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@', ln)
            if m and cur is not None:
                a = int(m.group(1)); n = int(m.group(2)) if m.group(2) is not None else 1
                gold[cur].append((a, a + max(n, 1) - 1))
        shared = set(mh) & set(gold)
        overlap = any(not (e1 < s2 or e2 < s1) for f in shared for (s1, e1) in mh[f] for (s2, e2) in gold[f])
        return bool(shared), overlap, sorted(mh), sorted(gold)

    out = {'nota': 'Indicador de plausibilidad con la solucion de referencia (no dada al modelo); no es resolucion funcional.',
           'origen': d.name,
           'fuente_de_los_141': dict(Counter(meta[k[0]]['source'] for k in INV)),
           'fuente_de_los_11': dict(Counter(meta[k[0]]['source'] for k in sets['11_recuperables'])),
           'fuente_de_los_9_controles': dict(Counter(meta[k[0]]['source'] for k in CTRL))}
    resumen, detalle = {}, {}
    for name, keys in sets.items():
        c, det = Counter(), []
        for k in keys:
            strip = base(k)['p_natural'] if k in INV else 1
            same, ov, f1, f2 = proxy(k, strip)
            c[('mismo_fichero_que_la_referencia' if same else 'otro_fichero', 'solapa' if ov else 'sin_solape')] += 1
            det.append({'task_id': k[0], 'estrategia': k[1], 'fuente': meta[k[0]]['source'], 'estado_original': base(k)['estado_original'],
                        'mismo_fichero': same, 'solapa': ov, 'ficheros_del_parche': f1, 'ficheros_de_la_referencia': f2})
        resumen[name] = {f'{a}|{b}': n for (a, b), n in sorted(c.items())}
        resumen[name]['total_mismo_fichero'] = sum(n for (a, _b), n in c.items() if a == 'mismo_fichero_que_la_referencia')
        detalle[name] = det
    # cruce con la visibilidad de ficheros (para los 96)
    cruce = Counter()
    for x in detalle['96_contexto_o_corrupt']:
        k = (x['task_id'], x['estrategia'])
        vis = file_context_status(k[0], k[1], base(k)['p_natural'], root)[0]
        cruce[(vis, 'edita_fichero_de_la_referencia' if x['mismo_fichero'] else 'edita_otro_fichero')] += 1
    out.update({'resumen': resumen, 'cruce_96_visibilidad_x_referencia': {f'{a}|{b}': n for (a, b), n in sorted(cruce.items())},
                **{f'detalle_{k}': v for k, v in detalle.items()}})
    path = d / 'analisis_referencia.json'
    path.open('x', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if not k.startswith('detalle')}, ensure_ascii=False, indent=1))
    print(f'[escrito: {path}]')


def main():
    if len(sys.argv) == 3 and sys.argv[2] == '--referencia':
        return referencia(pathlib.Path(sys.argv[1]).resolve())
    if len(sys.argv) == 3 and sys.argv[2] == '--anclaje-contenido':
        return anclaje_contenido(pathlib.Path(sys.argv[1]).resolve())
    if len(sys.argv) == 3 and sys.argv[2] == '--ficheros-contexto':
        return ficheros_contexto(pathlib.Path(sys.argv[1]).resolve())
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = pathlib.Path(sys.argv[1]).resolve()
    rows = load(d / 'cells.jsonl')
    rob = load(d / 'cells_robustez_autocrlf_false.jsonl')
    ctl = json.load(open(d / 'controls.json', encoding='utf-8'))
    man = json.load(open(d / 'manifest.json', encoding='utf-8'))
    out, js = [], {}

    def w(s=''):
        out.append(s)

    def table(header, body):
        w('| ' + ' | '.join(header) + ' |')
        w('|' + '|'.join('---' for _ in header) + '|')
        for r in body:
            w('| ' + ' | '.join(str(x) for x in r) + ' |')
        w()

    key = lambda r: (r['task_id'], r['estrategia'])
    patches = {}
    for r in rows:
        patches.setdefault(key(r), r)
    INV = [k for k, r in patches.items() if r['estado_original'] == 'invalid_patch']
    CTRL = [k for k, r in patches.items() if r['estado_original'] != 'invalid_patch']
    meta = {k: patches[k] for k in patches}
    nat = {k for k in INV if meta[k]['p_natural'] is not None and not meta[k]['ambiguo_ab']}
    by = defaultdict(dict)
    for r in rows:
        by[key(r)][(r['parche_eol'], r['arbol_eol'], r['p'])] = r
    byrob = defaultdict(dict)
    for r in rob:
        byrob[key(r)][(r['parche_eol'], r['arbol_eol'], r['p'])] = r

    w(f"# Analisis de {d.name}")
    w(f"Parches: {len(patches)} (141 `invalid_patch` esperados: {len(INV)}; controles con aplicabilidad original: {len(CTRL)}). "
      f"Celdas principales: {len(rows)}; robustez: {len(rob)}. Script v{man.get('version')}, manifest esquema {man.get('manifest_esquema')}.")
    w(f"Integridad: sin cambios = {man.get('integridad_sin_cambios')}; codigo de salida = {man.get('codigo_salida')}. "
      f"`core.autocrlf` efectivo: principal={man.get('config_efectiva_matriz_principal', {}).get('core.autocrlf')}, "
      f"robustez={man.get('config_efectiva_replica_robustez', {}).get('core.autocrlf')}.")
    w()
    js['n'] = {'parches': len(patches), 'invalid': len(INV), 'controles': len(CTRL), 'natural_p': len(nat)}

    # ---- controles ------------------------------------------------------------------------------------------------
    w('## 0. Controles'); w()
    c1 = ctl['control_1_linea_base']
    w(f"- **Control 1 (linea base = resultado original de `git apply --check`)**: {c1['coinciden']} de {c1['parches']} coinciden; "
      f"discrepancias: {len(c1['discrepancias'])}.")
    c2 = ctl.get('control_2_aplicables_pasan_en_linea_base', {}); w(f"- **Control 2** (los {c2.get('n')} aplicables originales aplican en la linea base): fallan {len(c2.get('fallan', []))}.")
    c3 = ctl.get('control_3_sin_diff_fallan_en_todas_las_celdas'); c4 = ctl.get('control_4_celdas_cruzadas_de_p')
    if c3 is not None:
        w(f"- **Control 3** (respuestas sin diff nunca aplican): violaciones {len(c3['violaciones'])}.")
    if c4 is not None:
        w(f"- **Control 4** (celdas con `-p` cruzado deben fallar): n={c4['n']}, categorias={c4['categorias']}, "
          f"que aplican (anomalia)={len(c4['aplican_(anomalia)'])}.")
    w(); js['controles'] = {'c1_coinciden': c1['coinciden'], 'c1_discrepancias': len(c1['discrepancias']),
                            'c3_violaciones': None if c3 is None else len(c3['violaciones']),
                            'c4': None if c4 is None else {'n': c4['n'], 'anomalias': len(c4['aplican_(anomalia)'])}}

    # ---- 1. aplicables por condicion --------------------------------------------------------------------------------
    w('## 1. Parches que pasan `git apply --check` por condicion (matriz principal, `autocrlf=true`)'); w()
    w(f"**A. Con el `-p` natural de cada parche** (resultado principal fijado de antemano). Poblacion: {len(nat)} de los {len(INV)} "
      f"`invalid_patch` con `-p` natural no ambiguo; excluidos {len(INV) - len(nat)} (sin cabeceras o `-p` indeterminado). "
      f"En la linea base original (CC con `-p1`) aplican 0 de los {len(INV)}.")
    w()
    body, js['aplican_p_natural'] = [], {}
    for pe, te in MAIN_COMBOS:
        a = sum(1 for k in nat if by[k][(pe, te, meta[k]['p_natural'])]['aplica'])
        ne = sum(1 for k in nat if by[k][(pe, te, meta[k]['p_natural'])]['no_evaluable'])
        ca = sum(1 for k in CTRL if by[k][(pe, te, meta[k]['p_natural'])]['aplica'])
        body.append((f"{ABBR[(pe, te)]} (parche {pe}, arbol {te})", f"{a} / {len(nat)} ({100 * a / len(nat):.1f} %)", ne, f"{ca} / {len(CTRL)}"))
        js['aplican_p_natural'][ABBR[(pe, te)]] = {'invalid': a, 'de': len(nat), 'controles': ca, 'no_evaluables': ne}
    table(['Condicion', f'`invalid_patch` que aplican (de {len(nat)})', 'no evaluables', 'Controles (9 aplicables originales)'], body)
    w(f"**B. Con `-p` forzado** (los {len(INV)} `invalid_patch`, sin tener en cuenta el `-p` natural; el que no corresponde es un control):"); w()
    body, js['aplican_p_forzado'] = [], {}
    for p in (1, 0):
        for pe, te in MAIN_COMBOS:
            a = sum(1 for k in INV if by[k][(pe, te, p)]['aplica'])
            ca = sum(1 for k in CTRL if by[k][(pe, te, p)]['aplica'])
            body.append((f"{ABBR[(pe, te)]} con -p{p}", f"{a} / {len(INV)}", f"{ca} / {len(CTRL)}"))
            js['aplican_p_forzado'][f"{ABBR[(pe, te)]}_p{p}"] = {'invalid': a, 'controles': ca}
    table(['Celda', f'`invalid_patch` que aplican (de {len(INV)})', 'Controles'], body)
    w("Leyenda: primera letra = parche original (C = CRLF) o normalizado (L = LF); segunda = arbol CRLF o LF. "
      "**CC con `-p1` es el filtro original; LL con `-p1` es la celda mas parecida a lo que reciben los evaluadores (parche LF, `-p1`, "
      "Linux), sin sus alternativas de aplicacion (sin equivalencia demostrada).**"); w()

    # ---- 2. por estrategia -----------------------------------------------------------------------------------------
    w('## 2. Desglose por estrategia de recuperacion (con `-p` natural)'); w()
    body, js['por_estrategia'] = [], {}
    for s, name in STRAT.items():
        ks = [k for k in nat if k[1] == s]
        kc = [k for k in CTRL if k[1] == s]
        row = [name, len([k for k in INV if k[1] == s]), len(ks)]
        for pe, te in MAIN_COMBOS:
            row.append(f"{sum(1 for k in ks if by[k][(pe, te, meta[k]['p_natural'])]['aplica'])} / {len(ks)}")
        row.append(f"{sum(1 for k in kc if by[k][('CRLF', 'CRLF', 1)]['aplica'])} / {len(kc)}")
        body.append(row)
        js['por_estrategia'][name] = {'invalid': len([k for k in INV if k[1] == s]), 'con_p_natural': len(ks), 'controles': len(kc)}
    table(['Estrategia', '`invalid_patch`', 'con -p natural', *[ABBR[c] for c in MAIN_COMBOS], 'controles en linea base'], body)

    # ---- 3. transiciones ----------------------------------------------------------------------------------------------
    w('## 3. Transiciones respecto de la linea base original (CC con `-p1`), solo `invalid_patch` con `-p` natural'); w()
    js['transiciones'] = {}
    for pe, te in [('LF', 'LF'), ('CRLF', 'CRLF'), ('LF', 'CRLF'), ('CRLF', 'LF')]:
        tr = Counter((by[k][('CRLF', 'CRLF', 1)]['categoria'], by[k][(pe, te, meta[k]['p_natural'])]['categoria']) for k in nat)
        w(f"**{ABBR[(pe, te)]} con su `-p` natural** (desde la categoria de la linea base hasta la de esta celda):"); w()
        table(['desde (linea base)', 'hasta (esta celda)', 'parches'], [(a, b, n) for (a, b), n in sorted(tr.items())])
        js['transiciones'][ABBR[(pe, te)]] = {f'{a}->{b}': n for (a, b), n in tr.items()}

    # ---- 4. errores persistentes -----------------------------------------------------------------------------------
    w('## 4. Errores que persisten'); w()
    never = [k for k in INV if not any(by[k][c]['aplica'] for c in by[k])]
    w(f"- **Nunca aplican en ninguna de las 8 celdas de la matriz principal:** {len(never)} de {len(INV)} `invalid_patch`. "
      f"Categoria en la linea base: {dict(Counter(by[k][('CRLF', 'CRLF', 1)]['categoria'] for k in never))}.")
    w()
    w("**Categoria en la celda LL con su `-p` natural** (los que siguen sin aplicar):"); w()
    cats = Counter(by[k][('LF', 'LF', meta[k]['p_natural'])]['categoria'] for k in nat)
    table(['categoria (LL, -p natural)', 'parches'], sorted(cats.items(), key=lambda x: -x[1]))
    js['persisten_LL_natural'] = dict(cats)
    base_cat = Counter(by[k][('CRLF', 'CRLF', 1)]['categoria'] for k in INV)
    w(f"- Para comparar, categorias de la linea base sobre los {len(INV)}: {dict(base_cat)}."); w()
    sin_diff = [k for k in INV if meta[k]['sin_diff_original']]
    w(f"- **Respuestas sin diff:** {len(sin_diff)}; aplican en alguna celda: {sum(1 for k in sin_diff if any(by[k][c]['aplica'] for c in by[k]))} (control 3).")
    cp = [k for k in INV if by[k][('CRLF', 'CRLF', 1)]['categoria'] == 'corrupt_patch']
    cp_fl = [k for k in cp if any(by[k][c]['aplica'] for c in by[k])]
    w(f"- **`corrupt_patch` en la linea base:** {len(cp)}; aplican en alguna celda: {len(cp_fl)} (H3 esperaba pocos o ninguno)."); w()
    js['never_apply'] = len(never); js['corrupt'] = {'n': len(cp), 'aplican_en_alguna_celda': len(cp_fl)}

    # ---- 5. no evaluables / ambiguos -------------------------------------------------------------------------------
    w('## 5. Casos no evaluables o ambiguos'); w()
    ne = [r for r in rows + rob if r['no_evaluable']]
    w(f"- **Celdas no evaluables:** {len(ne)} (principal {sum(1 for r in rows if r['no_evaluable'])}, robustez {sum(1 for r in rob if r['no_evaluable'])}). "
      f"Motivos: {dict(Counter((r['reconstruccion'].get('motivo_no_evaluable') or '')[:40] for r in ne))}.")
    w(f"- **Grupos de prefijo (150 parches):** {dict(Counter(meta[k]['grupo_prefijo'] for k in patches))}.")
    w(f"- **Ambiguedad `a/` `b/` (directorio real llamado a o b):** {sum(1 for k in patches if meta[k]['ambiguo_ab'])}.")
    ind = [k[0][:45] + ' ' + k[1] for k in INV if meta[k]['grupo_prefijo'] == 'indeterminado']
    w(f"- **`-p` indeterminado (excluidos del analisis de `-p` natural):** {ind}."); w()
    js['no_evaluables'] = len(ne); js['indeterminados'] = ind

    # ---- 6. principal frente a robustez ------------------------------------------------------------------------------
    w('## 6. Matriz principal (`autocrlf=true`) frente a la replica de robustez (`autocrlf=false`), arboles LF'); w()
    diff_cat = diff_msg = tot = 0
    flips = []
    for k in patches:
        for c, rr in byrob.get(k, {}).items():
            m = by[k][c]; tot += 1
            if m['categoria'] != rr['categoria']:
                diff_cat += 1; flips.append((k[0][:40], k[1], c, m['categoria'], rr['categoria']))
            if (m['git_mensaje'] or '') != (rr['git_mensaje'] or ''):
                diff_msg += 1
    w(f"- Celdas comparadas: {tot}. Distinta categoria: {diff_cat}. Distinto mensaje de Git: {diff_msg}.")
    if flips:
        w('- Diferencias de categoria:'); w()
        table(['parche', 'estrategia', 'celda', 'principal', 'robustez'], flips[:40])
    w(); js['robustez'] = {'celdas': tot, 'distinta_categoria': diff_cat, 'distinto_mensaje': diff_msg}

    # ---- 7. filtro original frente a celdas parecidas al evaluador ---------------------------------------------------
    w('## 7. Filtro original (CC, `-p1`) frente a la celda mas parecida a los evaluadores (LL, `-p1`)'); w()
    ll_inv = [k for k in INV if by[k][('LF', 'LF', 1)]['aplica']]
    ctl_fail = [k for k in CTRL if not by[k][('LF', 'LF', 1)]['aplica']]
    w(f"- `invalid_patch` que **aplican en LL con `-p1`**: {len(ll_inv)} de {len(INV)} (rechazados por el filtro original). "
      f"Por grupo: {dict(Counter(meta[k]['grupo_prefijo'] for k in ll_inv))}. Por estrategia: {dict(Counter(STRAT[k[1]] for k in ll_inv))}.")
    w(f"- Controles (aplicaban en el filtro original) que **no aplican en LL con `-p1`**: {len(ctl_fail)} de {len(CTRL)}.")
    w("- Esto es una prueba de sensibilidad: `git apply --check` estricto, sin las alternativas de los evaluadores y con un arbol "
      "emulado; no equivale a la aceptacion del evaluador oficial ni a la resolucion de la tarea."); w()
    js['LL_p1'] = {'invalid_que_aplican': len(ll_inv), 'controles_que_no_aplican': len(ctl_fail)}

    (d / 'analisis.md').open('x', encoding='utf-8').write('\n'.join(out) + '\n')
    (d / 'analisis.json').open('x', encoding='utf-8').write(json.dumps(js, ensure_ascii=False, indent=1))
    print('\n'.join(out))
    print(f"[escrito: {d / 'analisis.md'} y analisis.json]")


if __name__ == '__main__':
    main()
