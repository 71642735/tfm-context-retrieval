# pilot_p1 — Preparación técnica del piloto P1 (fases 1, 2, 3A y 3B.1)

> **Ni la fase 1, ni la 2, ni la 3A, ni la 3B.1 son una ejecución experimental de P1.** No hay generaciones reales con el LLM ni
> llamadas a la API. Las fases 3A y 3B.1 **sí han ejercitado** el filtro G y la evaluación funcional, pero solo con datos sintéticos y
> evaluadores falsos (y, en solo lectura, con prompts y repositorios reales): **no se han ejecutado sobre generaciones reales del LLM ni
> con el evaluador oficial**, y sus resultados no son resultados del piloto. La fase 1 (commit `e4342dd`) validó el conversor
> SEARCH/REPLACE → diff; la fase 2 prepara y valida los prompts O1/E1, el normalizador N y la selección
> determinista de las 12 tareas; la fase 3A construye y prueba, **solo con un cliente falso y respuestas
> sintéticas**, la orquestación aislada de las 72 generaciones. El protocolo P1 (D-005) sigue **sin aprobar**. Los resultados del experimento original
> (150 parches, `results/`, `repos/`) no se han tocado.

## Objetivo

En el experimento original el modelo debía escribir directamente un diff unificado, y 141 de 150 salidas no pasaron
`git apply --check`. P1 propone probar un formato en el que el modelo cite bloques literales (SEARCH) y su reemplazo, y
sea un programa determinista quien construya el diff. Esta fase construye y valida ese programa: el parser del formato y
el aplicador. No dice nada sobre si el formato mejora los resultados.

## Contenido

| Fichero | Función |
|---|---|
| `edit_format.py` | Parser estricto de instrucciones `FILE` / `SEARCH` / `REPLACE` |
| `applier.py` | Aplicador determinista sobre copias temporales de ficheros de un commit; genera el diff |
| `prompts.py` | Fase 2: reconstrucción de los prompts O1 y E1 y verificación de que comparten contexto |
| `instructions_edit_v1.txt` | Fase 2: instrucciones E1 congeladas (SHA-256 fijado en `prompts.py`) |
| `normalizer.py` | Fase 2: normalizador N de parches del brazo original |
| `select_tasks.py`, `data/task_selection.json` | Fase 2: selección determinista de las 12 tareas y metadatos para reproducirla |
| `orchestrator.py` | Fase 3A: orquestación aislada, reanudable y verificable de las 72 condiciones |
| `client.py` | Fase 3A: interfaz de cliente inyectable (`GenerationClient`) y `FakeClient`; **no hay cliente real** |
| `format_metrics.py` | Fase 3A: vallas Markdown externas/internas y parseabilidad, independientes del parser |
| `decision.py` | Fase 3A: regla de decisión del protocolo con condiciones excluidas por infraestructura |
| `gate.py` | Fase 3B.1: filtro común G (aplicabilidad) de `O1n` y `E1` |
| `functional.py` | Fase 3B.1: interfaz de evaluación funcional y evaluador **falso** (no hay adaptador del evaluador oficial) |
| `tests/` | Pruebas (`unittest`), fixtures y contraste con parches conocidos |
| `.gitattributes` | `* -text` para `instructions_edit_v1.txt` y `data/` (sin conversión de finales de línea) |
| `tests/fixtures/.gitattributes` | `* -text`: impide que `core.autocrlf` convierta los fixtures (solo afecta a esa carpeta) |

## Formato EDIT-v1

```
FILE: ruta/relativa/fichero.py
<<<<<<< SEARCH
texto literal que existe en el fichero
=======
texto de reemplazo
>>>>>>> REPLACE
```

* Un `FILE:` admite varios bloques seguidos; otro `FILE:` cambia de fichero.
* Fuera de los bloques solo se aceptan líneas en blanco y vallas Markdown (líneas que empiezan por ```). Cualquier otro
  texto es `parse_error`; un diff unificado no se acepta.
* Los marcadores se reconocen por igualdad exacta de línea, ignorando **solo espacios y tabuladores** finales. Un marcador
  en la sección equivocada, un bloque sin cerrar, un `FILE:` sin bloques o un carácter NUL son error.
* CRLF y CR de la entrada se normalizan a LF.
* `SEARCH` vacío = crear fichero. `REPLACE` vacío = borrar lo encontrado.

## Reglas del aplicador

1. **Solo lectura.** `GitSource` ejecuta únicamente `git ls-tree` y `git cat-file` (lista blanca; commit hexadecimal
   obligatorio; sin checkout, fetch ni escritura). `DirSource` lee de un directorio (pruebas).
2. **Copias temporales aisladas.** Cada fichero se copia a un directorio temporal nuevo, se modifica allí y se borra al
   terminar. Con `keep_copies_in=<dir>` se conservan, pero **nunca se escribe en `<dir>`**: se crea dentro un subdirectorio
   nuevo y vacío (`mkdtemp`), de modo que no puede sobrescribir nada. `<dir>` debe ser absoluto, existir y no estar dentro
   del proyecto (`src/`, `repos/`, `results/`...), de la fuente que se lee ni de ningún árbol git; si no, `WorkdirError`
   antes de hacer nada.
3. **Coincidencia única y verificable.** El `SEARCH` se busca por líneas completas sobre el fichero **original**: nivel 1 =
   igualdad exacta ignorando espacios y tabuladores finales; si hay 0 coincidencias, nivel 2 = ignorando la indentación
   (espacios y tabuladores iniciales) con un desplazamiento uniforme (el `REPLACE` se reindenta igual). Exactamente una
   coincidencia en el nivel que se use; 0 → `search_not_found`, 2 o más → `ambiguous_match`. Otros blancos (`\x0c`,
   `\xa0`, espacios Unicode) **no** se ignoran. No hay otra coincidencia aproximada.
4. **Todo o nada.** Si un bloque falla no se devuelve ningún diff.
5. **Operaciones inconsistentes.** Bloques solapados (también duplicados idénticos) → `overlapping_edits`; `SEARCH` vacío
   sobre fichero existente, crear dos veces el mismo fichero o crear un fichero vacío o solo con líneas en blanco →
   `inconsistent_edits`; `SEARCH` solo con líneas en blanco → `blank_search`; ediciones sin efecto → `empty_diff`.
6. **Creación de ficheros.** Además: se rechaza (`inconsistent_edits`) la colisión por mayúsculas/minúsculas con una entrada
   existente (fichero o directorio padre) y entre ficheros nuevos de la misma instrucción, y crear a la vez `a` y `a/b`.
   Crear sobre un directorio existente → `unsupported_file`; bajo un padre que es fichero o symlink → `unsafe_path`.
7. **Rutas.** `unsafe_path` para rutas absolutas, con unidad (`C:`), `~`, `..`, `.`, segmentos vacíos, barra invertida,
   caracteres de control, `:` en un segmento, segmentos que terminan en espacio o punto, `.git`/`.gitmodules`, nombres
   reservados de Windows (`con`, `aux`, `nul`, `com1`...), segmentos de más de 255 bytes y rutas de más de 1024 caracteres.
   Symlinks, submódulos y directorios → `unsupported_file`.
8. **Formato del fichero.** Se conserva el final de línea nativo (CRLF o LF), el BOM UTF-8 y la ausencia de salto final.
   Se rechazan (`unsupported_file`) binarios, no UTF-8 y finales de línea mixtos o CR sueltos. Los ficheros nuevos se
   crean en LF con salto final.
9. **Errores del entorno ≠ errores del modelo.** `GitSource.entry()` devuelve `None` solo si la ruta no existe en el
   commit; cualquier fallo de git (repositorio dañado, `safe.directory`, tiempo agotado, git ausente) lanza `SourceError`,
   y el aplicador lo devuelve como `environment_error` (`ApplyResult.model_fault` es `False`). Cada invocación de git tiene
   un límite de 60 s (`GIT_TIMEOUT_S`, ajustable por `GitSource(timeout=...)`); al agotarse se informa como
   `environment_error` con el motivo. Una ejecución de P1 debe tratar `environment_error` como reintento o incidencia, no
   como fallo del formato.
10. **Diff.** Estilo git: `diff --git a/ b/`, `---`/`+++` con prefijos `a/` `b/`, 3 líneas de contexto, `\ No newline at end
    of file` cuando corresponde, ficheros ordenados por ruta, sin fechas ni identificadores variables. Mismo commit y misma
    instrucción producen el mismo diff byte a byte (`ApplyResult.diff_sha256`). Escribirlo en bytes (`diff_bytes`): el diff
    de ficheros CRLF contiene CR.

Estados: `parse_error`, `unsafe_path`, `file_not_found`, `unsupported_file`, `search_not_found`, `blank_search`,
`ambiguous_match`, `overlapping_edits`, `inconsistent_edits`, `empty_diff`, `patch_ready` y `environment_error`.

## Uso

```python
from pilot_p1.applier import GitSource, apply_text
src = GitSource("repos/owner__repo", "<base_commit>")
r = apply_text(salida_del_modelo, src)
if r.ok:
    open("parche.diff", "wb").write(r.diff_bytes)
elif r.model_fault:
    print("rechazo atribuible a la salida:", r.status, r.detail)
else:
    print("fallo del entorno, no del modelo:", r.detail)
```

## Cómo reproducir las pruebas

Desde la raíz del repositorio. No necesitan API, ni red, ni evaluadores, ni modifican `repos/`:

```bash
python -B -m unittest discover -s pilot_p1/tests -t .
```

Requisitos: Python 3 y `git` en el PATH (usado para los repositorios temporales y para contrastar con `git apply`).
`P1_SKIP_KNOWN=1` omite el contraste con parches conocidos (~2,5 min). Duración total ≈ 8-10 min (fases 1 y 2). `python -m pilot_p1.select_tasks --check` verifica la selección.

## Validación técnica

| | Pruebas locales | Parches conocidos contrastados |
|---|---|---|
| Validación inicial | 93 | 19 (8 originalmente aplicables + 11 recuperables) |
| Validación final (tras las correcciones) | **139** | **20** (los 9 originalmente aplicables + los 11 recuperables) |

Ninguna de estas cifras representa incidencias resueltas ni resultados nuevos del experimento: miden solo que el
conversor y Git aceptan los parches. Los resultados originales (141 `invalid_patch`, 7 `not_resolved`, 2 `resolved`) no cambian.

**Validación inicial (2026-11-12): 93 pruebas locales, todas correctas.** Parser (32), aplicador (60: aceptados, rechazados,
rutas inseguras, solo lectura) y contraste con parches conocidos (1). Cada caso aceptado se contrasta con **`git apply`
real**: el fichero resultante es idéntico byte a byte y el diff pasa `git apply --check`.

**Contraste con parches conocidos.** De los 150 parches originales, 19 pasaron `git apply --check` (con su `-p0`/`-p1`)
sobre los ficheros del `base_commit` en un directorio temporal: **8 ya aplicables en el experimento original y 11
recuperables bajo condiciones alternativas** (los que no llevaban prefijos `a/` `b/`; el filtro original usa `-p1` y los
marcó `invalid_patch`). Convertidos bloque a bloque, el aplicador aceptó los 19 con resultado idéntico al de `git apply`.
Tras la revisión, el contraste incluye también altas de fichero (`--- /dev/null`): son **20** (9 + 11), donde el noveno es
el parche `ansible-7e1a…/hybrid`, que solo crea un fichero. No se exige que todo hunk anclado dé `patch_ready`.

**Por qué 19 (o 20) no contradice los 9 del experimento original.** Son magnitudes distintas. Los 9 son los parches que
superaron el filtro original (`git apply --check` con `-p1`, sobre el árbol real, con el parche tal como se guardó) y
llegaron a evaluación funcional: 2 resolvieron, 7 no. Los 19/20 miden solo aplicabilidad bajo otras condiciones (blobs en LF,
parche normalizado a LF, `-p0` además de `-p1`). Los 9 están incluidos en los 20 (8 en los 19 más el de altas de fichero) y
los otros 11 son los recuperables ya descritos en D-004. **No son tareas resueltas**: que Git acepte un parche no dice
nada sobre si arregla la incidencia.

**Correcciones tras la revisión técnica (2026-11-12).**

| Problema | Corrección |
|---|---|
| `workdir` podía apuntar a cualquier directorio y sobrescribir ficheros | Sustituido por `keep_copies_in`: ruta absoluta, existente, fuera del proyecto, de la fuente y de árboles git; se escribe solo en un subdirectorio nuevo |
| `entry()` confundía un fallo de git con "fichero inexistente" | `None` solo si no existe; los fallos lanzan `SourceError` y se devuelven como `environment_error` (no atribuible al modelo) |
| `rstrip()`/`strip()` quitaban más blancos que espacios y tabuladores | Solo `" \t"`; `\x0c`, `\xa0`, `\x1c`... ya no se ignoran (aplicador y marcadores) |
| Sin límites de tiempo | 60 s por llamada a git, configurable; error informado |
| Fixtures expuestos a `core.autocrlf` | `tests/fixtures/.gitattributes` (`* -text`), SHA-256 fijados y prueba de ida y vuelta con `autocrlf=true` |
| Casos límite de creación | Colisiones de mayúsculas, ficheros en blanco, `a` y `a/b` a la vez, nombres reservados de Windows, longitudes, NUL |
| Altas de fichero sin contraste con parches reales | Incluidas en `test_known_patches.py` |

**Resultado final: 139 pruebas, todas correctas** (≈ 4 min; 0 fallos, 0 omitidas en el último ciclo). Desglose: parser 32;
aplicador 60; cierre 46 (`test_hardening.py`: copias seguras 10, errores de git y tiempos 10, normalización de espacios 6,
fixtures 4, creación de ficheros 16); contraste con parches conocidos 1.

**Integridad.** Antes y después de las pruebas son idénticos los SHA-256 de los ficheros versionados, de los 450 ficheros de
`logs/downstream` (los 150 parches), de `results/` y el HEAD e índice de los 21 repositorios de `repos/`.

---

# Fase 2: prompts O1/E1, normalizador N y selección de tareas

Preparación y validación local, sin generaciones, API ni evaluadores. Sigue el protocolo P1 (`docs/downstream-patch-diagnostics.md`,
15.4) sin modificarlo; las dudas están en "Problemas pendientes de la fase 2".

## Prompts O1 y E1 (`prompts.py`)

**Cómo se reconstruye O1.** No se recupera nada de nuevo (ni BM25, ni UniXcoder, ni RRF). El prompt que se envió al modelo
se obtiene del `prompt.txt` original deshaciendo exactamente la traducción de `Path.write_text` en Windows: todo `LF` del
prompt en memoria se guardó como `CRLF`, así que cada `CRLF` del fichero vuelve a `LF`. `reconstruct_prompt` **exige** que
todo `LF` del fichero vaya precedido de `CR` (se cumple en los 150) y falla si no. O1 es ese prompt sin cambios.

**Cómo se preservan los CRLF internos.** Un fragmento de código que ya contenía `CRLF` se guardó como `CR CR LF` (108 de los
150 prompts) y se recupera como `CRLF`: no se normaliza ningún final de línea del contexto. Los prompts nuevos se serializan con
`serialize_prompt` (UTF-8 exacto, `write_bytes`, sin traducción), de modo que lo enviado y lo guardado son los mismos bytes.

**Cómo se construye E1.** `build_e1` = parte compartida de O1 (todo lo anterior a `INSTRUCTIONS:`) + el texto congelado de
`instructions_edit_v1.txt`. **La única diferencia autorizada entre O1 y E1 es el bloque INSTRUCTIONS.** E1 conserva las tres
frases de información del original (usar solo issue y contexto, no asumir otros ficheros, cambio mínimo) y la de no usar
bloques Markdown, y sustituye "unified diff" y "sin explicaciones antes o después del parche" por el formato EDIT-v1
(`FILE:` + `SEARCH` / `REPLACE`), compatible con el parser y el aplicador de la fase 1.

**Creación de ficheros (instrucción añadida el 12/11/2026).** E1 incluye la regla: *"To create a new file, use a block whose
SEARCH section is empty (no lines between the `<<<<<<< SEARCH` line and the `=======` line) and put the complete content of the
new file in the replacement section. Do this only for a path that does not already exist in the repository."* Es exactamente lo
que ya aceptan `edit_format.py` y `applier.py` (SEARCH vacío = crear; sobre un fichero existente da `inconsistent_edits`); no se
inventó sintaxis ni se tocó el aplicador. Se probó que un bloque escrito según la regla se analiza y produce un fichero nuevo con
`new file mode`, que sobre un fichero existente se rechaza, y que el texto de E1 **sin** esa regla conserva el SHA-256 de la
primera versión congelada (`ae053cec644edcf53308bec657f68b2a687a1cc9ad27728780fdbf9ab29246a8`): las demás reglas no cambiaron.

**Verificación de la reconstrucción (confirmada con las 150 condiciones).**
1. *O1 reproduce el prompt en memoria enviado al modelo:* el `prompt.txt` se escribió con `write_text(prompt)` en
   `generate_from_context`, inmediatamente antes de la llamada a la API, con el mismo `prompt`; se ejecuta el `build_prompt`
   real del generador sobre los fragmentos recuperados del fichero y el resultado es igual al prompt reconstruido.
2. *`prompt.txt` contiene transformaciones de Windows:* los 150 ficheros cumplen que **todo** `LF` va precedido de `CR` (ningún
   `LF` suelto), y `windows_write_text_bytes(reconstruct(raw)) == raw` en los 150.
3. *Los CRLF internos se conservan:* los 108 prompts con `CR CR LF` recuperan `CRLF` dentro del fragmento; el recuento de `CRLF`
   de O1 y de E1 es idéntico y no hay normalización global.
4. *E1 solo cambia las instrucciones finales:* issue, parte compartida y fragmentos (10) idénticos y mismos bytes del prefijo.
Limitación: no se puede comprobar contra los bytes realmente enviados por la red (no se guardaron); la fidelidad se apoya en
la plantilla del generador y en la exactitud de la inversión.

**Parser del prompt.** `split_prompt` divide en issue, fragmentos, parte compartida e instrucciones y comprueba que
reconstruir con la plantilla del generador original (`build_prompt`, `src/downstream/generation.py`) devuelve exactamente el
mismo texto; si hay ambigüedad (p. ej. un issue que imita el marcador de contexto) lanza `PromptError` en lugar de adivinar.
`arm_record` exige además los 10 fragmentos del protocolo (K = 10).

**Hashes y controles (todos verificados por pruebas):**

| Control | Valor |
|---|---|
| SHA-256 de `instructions_edit_v1.txt` (E1, **vigente**, con la regla de creación) | `3577b64d079143810dd018d805677146fe515bc49904d2862dded53f8db293be` |
| SHA-256 de E1 en la primera versión congelada (sin la regla de creación; sustituida) | `ae053cec644edcf53308bec657f68b2a687a1cc9ad27728780fdbf9ab29246a8` |
| SHA-256 de las instrucciones originales (O1) | `1980c18b541d4c935ed5ff1686128e7086155d97f2f6a56d80de528eb91cdaac` |
| Plantilla O1 | extraída por AST del generador real y comparada; además se ejecuta su `build_prompt` real sobre los fragmentos parseados y reproduce el prompt original en las 150 condiciones |
| Ida y vuelta con `write_text` | `windows_write_text_bytes(reconstruct(raw)) == raw` en las 150 |
| Igualdad de contexto O1/E1 | `arm_record` registra el SHA-256 de O1, de E1, del issue, de la parte compartida, del orden de fragmentos y del código de cada uno; `context_identical` es verdadero en las 150 |
| Procedencia del contexto | el código de los 360 fragmentos de las 36 condiciones del piloto coincide con las líneas `start..end` del fichero en el `base_commit` (salvo espacios finales) |
| Rutas `File:` | las 360 son seguras y existen como fichero en el `base_commit` (solo lectura) |
| Respuesta E1 simulada (no del modelo) | copiar las 6 primeras líneas del primer fragmento como SEARCH da `patch_ready` en las 36 condiciones |

## Normalizador N (`normalizer.py`)

Única corrección posible: añadir `a/` (en `---`) y `b/` (en `+++`) cuando **todas** las cabeceras carecen de ellos. Puro, en
memoria, determinista e idempotente; conserva cada terminador de línea y el sufijo de las cabeceras (marcas de tiempo). No toca
hunks, contenido, contadores ni números de línea: solo cambian líneas `---`/`+++`, y solo por el prefijo. Los hunks se recorren
con sus contadores, de modo que una línea que parece cabecera dentro de un hunk es contenido.

| Estado | Cuándo | Efecto |
|---|---|---|
| `normalized` | todas las cabeceras sin prefijo y coherentes (`---` y `+++` con la misma ruta) | prefijos añadidos |
| `already_prefixed` | todas con `a/` `b/` (incluye `diff --git a/x b/x` coherente y altas con `b/`) | ninguno |
| `unchanged_mixed` | cabeceras con y sin prefijo | ninguno |
| `unchanged_git_headers` | `diff --git` no coherente con unas cabeceras ya prefijadas (p. ej. `---` sin prefijo) | ninguno |
| `unchanged_malformed` | hunk truncado, con línea no válida o que excede sus contadores | ninguno (no se reparan contadores) |
| `unchanged_no_headers` | no hay `---`/`+++` seguidas de un hunk | ninguno |
| `unchanged_unsupported` | rutas entre comillas, renombrados, borrado completo, `/dev/null` en ambos lados | ninguno |

Altas de fichero (`--- /dev/null`): solo se modifica `+++`. Como Git, N ignora las líneas sobrantes **después** de un hunk
completo (comprobado con `git apply`, que las tolera; p. ej. el parche de `ansible-7e1a…/hybrid`).

**Limitaciones.** (1) No repara contadores, cabeceras truncadas ni parches sin hunks: esos casos fallan igual que en el
original, así que `O1n` puede no corregir parches que un normalizador más agresivo habría arreglado; es deliberado para no
favorecer al brazo original. (2) Una ruta que empiece por un directorio real llamado `a` o `b` se trata como sin prefijo si
`---` y `+++` son iguales (`a/a/x.py`), pero un alta con `b/...` se interpreta como ya prefijada. (3) `unchanged_malformed` es
el juicio estructural de N (por contadores), no el de Git.

**Resultados sobre los 150 originales (solo lectura, en memoria):** `normalized` 49, `already_prefixed` 34,
`unchanged_malformed` 36, `unchanged_no_headers` 29, `unchanged_git_headers` 2; idempotente en todos. Coincide con el
diagnóstico de prefijos (93 sin prefijo: 49 normalizados, 30 malformados, 14 sin hunk, 2 con `diff --git` incoherente;
39 con `a/` `b/`; 17 sin cabeceras). De los 11 parches recuperables (los que Git acepta con `-p0`), **los 11 quedan
`normalized` y aplican con `-p1` dando el mismo fichero final** que con `-p0` (comprobación técnica en temporales, no es G).

## Selección de las 12 tareas (`select_tasks.py`, `data/task_selection.json`)

Regla del protocolo, sin cambios: 7 Verified + 3 Poly + 2 Pro de las 50 tareas de `results/final_tasks.csv`; dentro de cada
fuente se ordenan por `sha256("42:<original_inst_id>")` y se toman las primeras *n*. El hash de la lista es
`sha256("<ids unidos por salto de línea>")[:16]` con los **identificadores completos**, en el orden Verified, Poly, Pro, sin
salto final. **Resultado: `6dbd0c9f9365690c`, igual al del protocolo.** `check_selection` lanza `SelectionHashMismatch` si no
coincide: no hay sustitución silenciosa. Las 36 condiciones son estas 12 tareas × `bm25`, `semantic`, `hybrid`, y las 36 tienen
su `prompt.txt` original.

El manifiesto guarda solo lo necesario para reproducir: las 50 tareas con su fuente (campo `source` del dataset local
`Contextbench/ContextBench`, cache offline), la regla, el hash y la lista. Recalcular no necesita red ni el dataset
(`python -m pilot_p1.select_tasks --check`); `--write` no escribe si el hash no coincide ni sobrescribe.

## Pruebas de la fase 2 y resultados

Se añaden `test_prompts.py` (21), `test_normalizer.py` (32), `test_normalizer_known.py` (1) y `test_selection.py` (15).
**Suite completa: 208 pruebas, 208 superadas, 0 fallidas, 0 omitidas** (139 de la fase 1, que siguen pasando, + 69 de la fase 2; 0 fallos, 0 omitidas;
≈ 10 min). Las pruebas de la fase 2 comprueban, sobre las 150 condiciones originales: reconstrucción exacta de O1 (ida y vuelta
con `write_text`, `build_prompt` real del generador), contexto idéntico O1/E1 (hash del issue, de la parte compartida, del orden
y del código de cada fragmento), CRLF internos preservados (108 prompts), instrucciones E1 con SHA-256 fijado y aceptadas por el
parser y el aplicador; normalizador con casos positivos, negativos y de idempotencia, solo cambian cabeceras y 11/11 recuperables
equivalentes a `git apply -p0`; y la selección (hash `6dbd0c9f9365690c`, cuotas 7/3/2, regla de orden, manifiesto manipulado y
hash distinto rechazados).

## Problemas pendientes de la fase 2

1. ~~E1 no pedía crear ficheros~~ **Resuelto** (instrucción añadida, nuevo SHA-256, ver arriba). Queda como límite que el
   modelo debe declarar el fichero nuevo con SEARCH vacío; si no lo hace, E1 devolverá `file_not_found`.
2. **"Idéntico byte a byte al `prompt.txt` original" (protocolo 15.4)** se cumple respecto del prompt en memoria enviado al
   modelo, no respecto de los bytes del fichero guardado en Windows (traducción de saltos de línea). Es la interpretación
   pedida para esta fase; conviene reflejarla al revisar el protocolo.
3. El protocolo no fija la forma del identificador del hash de selección; se verificó con los identificadores completos.
4. `O1n` no repara contadores ni cabeceras truncadas (limitación 1 del normalizador). Se mantiene.
5. Los prompts nuevos deben guardarse con `serialize_prompt`/`write_bytes`; `write_text` volvería a traducir los saltos en Windows.
6. Sigue sin verificarse nada en Linux/Docker y no se ha comprobado la disponibilidad de modelo y API (no se hacen llamadas).
7. **Falta para la orquestación de las 72 generaciones** *(estado al cierre de la fase 2; la orquestación se implementó después en la 3A
   y el filtro G y la integración de la evaluación funcional en la 3B.1)*: módulo de generación (O1 y E1 por condición, consecutivos) con
   directorios de salida nuevos y lista blanca de rutas, reintentos solo para 429/503 y registro de modelo, fecha y hashes;
   filtro G y evaluación; control de integridad antes y después; y la aprobación del protocolo.

---

# Fase 3A: orquestación aislada de las 72 generaciones (solo simulacros)

**No se ha conectado ninguna API ni se ha ejecutado ninguna generación real.** Todo lo de esta fase se probó con un cliente
falso y respuestas sintéticas; los registros de esos simulacros llevan `synthetic: true`, viven en directorios `simulacro_*` y
nunca pueden confundirse con resultados experimentales. Aplica el protocolo congelado (`fb589c1`) sin cambiarlo.

> **Nota de lectura (coherencia histórica).** Esta sección describe el estado **al cierre de la fase 3A** (commit `b87abb2`). Las frases
> que presentan el filtro G y la evaluación funcional como «no existen todavía», «pendientes» o «no implementadas» (incluidos el valor
> `pending_phase_3B` de los registros y la lista «Limitaciones y puntos pendientes para la fase 3B») son **históricas**: ambas piezas se
> **implementaron después, en la fase 3B.1** (apartado siguiente), y se conservan aquí sin cambios como registro de lo que se verificó en 3A.
> La fase 3B.1 está implementada y probada con datos sintéticos y revisada; P1 no se ha ejecutado con generaciones reales y su
> protocolo sigue **pendiente de aprobación**.

## Arquitectura (`orchestrator.py`)

1. **Selección:** solo `data/task_selection.json` (recalculada y comprobada contra `6dbd0c9f9365690c`). 12 tareas × 3 métodos ×
   2 brazos = **72 condiciones**; para cada par (tarea, método) se ejecutan consecutivamente `O1` y luego `E1`.
   `cond_id = c<índice>-<sha8 de la tarea>-<método>-<brazo>`; `pair_id` es lo mismo sin el brazo.
2. **Prompts:** `prompts.py` (`build_o1`, `build_e1`) a partir de los `prompt.txt` originales (solo lectura). Antes de cualquier
   llamada se comprueba, para cada par, que O1 y E1 comparten issue, parte compartida, orden de fragmentos y K = 10; si no, se
   aborta.
3. **Cliente inyectable** (`client.py`): `GenerationClient.generate(prompt, model, max_output_tokens, thinking_level) →
   ClientResponse`. Solo existe `FakeClient`. El orquestador rechaza (`RealClientNotAllowed`) cualquier cliente sin
   `is_synthetic = True`; el cliente real será de la fase 3B, con autorización expresa.
4. **Etapas separadas**, cada una en su propio fichero: *generación* (`response.txt` + `generation.json`), *formato*
   (`format_metrics.json`), *conversión* de `E1` (`conversion.json`, `diff.patch`), *normalización* de `O1` (`normalization.json`,
   `o1.patch`, `o1n.patch`), *aplicabilidad* (filtro G) y *resolución funcional*: estas dos últimas **no existían al cierre de 3A** (se añadieron en 3B.1) y
   figuran como `pending_phase_3B`. `o1.patch` es la respuesta con el mismo tratamiento del generador original (`strip()` + salto
   final) y `o1n.patch` el resultado de N sobre ella; la respuesta original no se modifica nunca.
5. **Parámetros registrados** (manifiesto y `generation.json`): modelo `gemini-3.5-flash-lite`, 4096 tokens, razonamiento `minimal`,
   hasta 3 intentos de API (429/503, esperas de 10·n s como el original), fecha, versión del protocolo
   (`P1-frozen-fb589c1`), hashes de cada prompt, de las instrucciones O1 y E1 y de la selección.

## Esquema de directorios y registros

```
<salida>/simulacro_*/                  (o p1_run_* en una ejecución real)
  RUN_MANIFEST.json                    escrito una vez: protocolo, modelo, selección, 72 condiciones con hashes de prompt/contexto
  events.jsonl                         solo anadir; cada linea lleva el SHA-256 de la anterior (cadena)
  RUN.lock                             existe solo mientras se ejecuta
  conditions/<cond_id>/
    prompt.txt                         bytes exactos enviados (sin traducción de saltos de línea)
    response.txt                       respuesta original, byte a byte
    generation.json | generation_failed.json   sello (hashes, intentos, tokens, estado) o fallo de infraestructura
    format_metrics.json                vallas externas / internas y parseabilidad
    O1: normalization.json, o1.patch, o1n.patch      E1: conversion.json, diff.patch
```

Todo fichero se crea **una sola vez** (`write_new`: temporal + enlace exclusivo; si existe, `OverwriteError`). Eventos:
`run_started`, `prompt_written`, `api_attempt_started/failed`, `api_response_received` (con el hash de la respuesta y el uso),
`generation_sealed`, `stage_written`, `apply_infra_retry`, `condition_not_evaluable`, `run_resumed`, `interrupted_retry`.

## Aislamiento

`validate_output_dir` se ejecuta **antes de escribir**: la ruta debe ser absoluta; llamarse `simulacro_*` (sintético) o `p1_run_*`
(real); no ser el proyecto ni un ancestro; **dentro del proyecto solo se admite `pilot_p1_runs/<ejecución>`**; se prohíbe
`src/`, `repos/`, `results/`, `logs/`, `diagnostics/`, `docs/`, `external/`, `pilot_p1/` y cualquier árbol git; si existe, debe estar
vacía o ser una ejecución de P1 (con manifiesto). Los `run_id` empiezan por `p1-` (`p1-sim-…`), por lo que no reutilizan los de
la evaluación original. Del experimento original solo se lee (`prompt.txt`, `final_tasks.csv`, repositorios con `git ls-tree` /
`cat-file`). Las pruebas escriben solo en directorios temporales fuera del proyecto.

## Reanudación

`run()` es reanudable: si el directorio existe, **verifica antes de continuar** (manifiesto y su hash, cadena de eventos, hash de
cada prompt/respuesta/derivado frente a su sello, ficheros o directorios inesperados) y compara el manifiesto con la
configuración actual; cualquier incoherencia lanza `IntegrityError` y no se toca nada. Después, para cada condición:
- generación **sellada** → no se vuelve a llamar al modelo; solo se completan las etapas derivadas que falten (deterministas);
- `generation_failed.json` → condición ya declarada no evaluable; no se reintenta sola;
- `response.txt` sin sellar (caída entre ambos pasos) → se sella desde el evento `api_response_received` si el hash coincide;
- llamada iniciada sin respuesta guardada (caída durante la llamada) → `InterruptedConditionError`: **decisión manual** (un
  `on_interrupted="retry"` explícito vuelve a llamar y lo deja registrado), porque repetirla podría duplicar una generación;
- un bloqueo `RUN.lock` huérfano impide arrancar otra ejecución hasta que alguien lo revise.
`verify(recompute=True)` además recalcula las métricas de formato y la normalización y las compara con lo guardado. Un `*.tmp` de
una escritura interrumpida se avisa (warning) pero no bloquea.

## Política de reintentos y de errores

| Tipo | Ejemplos | Qué se hace | Cómo se registra |
|---|---|---|---|
| **Error de la salida del modelo** | `parse_error`, `search_not_found`, `ambiguous_match`, respuesta vacía… | **No se reintenta**; es el resultado de la condición | `category: model_output_error` |
| **Error de infraestructura recuperado** | git falla y luego funciona | Se reaplica **la misma respuesta**, hasta 3 intentos totales (`MAX_APPLY_ATTEMPTS`), sin regenerar | `attempts`, `recovered_after_retry`, evento `apply_infra_retry` |
| **Condición no evaluable por infraestructura** | `environment_error` persistente tras 3 intentos; API 429/503 agotada o error permanente | Se registra y **no se reintenta sola** | `category: infrastructure_not_evaluable`, evento `condition_not_evaluable`; el **par** queda excluido |

`summary()` informa por separado de errores del modelo, errores de infraestructura (intentos fallidos, reintentos, recuperados),
condiciones no evaluables y pares excluidos. **Decisión con exclusiones** (`decision.py`): un par con un brazo no evaluable se
excluye de la comparación pareada; **los umbrales no se reescalan** (se siguen midiendo sobre 36); si alguna forma de completar lo
que falta cambiase la decisión, el resultado es `inconclusive_by_infrastructure`. Se prueba con recuentos sintéticos (aún no hay
resultados del filtro G).

## Métricas de vallas Markdown (`format_metrics.py`)

Detección independiente del parser (solo marcadores de línea; no llama a `parse_edits` ni modifica la respuesta). Se registran **por
separado**: (1) **vallas externas** que envuelven o acompañan la respuesta (líneas que empiezan por ``` fuera de los bloques; en `O1`,
fuera de las líneas de contenido del diff); (2) **vallas internas**: secuencias ``` dentro del contenido de una edición (en `O1`, dentro
de líneas `+`/`-`/espacio); (3) **parseabilidad real** con el parser existente (solo `E1`). También `wraps_response` y
`fences_and_parseable` (vallas y parseable a la vez). Tres indicadores de vallas: **externas**, **internas** y su **unión**
(`fences_union_present`), que cubre la métrica original del protocolo (`original_metric_a_present`, línea que empieza por ```):
iguales cuando las vallas están al principio de línea; la unión solo es mayor con secuencias ``` a mitad de línea. La distinción es
solo de registro y **no altera la parseabilidad ni los umbrales**.

## Mejora neta y registro de victorias (`decision.py`)

Interpretación fijada el 12/11/2026, **antes de cualquier generación experimental** (no es un ajuste posterior a resultados):
«`E1` supera a `O1n` en ≥ 6 condiciones» = **mejora neta** = victorias de `E1` − victorias de `O1n` ≥ 6 (abandono si ≤ 2, con el resto de
reglas del protocolo sin cambios). Victoria de `E1`: `E1` aplicable y `O1n` no; victoria de `O1n`: al revés; empate: ambos aplicables o
ambos no aplicables. `evaluate()` devuelve siempre `pairwise` con victorias de cada brazo, empates (`ties_both_pass`,
`ties_both_fail`), `n_paired` y `net_improvement`, en total y por estrategia. Documentado en el protocolo (15.4).

## Pruebas y simulacros de la fase 3A

**Estado final de 3A — suite completa: 303 pruebas, 303 superadas, 0 fallidas, 0 omitidas** (≈ 11 min): 208 de las fases 1 y 2 (siguen
pasando) + 95 nuevas de la fase 3A: `test_format_metrics.py` 20, `test_decision.py` 20 y `test_orchestrator.py` 55 (condiciones 2,
simulacro completo 10, reanudación 6, detección de corrupción 14, no sobrescritura 2, errores 8, aislamiento 7, carpeta de
ejecuciones 3, interfaces 3). La fase 3A está **completada y commiteada** (`b87abb2`); *al cierre de 3A* la 3B (cliente real, filtro G, evaluación) no se había empezado:
el filtro G y la integración de la evaluación funcional se implementaron después en la 3B.1 (cliente real y evaluador oficial siguen pendientes).

**Simulacro de las 72 condiciones** (`FullSimulation`, prompts originales y repositorios reales en solo lectura, cliente falso,
respuestas sintéticas derivadas del primer fragmento, con variantes que deben conservarse: vallas Markdown, espacios y saltos
iniciales, CRLF):
- 72 llamadas en el orden previsto (par `O1`→`E1` consecutivo), con modelo, 4096 tokens y `minimal`; cada prompt enviado coincide con el
  registrado; ningún prompt se envía dos veces.
- Contexto idéntico en los 36 pares (hashes de issue, parte compartida, orden y K = 10) y prompts distintos solo en las instrucciones.
- Las 72 respuestas guardadas coinciden byte a byte con las devueltas por el cliente falso (también las que llevan vallas, CRLF o
  saltos iniciales).
- Conversión: 36 `E1` → `patch_ready`; normalización: 36 `O1` → `normalized`; 72 registros de formato; aplicabilidad y resolución
  figuraban como `pending_phase_3B` (al cierre de 3A; en 3B.1 pasaron a ser las etapas `applicability` y `functional`). Estos estados son consecuencia de la construcción sintética, **no un resultado**.
- `verify(recompute=True)` correcto sin avisos; todos los registros llevan `synthetic: true`; cadena de eventos íntegra.
- Resultados originales (`results/`, tamaños de `logs/downstream`) idénticos antes y después.

**Otras comprobaciones simuladas:** reanudación tras ejecución parcial y tras caída (sin duplicados: cada prompt se envía una vez);
recuperación de una respuesta guardada pero sin sellar; rechazo de la reanudación tras caída durante la llamada salvo `on_interrupted="retry"`;
detección de respuesta, prompt, sello, derivados, diff, manifiesto o eventos alterados o truncados, ficheros y directorios
inesperados, configuración incompatible y bloqueo huérfano; `write_new` no sobrescribe; errores 503/429 reintentados con esperas
10 y 20 s, error permanente sin reintento, respuestas vacías o `None` como error del modelo; conversión con fallos de entorno
recuperados en el tercer intento, persistentes (par excluido, no atribuido al modelo) y errores de salida sin reintento (una sola
aplicación por condición); cliente real rechazado; rutas de salida prohibidas rechazadas sin crear nada; constantes del cliente
iguales a las del generador original (leídas por AST) y ausencia de cualquier import de `google`.

## Limitaciones y puntos pendientes para la fase 3B *(estado al cierre de 3A)*

1. **Aplicabilidad (filtro G) y resolución funcional no implementadas** *(al cierre de 3A; implementadas después, en 3B.1, con datos
   sintéticos y evaluador falso)*; `decision.py` solo estaba probada con recuentos sintéticos.
2. **Ubicación de las salidas reales.** El protocolo 15.4 prevé `results/downstream_pilot_p1/` y `logs/downstream_pilot_p1/`, pero esta
   fase prohíbe escribir en `results/` y `logs/`; el orquestador solo admite `pilot_p1_runs/<ejecución>`, **adoptado como ubicación
   definitiva** (sustituye a las rutas previstas en el protocolo; documentado en 15.4) y añadido a `.gitignore`. Una prueba comprueba que
   Git la ignora y que solo esa carpeta es escribible dentro del proyecto.
3. ~~Definición de "supera en N condiciones"~~ **Resuelto**: mejora neta, documentada en el protocolo y registrada con victorias y empates.
4. ~~Métrica de vallas~~ **Resuelto**: tres indicadores (externas, internas, unión), documentados en el protocolo.
5. Una condición cuya **generación** falla por infraestructura queda excluida y no se reintenta; no hay todavía un mecanismo explícito
   para reintentarla de forma autorizada.
6. Un cliente real (Gemini) y su manejo de errores no existen; la lista de códigos reintentables se copia del generador original.
7. Sin comprobar en Linux/Docker; `RUN.lock` huérfano y `*.tmp` requieren revisión manual.

---

# Fase 3B.1: filtro común G e integración técnica de la evaluación funcional (sin ejecución real)

> **Estado: implementada y probada solo con datos sintéticos (364 pruebas superadas) y revisada; P1 no se ha ejecutado con generaciones
> reales y su protocolo sigue pendiente de aprobación.** No se ha ejecutado ninguna generación real, ni el
> evaluador oficial, ni se ha usado la red, ni se han instalado o descargado dependencias o repositorios. Nada de lo que sigue es un
> resultado del piloto P1. No se ha modificado el protocolo, sus umbrales ni los documentos generales.

## 1. Objetivos y alcance

**Incluido:** (a) el filtro común G (`gate.py`), con la misma política para `O1n` y `E1`; (b) las etapas `apply_gate()` y
`evaluate_functional()` del orquestador, con registros, verificación de integridad, reintentos y reanudación; (c) la interfaz de
evaluación funcional y un evaluador falso (`functional.py`); (d) la agregación por pares (`pair_results()`, `decision_report()`) hacia
`decision.py`; (e) los controles que impiden mezclar resultados sintéticos y reales o conectar por error el evaluador original.

**Fuera de alcance (3B.2 y posteriores):** cliente real de la API, adaptador del evaluador oficial, ejecución de G y de la evaluación
sobre salidas reales del modelo, verificación en Linux/Docker, aprobación y congelación del protocolo.

## 2. Filtro común G (`gate.py`)

- **Política única:** `git apply --check -p1 <parche>` en un directorio **temporal**. El árbol contiene una copia de los ficheros que el
  parche toca (rutas de `numstat` y de las cabeceras, incluidos los orígenes de renombrados) y de los antecesores que sean ficheros,
  leídos como blobs del `base_commit` con `git cat-file` (solo lectura; sin checkout). El parche se pasa **byte a byte, sin ninguna
  corrección adicional** (ni finales de línea, ni prefijos, ni espacios).
- **Mismo tratamiento para `O1n` y `E1`:** `gate_check(patch, source)` ni siquiera recibe el brazo; el orquestador la llama con los mismos
  argumentos para los dos (`o1n.patch` o `diff.patch`). Pruebas: la firma no contiene `arm`; bytes idénticos dan resultados idénticos; el
  parche de `E1` y el de `O1n` para la misma edición son ambos aplicables y producen el mismo fichero; un parche `O1` con CRLF o sin
  prefijos se rechaza con la misma severidad que se aplicaría a `E1`.
- **`E1` sin parche:** si la conversión no llegó a `patch_ready`, no hay nada que aplicar y la condición se registra `not_applicable`
  (motivo `conversion:<estado>`) sin ejecutar git; si la conversión fue infraestructura, se propaga como no evaluable. A `O1n` se le
  aplica G siempre (aunque `N` no reconozca un diff): git dará su veredicto. Es la consecuencia natural de que `O1` entrega un parche
  y `E1` no lo entrega cuando falla el formato.
- **Estados:** `applicable` (código 0); `not_applicable` (código 1, o 128/129 con un mensaje de rechazo de parche de
  `PATCH_REJECTION_MARKERS`; atribuible a la salida); `environment_error` (cualquier otro fallo de git, tiempo agotado, fuente ilegible,
  directorio de trabajo inseguro) → hasta 3 intentos totales con la misma entrada y, si persiste, `not_evaluable_infrastructure`.
- **Se registra:** comando (plantilla `git apply --check -p1 <patch_file>`), código de salida, stdout/stderr (recortados), detalle del
  error, duración, versión de git, rutas tocadas, hash del parche, intentos, motivo y artefacto de entrada.
- **Artefactos distintos y conservados** (`conditions/<cond_id>/`): `response.txt` (respuesta original), `o1.patch` (tratamiento del
  generador original), `o1n.patch` (normalizado por N), `diff.patch` (convertido de `E1`) y `applicability.json` (veredicto de G).
- **Aplicabilidad ≠ resolución:** G solo dice que git acepta el parche; no mide si arregla la tarea.

## 3. Evaluación funcional (`functional.py` y `orchestrator.evaluate_functional`)

- **Interfaz:** `FunctionalEvaluator.evaluate(EvalRequest) → EvalResponse` con `outcome` ∈ {`resolved`, `not_resolved`,
  `infrastructure_error`}, `evidence` (JSON) y `detail`. `EvalRequest` incluye condición, par, tarea, método, brazo, ruta y hash del parche,
  repositorio, `base_commit` y un `run_label` propio (`<run_id>-<cond_id>`, que empieza por `p1-`).
- **Solo se evalúan los parches que G aprobó.** Se registran `functional.json` (evaluador, versión, petición, resultado, intentos,
  hash de la aplicabilidad y de la evidencia) y `functional_evidence.json` (evidencia necesaria para reproducir; limitada a 200 KB).
- **Estados:** *pendiente* = parche aplicable sin `functional.json` (no se escribe un fichero «pendiente»: cada artefacto se crea una sola
  vez); *no aplicable* = G no lo aprobó (nunca se evalúa); `resolved` / `not_resolved`; `not_evaluable` (infraestructura).
- **Evaluadores:** solo `FakeFunctionalEvaluator` (sintético). `check_evaluator_allowed` rechaza evaluadores no sintéticos en una
  ejecución sintética, cualquier evaluador sintético en una real, módulos `src.*`/`swebench` y, en 3B.1, **toda** ejecución real.
- **Integración prevista del evaluador oficial (3B.2, no implementada):** un adaptador que implemente esta misma interfaz y se ejecute en
  un entorno aislado (ver los requisitos en el apartado 10); la evaluación funcional no tiene criterio de éxito ni de abandono en el
  protocolo y solo se describe.

## 4. Efectos secundarios del evaluador original y por qué no se usa

Revisado `src/downstream/evaluation.py`, `src/repo_manager.py` y los ejecutores de PolyBench y Pro (solo lectura):

| Efecto | Dónde | Consecuencia |
|---|---|---|
| `git clone`, **`git fetch origin`** y **`git checkout --force <base_commit>`** | `prepare_repository`, llamado al inicio de `evaluate_patch` | Usa la red y **modifica el árbol de trabajo y el HEAD** de los repositorios de `repos/` |
| `git apply --check` sobre el repositorio de trabajo | `check_patch_applies` | Depende del estado que dejó el checkout (CRLF/LF, `autocrlf`) |
| Descarga de datos | `load_task`, `load_swebench_dataset`, runners (`load_dataset`) | Red / caché de Hugging Face |
| `podman pull` | `ensure_podman_image` | Red; descarga imágenes |
| Contenedores | `docker.from_env()`, `run_instance`; Pro con `--use_local_docker --dockerhub_username` | Crea y borra contenedores; ejecuta código de los parches y de las pruebas; baja imágenes |
| Escritura en `logs/` | `logs/run_evaluation/<run_id>/…`, `logs/polybench/…`, `logs/probench/…` | Escribe en una zona prohibida |
| `run_id = downstream-<método>` fijo | `evaluate_patch` | **Colisiona** entre tareas y entre brazos de P1 y con los resultados originales: podría sobrescribirlos o mezclarlos |
| Parche global de `Path.write_text` y de `swe_run.cleanup_container` | `run_with_windows_podman_compatibility` | Cambia el comportamiento de todo el proceso mientras dura |
| Subprocesos con `.venv-polybench` y `external/SWE-bench_Pro` | `evaluate_poly_patch`, `evaluate_pro_patch` | Ejecutan código externo; escriben ficheros del evaluador |

**Conclusión:** no se puede garantizar su aislamiento tal cual, y por eso **no se invoca**. Cómo se evita que afecte al experimento:
ningún módulo de `pilot_p1/` importa `src`, `docker`, `swebench`, `google` ni librerías de red (comprobado por AST y en un subproceso),
ni llama a `prepare_repository`, `evaluate_patch`, `run_instance` o `check_patch_applies`; nunca se ejecuta `checkout`, `fetch`,
`clone`, `pull`, `reset`, `clean`, `add` ni `push`; `check_evaluator_allowed` impide conectar el evaluador original; y G solo actúa
sobre copias temporales.

## 5. Aislamiento y protección

- **Repositorios originales:** `GitSource` solo ejecuta `ls-tree` y `cat-file`; G trabaja en directorios temporales fuera del proyecto
  y de cualquier árbol git (`assert_safe_workdir`), con el entorno limpio de `GIT_DIR`/`GIT_WORK_TREE` y de la configuración global.
  Las pruebas comprueban que ninguna invocación usa como `cwd` un repositorio de `repos/` y que HEAD e índice no cambian.
- **Resultados y logs originales:** el orquestador solo escribe en `pilot_p1_runs/<ejecución>` (o un directorio `simulacro_*`/`p1_run_*`
  validado); se prohíben `src/`, `repos/`, `results/`, `logs/`, `diagnostics/` y `docs/`. Las pruebas comparan antes y después los hashes
  de `results/` y los tamaños de `logs/downstream`.
- **Artefactos de P1:** creación exclusiva (`write_new`), registro de eventos encadenado por hashes y `verify()` extendido: el parche de
  entrada de G coincide con su hash, `functional.json` solo existe para parches aprobados por G y evalúa exactamente ese parche, la
  evidencia coincide con su hash, el `run_label` es de P1 y **todo registro tiene el mismo `synthetic` que el manifiesto** (no se
  mezclan sintéticos y reales). `verify(recompute=True)` vuelve a ejecutar G y compara el veredicto.

## 6. Estados, errores, reintentos y reanudación

| Etapa | Estados | Error del modelo | Infraestructura |
|---|---|---|---|
| Aplicabilidad (G) | `applicable`, `not_applicable`, `not_evaluable_infrastructure` | `not_applicable` (no se reintenta) | `environment_error` ×3 → no evaluable; el **par se excluye** de la decisión |
| Funcional | `resolved`, `not_resolved`, `not_evaluable`, pendiente, no aplicable | — | `EvaluatorInfraError`/`infrastructure_error` ×3 → `not_evaluable`; **no** excluye el par (no tiene criterio de decisión) |

- **Reintentos:** hasta 3 intentos totales con la misma entrada, solo ante infraestructura; nunca se regenera ni se reaplica por un
  rechazo del parche.
- **Pausa:** si más del 25 % de las evaluaciones funcionales de parches aplicables terminan en infraestructura,
  `summary()["functional_infrastructure"]["pause_recommended"]` es verdadero (regla del protocolo; exactamente el 25 % no pausa).
- **Reanudación:** `apply_gate()` y `evaluate_functional()` verifican la integridad, saltan lo ya registrado (sin duplicados ni
  sobrescrituras) y retoman una evaluación interrumpida; un `RUN.lock` huérfano bloquea hasta que alguien lo revise.
- **Decisión:** `pair_results()` convierte G y el formato en `PairResult` (aplicable/no aplicable, `None` si no evaluable);
  `decision_report()` aplica `decision.py` (mejora neta, victorias, empates, exclusiones). Con datos sintéticos no es un resultado.

## 7. Pruebas realizadas

**Suite completa de `pilot_p1` (todas las fases): 364 pruebas, 364 superadas, 0 fallidas, 0 omitidas** (`Ran 364 tests … OK`, ≈ 32 min en
esta máquina, porque incluye los contrastes con repositorios reales en solo lectura). Son las 303 de las fases 1, 2 y 3A, que siguen
pasando, más **61 nuevas de 3B.1**: `test_gate.py` 19 y `test_functional.py` 42.

`test_gate.py` (19): parche válido (comando, código de salida, intentos, versión de git); contexto erróneo, corrupto, vacío y basura
(`not_applicable` sin reintentos); sin prefijos rechazado y, normalizado por N, aplicable; altas (también sobre un fichero existente);
fichero inexistente, conflicto de antecesor y renombrado; CRLF nativo (E1 aplicable; el mismo parche en LF, rechazado); bytes del parche
entregados sin modificar a git; la firma de `gate_check` no tiene brazo y bytes idénticos dan resultados idénticos; parche de `E1` y de
`O1n` para la misma edición, ambos aplicables y con el mismo fichero final; errores de infraestructura (fuente que falla 2 veces y se
recupera, fallo persistente = 3 intentos, tiempo agotado, git ausente, código 128 sin/con mensaje de rechazo); entorno sin `GIT_DIR` ni
configuración global; directorios de trabajo inseguros; rutas con `..` sin escribir fuera; equivalencia con un árbol completo en 8 casos;
y, **sobre repositorios y parches reales en solo lectura**, que `psf__requests-5414/hybrid` es rechazado tal cual y aceptado tras N y
`pytest-5809/bm25` es aceptado, sin ninguna invocación con `cwd` en `repos/` y con HEAD e índice intactos.

`test_functional.py` (42): *etapa G* (11): ambos brazos con artefactos distintos y veredictos registrados, mismas llamadas y argumentos,
veredictos iguales a una recomputación independiente, reanudación sin repetir ni sobrescribir, `E1` sin parche (git no se ejecuta),
CRLF rechazado sin correcciones, infraestructura recuperada y persistente (par excluido, no es error del modelo), sin reintentos ante
rechazos. *Evaluación funcional* (11): solo se evalúan los aprobados por G, registro completo (petición con `run_label` de P1, evidencia,
hashes), espera a G, misma forma de petición para los dos brazos, reanudación sin duplicados, reanudación tras una caída, reintentos con
recuperación, fallo persistente = `not_evaluable` sin excluir el par, umbral de pausa del 25 % (estricto), evaluadores no permitidos.
*Manipulación* (8): parche, veredicto, evaluación de otro parche, mezcla sintético/real, evidencia, etiqueta ajena a P1. *`strip()` original*
(2): ver el hallazgo del apartado 9. *Higiene* (5): imports y llamadas prohibidos por AST, git solo en comandos permitidos, importar el paquete
no carga `docker`/`swebench`/`google`/`src.downstream.evaluation`. *Simulacro completo con G* (5): 72 condiciones con prompts y repositorios reales
en solo lectura, respuestas y evaluador sintéticos: 36 `E1` aplicables y `O1` no aplicables solo en las respuestas con CRLF, evaluación solo de
los aplicables, `decision_report()` calculable con victorias, empates y mejora neta, y comparación antes/después de `results/`,
`logs/downstream` y del HEAD e índice de los 21 repositorios. **Los veredictos de ese simulacro se deducen de cómo se construyeron las
respuestas sintéticas: no son resultados del piloto.**

Comandos: `python -B -m unittest discover -s pilot_p1/tests -t .` (toda la suite) y `python -B -m unittest pilot_p1.tests.test_gate
pilot_p1.tests.test_functional` (solo 3B.1).

## 8. Reproducción (sin Internet ni credenciales)

Desde la raíz del repositorio, con Python 3 y `git` en el PATH; no se necesita API, red, Docker ni dependencias adicionales:

```bash
python -B -m unittest discover -s pilot_p1/tests -t .
```

Solo 3B.1: `python -B -m unittest pilot_p1.tests.test_gate pilot_p1.tests.test_functional`. `P1_SKIP_KNOWN=1` omite el contraste lento con
parches conocidos (fases 1 y 2). Las pruebas escriben únicamente en directorios temporales; de `repos/` y `logs/downstream` solo leen.

## 9. Decisiones técnicas y limitaciones

- **Árbol parcial en lugar de uno completo:** `git apply --check` solo necesita los ficheros tocados; una prueba compara el veredicto con el
  de un árbol completo (`git archive`) en 8 casos (válido, contexto, inexistente, alta, alta sobre existente, antecesor-fichero,
  sin prefijos, vacío) y coincide siempre.
- **Parche sin correcciones:** los originales se guardaron con CRLF por la traducción de `write_text` en Windows; P1 guarda bytes. G no
  convierte CRLF, así que un parche con CR que apunta a un fichero LF se rechaza (igual para los dos brazos); `E1` conserva el CRLF nativo
  de un fichero CRLF.
- **Lo que G no ve:** al ser `git apply --check`, no detecta, por ejemplo, un alta bajo un directorio que en realidad es un fichero (la
  conversión de `E1` lo rechaza antes con `unsafe_path`). Es la limitación del filtro del protocolo, no un defecto añadido.
- **Hallazgo — `strip()` del generador original:** el generador guarda `response.strip() + "\n"`; un diff cuyo último renglón sea una línea
  de contexto en blanco la pierde y queda con el hunk truncado (corrupto). `original_style_patch` reproduce ese tratamiento para `O1`
  (fidelidad) y N detecta el hunk truncado (`unchanged_malformed`) sin repararlo. Esto fue la causa del sexto parche `O1` no aplicable en el
  simulacro (las otras cinco eran respuestas con CRLF). No se ha cambiado nada; afecta solo a `O1`/`O1n` y conviene tenerlo presente al
  interpretar el brazo original.
- **Clasificación por código de salida:** 1, o 128/129 con mensajes de rechazo conocidos, es rechazo del parche; el resto es infraestructura.
  La lista de mensajes es una heurística acotada (`PATCH_REJECTION_MARKERS`).
- **Sin cliente real ni evaluador oficial:** todo el flujo se ha probado con clientes y evaluadores falsos.

## 10. Estado por categorías y trabajo pendiente para 3B.2

- **Implementado y verificado (con datos sintéticos, y en solo lectura sobre repositorios y prompts reales):** G, sus estados y
  reintentos; las etapas `apply_gate`/`evaluate_functional`; los registros, la verificación y la reanudación; la protección frente a
  mezclas sintético/real; el simulacro de 72 condiciones con respuestas sintéticas y evaluador falso.
- **Preparado, sin validar sobre tareas reales:** la interfaz de evaluación funcional y la regla de pausa del 25 %; el uso de G sobre
  salidas reales del modelo; `decision_report()` sobre datos reales.
- **Pendiente (3B.2):** (1) adaptador del evaluador oficial en un entorno aislado: copia de trabajo propia (no `repos/`), sin `fetch`/
  `checkout` sobre los originales, `run_id` único de P1, salida en `pilot_p1_runs/` (no `logs/`), sin parches globales, red/imágenes
  controladas y registro de versiones; (2) cliente real de la API y su política de errores; (3) revisar si G debe usar un árbol
  completo y el efecto del `strip()` original sobre `O1n`; (4) verificación en Linux/Docker; (5) aprobación y congelación del protocolo;
  (6) disponibilidad de modelo, API e imágenes. Nada de esto se ha hecho.

## 11. Construcción de los datos sintéticos (fases 3A y 3B.1) y su alcance

Explicación técnica de cómo se fabricaron los datos de los simulacros y las pruebas, para poder valorar su incorporación a la memoria.
Todo lo descrito está en el código; las referencias indican dónde.

**Qué es «sintético» aquí.** Cualquier dato que fabrica el banco de pruebas en lugar de proceder del LLM o del evaluador oficial: las
respuestas del «modelo», los veredictos funcionales, los errores de infraestructura y los mundos de juguete. Los registros de los
simulacros llevan `synthetic: true`, viven en directorios `simulacro_*` y el manifiesto lo advierte (`orchestrator.py`).

**Respuestas sintéticas de `O1` y `E1`** (`tests/sim_helpers.py`, `synthetic_text` y `variant`). Se fabrican a partir del **primer fragmento
de contexto del prompt real de cada condición** (`prompts.split_prompt`), no se escriben a mano condición a condición:
- `E1`: un bloque `FILE: <ruta del fragmento>` con `SEARCH` = las 6 primeras líneas del fragmento y `REPLACE` = esas mismas líneas más
  `# pilot-check`.
- `O1`: un diff unificado **sin prefijos `a/` `b/`** que reescribe una línea intermedia (`k = (n-1)//2`) y añade `# pilot-check`, con
  contexto antes y después y sin líneas en blanco finales (ver el hallazgo de `strip()` en el apartado 9).
- `variant` aplica de forma determinista, según `sha256(prompt)[:2] % 6`, una variación que debe conservarse byte a byte: vallas ```
  (valor 1), saltos de línea iniciales y espacios finales (2), CRLF (3); sin cambios en 0, 4 y 5. Las proporciones son arbitrarias.
- `Recorder` guarda lo devuelto y `fake_client()` lo entrega a `FakeClient` (`client.py`), de modo que se puede comparar con lo guardado.
Estas «ediciones» no intentan resolver la incidencia: solo añaden un comentario.

**Entradas reales, solo en lectura.** Las 12 tareas reales (`orchestrator.selection_from_manifest`, `data/task_selection.json`); los prompts
originales (`logs/downstream/<tarea>/<método>/prompt.txt`, vía `default_prompt_provider` y `prompts.py`); `final_tasks.csv` y los blobs
de `repos/` (`default_source_factory`, `GitSource`: solo `git ls-tree` y `git cat-file`); y algunos de los 150 parches originales
(`tests/test_normalizer.py`, `tests/test_normalizer_known.py`, y `OriginalRepositoriesAreOnlyRead` en `tests/test_gate.py`). El simulacro de 72
condiciones (`FullSimulation` en `tests/test_orchestrator.py` y `FullSimulationWithGate` en `tests/test_functional.py`) combina esas entradas reales
con las respuestas fabricadas. Los tests pequeños usan `SyntheticWorld` (`sim_helpers.py`): tareas inventadas `synth__task-<i>` y ficheros
`pkg/m<j>.py` con líneas `v<j>_<k> = <k>`, con prompts construidos con la plantilla real (`prompts.rebuild_shared`).

**Cómo se decide el resultado de G.** No hay una lista de casos que «deben pasar»: el veredicto lo da `git apply --check` real sobre el
parche construido, de modo que se deduce de la construcción. En el simulacro, `E1` es aplicable en las 36 condiciones (el `SEARCH` copia
líneas contiguas del fichero del `base_commit`; una prueba verifica que los 360 fragmentos coinciden con el fichero) y `O1` lo es salvo en
las respuestas con CRLF (5 de 36 en la ejecución realizada), que G rechaza sin correcciones; el test `test_verdicts_follow_from_the_synthetic_construction…`
calcula ese número desde las respuestas registradas. El oráculo independiente de G es `git apply --check` sobre un árbol completo
(`PartialTreeEquivalence`, `tests/test_gate.py`). El caso no previsto —un parche `O1` truncado por `strip()`— apareció al ejecutar el
simulacro, no se fijó de antemano.

**Evaluador funcional simulado** (`functional.py`, `FakeFunctionalEvaluator`; en los tests, `resolver` de `tests/test_functional.py`): devuelve
`resolved` si `int(patch_sha256[:2], 16) % 2 == 1` y `not_resolved` en otro caso. El veredicto está **determinado por el hash del parche**:
no ejecuta las pruebas oficiales ni depende de que el parche arregle nada.

**Errores de infraestructura inyectados a propósito:** respuestas `APIError` 503/429/400 programadas en `FakeClient`
(`tests/test_orchestrator.py`, clase `Errors`); una `source_factory` que lanza `SourceError` las primeras N veces o siempre (conversión y G);
`subprocess` simulado con tiempo agotado, git ausente o código 128 (`tests/test_gate.py`); un repositorio temporal con su objeto árbol
borrado (`tests/test_orchestrator.py`); y `EvaluatorInfraError`/`infrastructure_error` programados en el evaluador falso
(`tests/test_functional.py`).

**Qué verifican las 364 pruebas y qué no.** Verifican el comportamiento esperado de la infraestructura en los escenarios ensayados:
determinismo, mismo tratamiento de `O1n` y `E1` en G, aislamiento y protección de los datos originales, detección de manipulaciones,
reanudación sin duplicados ni sobrescrituras, y separación de estados y reintentos. **No demuestran mejoras de aplicabilidad ni de
resolución funcional**, ni dicen nada sobre la capacidad del LLM con cada formato, la tasa real de respuestas parseables, la equivalencia
con el evaluador oficial o el comportamiento en Linux/Docker; el 36/36 de `E1` es consecuencia de la construcción, y `decision_report()` con
estos datos no tiene significado experimental.

**Qué no ocurrió:** no hubo generaciones reales del LLM, ni llamadas a la API, ni ejecución del evaluador oficial.

---

# Fase 1: limitaciones pendientes

* No se puede añadir ni quitar el salto final de un fichero (el contraste omite hunks con `\ No newline`). Borrar la última
  línea de un fichero sin salto final deja la anterior con salto.
* No hay renombrados, borrados de fichero ni cambios de modo.
* Una línea de contenido que sea exactamente `=======` (p. ej. títulos RST) o un marcador no puede escribirse en un bloque.
* `patch_ready` significa que el diff se genera y aplica, no que resuelva la incidencia.
* **Sin verificar en Linux/Docker.** Las pruebas se ejecutaron solo en Windows (git 2.52, Python 3.14). Falta confirmar: los
  diffs (generados con `difflib`, que puede diferir de `git diff` y entre versiones de Python) y la aceptación por el
  comando de aplicación del evaluador real; `safe.directory`; symlinks reales (aquí la prueba usó una unión de directorios).
* La equivalencia con el filtro original (`check_patch_applies`) no está probada; aquí se usa el `git` local.
* El contraste usa solo parches que ya aplicaban, no salidas reales de un modelo con este formato.
* Un fichero nuevo con colisión de mayúsculas solo se detecta con la información de git/directorio de la fuente.

## Estado de la preparación técnica y trabajo pendiente para completar P1

**Fases técnicas implementadas** (herramientas y pruebas locales; ninguna es una ejecución experimental):

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Parser y aplicador SEARCH/REPLACE | Implementada, probada, commiteada (`e4342dd`) |
| 2 | Prompts O1/E1, normalizador N, selección determinista de las 12 tareas | Implementada, probada, commiteada (`f9d0c8d`) |
| Protocolo | Estados, métricas de formato, calendario y reglas de análisis | Versión técnica congelada (`fb589c1`); **aprobación definitiva pendiente** |
| 3A | Orquestación aislada de las 72 condiciones (cliente falso, simulacro sintético), vallas, decisión con exclusiones | Implementada, probada, commiteada (`b87abb2`) |
| 3B.1 | Filtro común G, etapas de aplicabilidad y de evaluación funcional, evaluador falso | **Implementada y probada con datos sintéticos (364 pruebas) y revisada; sin ejecución con generaciones reales** |

**Actividades experimentales todavía pendientes (no hechas, no autorizadas):**
- fase 3B.2: adaptador del evaluador oficial en un entorno aislado y cliente real de la API (apartado 10 de la 3B.1);
- generación real de las 72 condiciones (12 tareas × 3 métodos × 2 brazos);
- aplicación de G y evaluación funcional sobre las salidas reales del modelo, y análisis con la regla de decisión del protocolo;
- verificación en Linux/Docker, comprobación de modelo, API e imágenes, aprobación y congelación del protocolo, y ejecución.

*Texto original de este apartado (tras la fase 1, conservado como histórico):* «Instrucciones y prompts O1/E1, normalizador N, selección y
congelación de las 12 tareas, orquestación de las 72 generaciones con directorios de salida propios, filtro G, evaluación funcional y
análisis». De esa lista, todo lo técnico está ya implementado salvo lo indicado arriba; lo experimental sigue pendiente.
