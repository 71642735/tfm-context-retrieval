# pilot_p1 — Preparación técnica del piloto P1 (fases 1 y 2)

> **Ni la fase 1 ni la fase 2 son una ejecución experimental de P1.** No hay generaciones con LLM, ni llamadas a API, ni
> evaluación funcional, ni se ha ejecutado el filtro experimental G. La fase 1 (commit `e4342dd`) validó el conversor
> SEARCH/REPLACE → diff; la fase 2 prepara y valida los prompts O1/E1, el normalizador N y la selección
> determinista de las 12 tareas. El protocolo P1 (D-005) sigue **sin aprobar**. Los resultados del experimento original
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
7. **Falta para la orquestación de las 72 generaciones:** módulo de generación (O1 y E1 por condición, consecutivos) con
   directorios de salida nuevos y lista blanca de rutas, reintentos solo para 429/503 y registro de modelo, fecha y hashes;
   filtro G y evaluación; control de integridad antes y después; y la aprobación del protocolo.

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

## Pendiente para completar P1 (no hecho, no autorizado)

Instrucciones y prompts O1/E1, normalizador N, selección y congelación de las 12 tareas, orquestación de las 72
generaciones con directorios de salida propios, filtro G, evaluación funcional y análisis.
