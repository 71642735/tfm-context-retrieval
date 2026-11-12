# pilot_p1 — Fase técnica 1: conversor SEARCH/REPLACE → diff

> **Esta fase es una validación técnica, NO una ejecución experimental de P1.** No hay generaciones con LLM, ni llamadas
> a API, ni selección de tareas, ni evaluación funcional. Solo se ha implementado y validado en local el mecanismo que
> convierte instrucciones SEARCH/REPLACE en un diff. El protocolo P1 (D-005) sigue **sin aprobar**. Los resultados del
> experimento original (150 parches, `results/`, `repos/`) no se han tocado.

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
| `tests/` | Pruebas (`unittest`), fixtures y contraste con parches conocidos |
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
`P1_SKIP_KNOWN=1` omite el contraste con parches conocidos (~2,5 min). Duración total ≈ 4 min.

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

## Limitaciones pendientes

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
