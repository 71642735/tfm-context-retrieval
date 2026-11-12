# Diagnóstico de los parches no aplicables (evaluación downstream)

Documento de trabajo. Recoge la investigación realizada para entender por qué 141 de los 150 parches
generados por el LLM no se pueden aplicar, motivada por la corrección del director (entrega 2):
"el 94 % de los parches no se pueden aplicar… yo intentaría resolverlo antes de la entrega final".

**Convención de etiquetas**

| Etiqueta | Significado |
|---|---|
| **[ORIGINAL]** | Resultado del experimento tal y como se ejecutó y está en `results/` y `logs/`. No se ha tocado. |
| **[CONFIRMADO]** | Hecho comprobado en esta investigación leyendo datos o ejecutando una comprobación diagnóstica. |
| **[DIAGNÓSTICO]** | Resultado de una prueba diagnóstica nueva (no forma parte del experimento original). |
| **[HIPÓTESIS]** | Explicación plausible **no** verificada. |
| **[PENDIENTE]** | Prueba por hacer. |

Alcance: investigación de **solo lectura** sobre el proyecto. No se ha modificado el generador, el evaluador,
los parches, los repositorios (`repos/`) ni los resultados. No se han hecho llamadas al LLM ni pruebas funcionales.
Todos los artefactos de diagnóstico están en `diagnostics/downstream-patches/` (ver inventario, sección 10).

---

## 1. Objetivo y contexto del experimento original

**[ORIGINAL]** Experimento downstream: para cada una de las 50 tareas de la muestra y para cada estrategia
(BM25, UniXcoder/semantic, RRF/hybrid) se proporciona al LLM `gemini-3.5-flash-lite` la descripción de la
incidencia y los 10 chunks recuperados (K = 10). Una sola generación por condición (Pass@1), 4096 tokens de
salida, `thinking_level` minimal. Total: 150 condiciones.

- El prompt (`src/downstream/generation.py`, línea 81) pide únicamente: *"Return only a unified diff patch."*
  No se indica ninguna convención de rutas (`a/`, `b/`) ni se muestran números de línea de forma explícita.
- La respuesta se guarda sin postprocesado: `patch = response.text` → `patch.strip() + "\n"` →
  `patch_path.write_text(patch, encoding="utf-8")` (`generation.py:184-197`).
- Comprobación de aplicabilidad (`src/downstream/evaluation.py:132-164`, función `check_patch_applies`):
  `git -C <repo_root> apply --check <patch.diff>` (sin `-p`, es decir `-p1` por defecto). El stderr completo
  se guarda en el campo `detail`. `repo_root` es la carpeta de `repos/` preparada en el `base_commit`
  (`evaluation.py:598-626`).
- Si la comprobación falla, el estado es `invalid_patch` y no se llega a la evaluación funcional.

**[ORIGINAL] Cifras** (`results/downstream_results_final.jsonl`, 150 filas):

| Estado | Total | BM25 | UniXcoder | RRF |
|---|---|---|---|---|
| `invalid_patch` | **141** | 47 | 48 | 46 |
| `not_resolved` | **7** | 1 | 2 | 4 |
| `resolved` | **2** | 2 | 0 | 0 |

Los 9 parches aplicables (7 + 2) llegaron a la evaluación funcional oficial. Los 141 no.

## 2. Clasificación de los 141 parches inválidos

**[CONFIRMADO]** Clasificación por el mensaje de `git apply --check` conservado en `detail`
(script `classify_invalid_patches.py`; detalle por parche en `data/invalid_patches_classification.csv`):

| Causa | Casos | Mensaje típico de Git |
|---|---|---|
| Fichero inexistente | 45 | `error: _pytest/pastebin.py: No such file or directory` |
| Parche corrupto | 41 | `error: corrupt patch at line 20` |
| Sin diff válido | 24 | `error: No valid patches in input (allow with "--allow-empty")` |
| Contexto no coincide | 24 | `error: patch failed: src/transformers/generation/configuration_utils.py:N` |
| Fragmento sin cabecera | 7 | `error: patch fragment without header at line N: @@ -N,N +N,N @@` |

- **[CONFIRMADO]** Los 24 "sin diff válido" son respuestas de texto del modelo. Ejemplos revisados
  (`instance_ansible__ansible-39bd8b99…` semantic; `instance_internetarchive__openlibrary-e1e50298…` bm25):
  el modelo declara que el contexto recuperado no contiene el código necesario y no produce parche.
- **[HIPÓTESIS]** Esos 24 son fallos de recuperación (contexto insuficiente), no de formato. No se ha
  comprobado contra el gold context.
- **[CONFIRMADO]** Los 7 + 2 parches aplicables tienen cabeceras `--- a/…`; ninguno de los parches aplicables
  carece de prefijo (ver sección 3).
- **[CONFIRMADO]** Estructura de parche reconocible: **117 de 141** (83 %) según Git, de los cuales **112** tienen
  cabeceras de fichero completas y **5** las tienen defectuosas; los otros **24** no contienen diff. La cifra
  "113 de 141" de la auditoría original procede de otro criterio y queda sustituida. Ver la sección 2.1.

### 2.1 Criterios de "diff reconocible": 113 frente a 117

**[CONFIRMADO]** Durante la investigación aparecieron dos cifras para el mismo concepto. No es un error de cálculo:
son dos criterios distintos aplicados a los mismos 141 parches (verificado el 2026-11-11 leyendo los bytes de los
`patch.diff` sin alterarlos; la lectura en modo bytes y en modo texto da el mismo resultado).

| Cifra | Criterio | Origen |
|---|---|---|
| **113** (28 sin diff) | `"diff --git "` aparece en el texto **o** (`"--- "`, `"+++ "` y `"@@"` aparecen en cualquier parte del texto). Búsqueda de subcadenas, sin anclar a línea. | `src/downstream/analysis.py:188-191` (`analyze_invalid_patches`); registrada en `docs/experiment-log.md`, `docs/plan-trabajo-entrega3.md` y en la memoria v2.6 (sección 6.5) |
| **117** (24 sin diff) | Git reconoce estructura de parche: el error de `git apply --check` **no** es `No valid patches in input`. Para estos 141 parches equivale exactamente a tener una línea que empieza por `@@ -a,b +c,d @@`. | Esta investigación |

Los dos conjuntos comparten **112** parches y difieren en **6**: 1 solo en el criterio de 113 y 5 solo en el de 117
(113 − 1 + 5 = 117).

| Parche (tarea · estrategia) | Solo en | Qué ocurre | Mensaje de Git |
|---|---|---|---|
| `sphinx-doc__sphinx-8721` · semantic | 113 | Respuesta de texto del modelo que contiene las cadenas `--- `, `+++ ` y `@@` sueltas. **Falso positivo** de la heurística de subcadenas. | `error: No valid patches in input (allow with "--allow-empty")` |
| `instance_internetarchive__openlibrary-910b08570210509f3bcfebf35c093a48243fe754-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4` · hybrid | 117 | Dos líneas `---` seguidas, sin línea `+++`, y después un hunk válido. | `error: patch fragment without header at line 3: @@ -321,0 +322,96 @@?` |
| `instance_qutebrowser__qutebrowser-473a15f7908f2bb6d670b0e908ab34a28d8cf7e2-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d` · semantic | 117 | Igual (cabecera `---` duplicada, sin `+++`). | `error: patch fragment without header at line 3: @@ -1,3 +1,6 @@?` |
| `scikit-learn__scikit-learn-26323` · hybrid | 117 | Igual. | `error: patch fragment without header at line 3: @@ -1071,6 +1071,8 @@?` |
| `django__django-14373` · semantic | 117 | Igual. | `error: patch fragment without header at line 3: @@ -315,3 +315,3 @@?` |
| `sympy__sympy-17655` · bm25 | 117 | Igual. | `error: patch fragment without header at line 3: @@ -218,6 +218,8 @@?` |

Los cinco parches "solo en 117" son diffs con cuerpo válido pero con la cabecera de fichero defectuosa (el modelo
repite la línea `---` y omite `+++`). El criterio de 113 los dejó fuera porque exige la línea `+++`.

**Desglose adoptado de los 141 `invalid_patch`:**

| Categoría | Casos |
|---|---|
| Estructura de parche reconocible por Git | **117** (83 %) |
| &nbsp;&nbsp;con cabeceras `---` y `+++` completas | 112 |
| &nbsp;&nbsp;con cabeceras defectuosas (falta `+++`) | 5 |
| Sin diff (respuesta sin parche) | **24** (17 %) |

Los 24 sin diff coinciden con los 24 "sin diff válido" de la clasificación por causa (sección 2) y con los casos en
que Git responde `No valid patches in input`.

**Cuidado con otras cifras parecidas del diagnóstico**, que miden otra cosa: 17 parches sin ninguna línea `---`
(sección 3) y 28 sin diff según la heurística original (complemento de 113).

**Reproducción (solo lectura):** para cada `invalid_patch` de `results/downstream_results_final.jsonl`, leer
`logs/downstream/<tarea>/<estrategia>/patch.diff`. "Reconocible" = el campo `detail` no contiene
`No valid patches`; "cabeceras completas" = existen una línea `^--- \S` y una línea `^\+\+\+ \S` además de un hunk
`^@@ -\d+(,\d+)? \+\d+(,\d+)? @@`. Esta clasificación no está todavía en `classify_invalid_patches.py`.

## 3. Prefijos de ruta y comportamiento de `git apply -p1`

**[CONFIRMADO]** Distribución de las cabeceras `---` por estado (150 parches):

| Estado | Con prefijo `a/` | Sin prefijo | Sin cabeceras (texto) |
|---|---|---|---|
| `resolved` (2) | 2 | 0 | 0 |
| `not_resolved` (7) | 7 | 0 | 0 |
| `invalid_patch` (141) | 30 | **94** | 17 |

- **[CONFIRMADO]** Con `-p1` (valor por defecto), Git elimina el primer componente de cada ruta. Una cabecera
  `--- src/_pytest/pastebin.py` se interpreta como `_pytest/pastebin.py`, que no existe.
- **[CONFIRMADO]** Ejemplos reales de los 45 "fichero inexistente" (la ruta escrita por el modelo **sí existe**
  en el `base_commit`; la ruta que busca Git no):

| Tarea | Cabecera en `patch.diff` | Error de Git (completo) |
|---|---|---|
| `pytest-dev__pytest-5809` (semantic) | `--- src/_pytest/pastebin.py`, `--- testing/test_pastebin.py` | `error: _pytest/pastebin.py: No such file or directory` / `error: test_pastebin.py: No such file or directory` |
| `instance_ansible__ansible-39bd8b99ec8c6624207bf3556ac7f9626dad9173-v1055803c3a812189a1133297f7f5468579283f86` (bm25) | `--- lib/ansible/modules/async_wrapper.py` | `error: ansible/modules/async_wrapper.py: No such file or directory` |
| `scikit-learn__scikit-learn-13439` (bm25) | `--- sklearn/pipeline.py`, `--- sklearn/tests/test_pipeline.py` | `error: pipeline.py: No such file or directory` / `error: tests/test_pipeline.py: No such file or directory` |

- **[CONFIRMADO]** 44 de los 45 "fichero inexistente" corresponden a parches sin prefijo; 1 tiene prefijo `a/`.
- **[CONFIRMADO]** El prompt de cada tarea muestra las rutas como `File: src/_pytest/pastebin.py` (relativas a la raíz,
  sin prefijo). El modelo reproduce esa ruta.
- **[HIPÓTESIS]** Los 50 parches sin prefijo que fallan por otros motivos (corrupto, contexto…) pueden tener el
  prefijo como causa enmascarada, porque Git informa solo del primer error.

## 4. Comprobaciones con `git apply --check -p0`

Objetivo: medir cuántos de los 94 parches sin prefijo fallan **exclusivamente** por la interpretación de rutas.
Solo se ejecuta `git apply --check -p0` (no aplica nada).

**[DIAGNÓSTICO] Paso 1 – repo real.** Cada carpeta de `repos/` tiene un único `HEAD`, que coincide con el
`base_commit` solo de algunas tareas. Se ejecutó `-p0` directamente sobre el repo para los **39** parches cuya
tarea tiene el repo en su `base_commit` (sin `checkout`; `data/p0_check.json`). Para los otros **55** el commit
existe en local pero habría que hacer `checkout`, que modificaría `repos/`, así que no se ejecutó.

| Resultado (39) | Casos |
|---|---|
| Pasan | 3 |
| `corrupt patch` | 18 |
| `patch failed` (contexto) | 12 |
| Fragmento sin cabecera | 3 |
| Sin diff válido | 3 |

## 5. Reconstrucción temporal de archivos desde los commits originales

Para los 55 pendientes se reconstruyó una copia mínima fuera de `repos/`: por cada cabecera `---` del parche se
escribe, con `git show <base_commit>:<ruta>` (sin tocar el repo), el fichero de ese commit en un directorio
temporal, y se ejecuta allí `git apply --check -p0`. Los directorios temporales no se conservan (se regeneran
con los scripts). Rutas absolutas o con `..` se descartan (0 casos).

**[DIAGNÓSTICO] Primera versión (blobs en LF)** (`recon_check.py`, `data/p0_reconstruccion_94.json`):
resultado sobre los 94: **0 pasan** (43 contexto, 36 corruptos, 7 sin diff, 7 sin cabecera, 1 fichero inexistente).

**Validación de equivalencia.** Para saber si la reconstrucción equivale al repo real se reconstruyeron también
los 39 casos con repo real y se compararon. Resultado: **34/39** idénticos en estado y mensaje.
Discrepancias (`data/p0_reconstruccion_94.json`, `in_repo_head = true`):

| Tarea | Estrategia | Repo real | Reconstrucción LF |
|---|---|---|---|
| `instance_ansible__ansible-8127abbc298cabf04aaa89a478fc5e5e3432a6fc-…` | bm25 | pasa | `patch failed: lib/ansible/executor/process/worker.py:101` |
| `pylint-dev__pylint-4970` | hybrid | pasa | `patch failed: pylint/checkers/similar.py:800` |
| `scikit-learn__scikit-learn-14087` | hybrid | pasa | `patch failed: sklearn/linear_model/logistic.py:2191` |
| `instance_qutebrowser__qutebrowser-16de05407111ddd82fa12e54389d532362489da9-…` | bm25 | `patch failed: qutebrowser/config/configdata.py:3500` | `patch failed: qutebrowser/config/qtargs.py:147` |
| `pylint-dev__pylint-4970` | semantic | `patch failed: pylint/checkers/similar.py:801` | `patch failed: pylint/checkers/similar.py:801` (mensaje completo distinto) |

Con esto la reconstrucción LF **no** era equivalente (sección 6).

## 6. Diferencias LF/CRLF y efecto de `.gitattributes`

**[CONFIRMADO] Configuración del equipo.**
- `core.autocrlf=true` en la configuración **global** de Git (la del sistema, instalada con Git para Windows;
  consultable con `git config --show-origin --get core.autocrlf`). Ningún repo de `repos/` lo anula.
- `core.eol`, `core.safecrlf`, `apply.whitespace` y `apply.ignorewhitespace`: sin definir.
- Con `autocrlf=true`, los ficheros de texto se escriben en el árbol de trabajo con CRLF aunque el blob del commit
  esté en LF. En los 3 casos discrepantes, el árbol de trabajo tiene CRLF y el blob (`git show`) LF.
- 11 de los 19 repos cubiertos por los 39 casos con repo real tienen `.gitattributes` en el árbol de trabajo. `huggingface/transformers`
  fuerza `eol=lf` (se comprobó con `git check-attr` en `modeling_encoder_decoder.py`).

**[DIAGNÓSTICO] Comparación de variantes sobre los 39 casos con repo real** (`crlf_check.py`,
`data/crlf_validacion_39.json`):

| Variante de reconstrucción | Mismo estado | Mismo estado y mensaje |
|---|---|---|
| Blob del commit (LF) | 36/39 | 34/39 |
| Blob convertido siempre a CRLF | 38/39 | 38/39 |
| Bytes exactos del árbol de trabajo (control) | 39/39 | 39/39 |

La variante "siempre CRLF" falló en `huggingface__transformers-26752` (hybrid): se convirtió a CRLF un fichero
que `.gitattributes` mantiene en LF (reconstrucción da "pasa", el repo real da `patch failed`). Con la regla
corregida el fichero queda en LF.

**[CONFIRMADO] Interpretación de `.gitattributes` del `base_commit`** (`crlf_attr_check.py`): se usa
`git check-attr --source <base_commit> text eol -- <ruta>` (Git 2.52), no los atributos del `HEAD` actual.
Regla de conversión que reproduce `autocrlf=true`:
- `text` desactivado (`-text`) o contenido binario (NUL): sin conversión.
- `eol=lf`: LF.
- `eol=crlf`: CRLF.
- Resto (sin atributo, `text`, `text=auto`): CRLF, salvo que el blob ya contenga CR.

## 7. Validación de los 39 casos

**[DIAGNÓSTICO] Fase A** (`crlf_attr_check.py`, `data/faseA_39.json`):
- **39/39** coinciden con el repo real en estado y en mensaje completo de error.
- Los **46/46** ficheros reconstruidos son idénticos byte a byte al árbol de trabajo.

**[DIAGNÓSTICO] Fase B** (55 reconstruidos con el mismo procedimiento, `data/faseB_55.json`; 85 ficheros
convertidos a CRLF) y **consolidado de los 94 parches sin prefijo** con `-p0`:

| Categoría | 39 (repo real) | 55 (reconstruidos) | 94 |
|---|---|---|---|
| **Pasan con `-p0`** | 3 | 6 | **9** |
| Contexto no coincide (`patch failed`) | 12 | 22 | 34 |
| Corruptos (`corrupt patch`) | 18 | 18 | 36 |
| Fragmento sin cabecera | 3 | 4 | 7 |
| Sin diff válido | 3 | 4 | 7 |
| Otros (fichero inexistente) | 0 | 1 | 1 |
| Total | 39 | 55 | 94 |

- **Recuperados con `-p0`: 9 de 94 (≈ 9,6 %)**, equivalentes a 9 de los 141 `invalid_patch` (≈ 6,4 %).
- Pasar `git apply --check` **no** implica resolver la incidencia; no se ha ejecutado evaluación funcional.
- 2 de los 55 parches mencionan ficheros ausentes en el `base_commit`.

**[CONFIRMADO] Hallazgo adicional: los 150 `patch.diff` están en CRLF.** Se leyeron los bytes de los 150
archivos: todos usan `\r\n` y ninguno tiene líneas con `\n` puro (`classify_invalid_patches.py`).
- **[HIPÓTESIS]** Origen: `patch_path.write_text(patch, encoding="utf-8")` (`generation.py:194`) en Windows traduce
  `\n` a `\r\n` al escribir en modo texto.
- **[HIPÓTESIS]** Esto explicaría que los 9 parches recuperados solo pasen contra ficheros CRLF (la reconstrucción
  en LF dio 0 aplicables) y que parte de `corrupt patch` / `patch failed` sea un artefacto del guardado en Windows
  y no un error del modelo. No se ha comprobado.
- **[PENDIENTE]** No se ha verificado cómo recibe cada evaluador oficial (SWE-bench, SWE-PolyBench, SWE-bench Pro)
  el parche ni si lo normaliza antes de aplicarlo.

## 8. Limitaciones metodológicas y amenazas a la validez

1. **Entorno de pre-chequeo distinto al del evaluador oficial.** El `git apply --check` original se ejecutó en
   Windows con árboles de trabajo en CRLF. Los evaluadores oficiales corren en contenedores Linux con LF. El
   resultado "aplicable / no aplicable" del TFM puede no coincidir con el que daría el evaluador. Afecta a los
   141 `invalid_patch` (posibles falsos negativos o positivos) y no se ha medido su magnitud.
2. **Los 55 casos reconstruidos se validan por transferencia**, no directamente. El procedimiento reproduce los 39
   casos comprobables, pero los 55 no pueden contrastarse con el repo real sin `checkout`.
3. **Reconstrucción parcial.** Solo se escriben los ficheros de las cabeceras `---`. No se validan permisos,
   enlaces simbólicos, submódulos ni filtros de `.gitattributes` más allá de `text`/`eol`.
4. **La reconstrucción asume `autocrlf=true` y las reglas indicadas.** Equipos con otra configuración darían
   resultados distintos.
5. **Solo se analizan los 94 parches sin prefijo.** Los 30 con prefijo `a/` y los 17 sin cabeceras no se han
   probado con `-p0` ni con parches normalizados.
6. **`git apply --check` no mide corrección.** 9/94 son parches aplicables, no resueltos.
7. **Sesgo de selección en los 39.** Los 39 con repo real dependen de qué commit quedó en `HEAD`, no de un muestreo.
8. **Rutas absolutas en los scripts** (ver inventario): están tal y como se ejecutaron.
9. **No se ha confirmado la causa del CRLF en los parches** (hipótesis de `write_text`).

## 9. Comprobaciones pendientes y próximos pasos

Sin LLM ni cambios en el proyecto:

1. **[PENDIENTE]** Repetir la comprobación sobre los 141 `invalid_patch` con parches normalizados a LF y repos en
   LF (entorno Linux), con y sin prefijos: cuantifica el efecto CRLF.
2. **[PENDIENTE]** Leer cómo cada evaluador oficial recibe y aplica el parche (¿`git apply`, `patch -p1`,
   normaliza finales de línea?).
3. **[PENDIENTE]** Para los 24 "sin diff válido", comprobar si el gold context estaba en el contexto recuperado.
4. **[PENDIENTE]** Inspeccionar los 36 `corrupt patch` (conteos de línea de los hunks) y los 34 `patch failed`.
5. **[PENDIENTE]** Analizar los 30 con prefijo `a/` y los 17 sin cabeceras.

Con decisión del autor (requieren nuevas generaciones o cambios de código; no iniciados):

6. **[HIPÓTESIS / decisión]** El director propone un formato de edición más robusto (búsqueda y reemplazo, o
   función completa reescrita, convertido a parche por el pipeline), aplicado igual a las tres estrategias y
   justificado como corrección del formato de salida. Los errores de contenido (`corrupt patch` + `patch failed`
   = 70 de los 94 sin prefijo) apuntan a esta línea; no está probado.
7. **[Decisión]** Fijar la política de finales de línea al guardar los parches (`newline="\n"`) si se repite el
   experimento.
8. **[Decisión]** Actualizar la memoria: texto y cifras del capítulo de resultados, limitaciones (entorno de
   pre-chequeo) y la definición de "diff reconocible".

## 10. Inventario de archivos conservados

Carpeta: `diagnostics/downstream-patches/`.

- **JSON de `data/`:** se conservan **sin modificar**. Los generaron las **versiones iniciales** de los scripts, que
  usaban rutas absolutas de la carpeta temporal de la sesión.
- **Scripts de reconstrucción (`recon_check.py`, `crlf_check.py`, `crlf_attr_check.py`):** se **adaptaron antes de
  guardarlos en el repositorio** (2026-11-12). Cambios: localizan la raíz del proyecto automáticamente
  (primer directorio ascendente con `results/final_tasks.csv`), leen los datos de entrada de `data/`, escriben las
  salidas en `output/` (así **no sobrescriben** los JSON originales) y reconstruyen los ficheros en un directorio
  temporal del sistema que se borra al terminar. La lógica de las comprobaciones no cambia. La adaptación se revisó
  solo de forma **estática** (sintaxis y diff); **no se han vuelto a ejecutar** tras el cambio.
- **Orden de reproducción:** `recon_check.py` genera `output/p0_reconstruccion_94.json`; `crlf_check.py` y
  `crlf_attr_check.py` leen como entrada la versión original `data/p0_reconstruccion_94.json`.

| Archivo | Qué reproduce / contiene |
|---|---|
| `scripts/classify_invalid_patches.py` | Script de solo lectura con **rutas relativas** (ejecutar desde la raíz del proyecto). Reproduce: estado original por estrategia, clasificación de los 141 por causa, distribución de prefijos y finales de línea (CRLF) de los 150 `patch.diff`. Escribe `data/invalid_patches_classification.csv`. |
| `scripts/recon_check.py` | Reconstrucción en LF (blobs de `git show`) y `git apply --check -p0` de los 94 parches sin prefijo; validación frente a los 39 con repo real. Produce `p0_reconstruccion_94.json`. |
| `scripts/crlf_check.py` | Compara las variantes LF, CRLF (siempre) y bytes del árbol de trabajo en los 39 casos. Produce `crlf_validacion_39.json`. |
| `scripts/crlf_attr_check.py` | Versión final: usa `.gitattributes` del `base_commit` (`git check-attr --source`). Fase A: valida 39/39. Fase B: 55 reconstruidos y tabla consolidada de 94. Produce `faseA_39.json` y `faseB_55.json`. |
| `data/invalid_patches_classification.csv` | Una fila por condición (150): tarea, estrategia, estado, causa, prefijo, finales de línea y mensaje de Git completo (saltos de línea sustituidos por ` \| `). |
| `data/p0_check.json` | Primera comprobación `-p0` sobre los 39 casos con repo real en su `base_commit`. Se obtuvo con un fragmento en línea que **no se conservó como script**; el resultado equivalente (campos `ref_ok` / `ref_err`) está en `data/faseA_39.json`. |
| `data/p0_reconstruccion_94.json` | Reconstrucción LF de los 94 (los 39 con comparación frente al repo real). Incluye mensajes completos. |
| `data/crlf_validacion_39.json` | Comparación de variantes LF / CRLF / árbol de trabajo en los 39. |
| `data/faseA_39.json` | Validación final con `.gitattributes`: 39/39, mensaje del repo real y de la reconstrucción por caso. |
| `data/faseB_55.json` | Resultado individual y mensaje completo de Git de los 55 reconstruidos. |

Los datos originales del experimento no se han copiado ni modificado:
`results/downstream_results_final.jsonl`, `logs/downstream/<tarea>/<estrategia>/{patch.diff,prompt.txt,result.json}`
y `logs/run_evaluation/`.

**Nota sobre la ejecución:** los tres scripts de reconstrucción solo ejecutan `git show`, `git check-attr`,
`git rev-parse`, consultas de `git config` y `git apply --check` (sin escritura) sobre `repos/`; no hacen `checkout` ni modifican `repos/`,
`results/` ni `logs/`. Requieren que `repos/` contenga los repositorios y, para `crlf_check.py` y
`crlf_attr_check.py`, que cada repositorio siga en el commit de las 39 tareas comprobables.

## 11. Registro de decisiones

### D-001 · 2026-11-11 · Cifra de "parches con estructura de diff reconocible"

- **Decisión:** usar **117 de 141** (83 %) como número de `invalid_patch` con estructura de parche reconocible por
  Git, diferenciando **112** con cabeceras completas y **5** con cabeceras defectuosas. Los **24** restantes
  (17 %) no contienen diff.
- **Criterio adoptado:** Git reconoce estructura de parche (el error de `git apply --check` no es
  `No valid patches in input`). Es equivalente a la presencia de un hunk `@@ -a,b +c,d @@` anclado a inicio de línea.
- **Sustituye a:** la cifra 113 (28 sin diff) de la auditoría original (`analysis.py:188-191`).
- **Justificación:**
  1. La heurística original busca subcadenas sin anclar a línea y produjo un falso positivo
     (`sphinx-doc__sphinx-8721` · semantic, una respuesta de texto) y omitió cinco diffs con cabecera defectuosa.
  2. El criterio de Git no introduce una heurística propia: es el de la herramienta que decide la aplicabilidad.
  3. Es reproducible con los datos conservados y alinea esta cifra con la clasificación por causa
     (24 sin diff en ambas).
- **Casos discrepantes:** los seis de la sección 2.1.
- **Verificación previa:** leyendo los `patch.diff` en bytes y en texto, el criterio de Git y el de hunk con rangos
  dan el mismo conjunto (117); 112 tienen líneas `---` y `+++`, 5 no tienen `+++`, 24 no son diff.
- **Alcance:** es una corrección de la **clasificación descriptiva** de los `invalid_patch`. **No** cambia el estado de
  ninguna de las 150 condiciones (141 `invalid_patch`, 7 `not_resolved`, 2 `resolved`), ni los parches, ni
  `results/downstream_results_final.jsonl`.
- **No modificado (pendiente de decisión):** `src/downstream/analysis.py` (sigue calculando 113),
  `docs/experiment-log.md` (se conserva el registro histórico y se añade una nota de corrección) y la memoria v2.6,
  cuya sección 6.5 ("113 de los 141…") deberá actualizarse a 117, con 24 sin diff, y el texto asociado
  ("no garantiza…") se mantiene.
- **Formulación propuesta para la memoria:** "De los 141 parches no aplicables, 117 (83 %) contienen una estructura
  de parche reconocible por Git y 24 (17 %) son respuestas sin diff. Que un parche tenga un formato identificable no
  garantiza que pueda aplicarse."

## 12. Fase 2: influencia de los finales de línea y de los prefijos de ruta (diseño propuesto)

**Estado (2026-11-12): DISEÑO PROPUESTO, NO EJECUTADO.** Esta sección documenta el porqué y el cómo antes de
ejecutar nada. No modifica ni sustituye las secciones 1-11, que se conservan como registro de lo ya hecho.

### 12.1 Motivación científica

El objetivo no es "arreglar" los 141 parches, sino **distinguir los errores de generación del modelo de los efectos
introducidos por el entorno de evaluación** (formato en el que se guardó el parche, configuración de Git del equipo,
sistema operativo). Mientras no se separen, atribuir un `invalid_patch` al LLM puede ser incorrecto, y atribuirlo al
entorno también. Afecta a tres aspectos del TFM:

| Aspecto | Qué se persigue | Cómo lo atiende este diseño |
|---|---|---|
| **Reproducibilidad** | Documentar las condiciones necesarias para repetir las comprobaciones y entender por qué dos entornos dan resultados distintos. | Se fijan versiones y configuración (Git, `autocrlf`, `.gitattributes` del `base_commit`), se versionan los scripts y se registra cada celda con su mensaje de Git completo. |
| **Validez experimental** | No atribuir automáticamente al modelo errores que pueden depender del formato del parche, de la configuración de Git o del sistema operativo. | Se separan factores (finales de línea del parche, del árbol y nivel `-p`) en una comparación controlada, con controles positivos y negativos. |
| **Trazabilidad** | Conservar resultados originales, hipótesis, comprobaciones posteriores y límites de cada conclusión. | Las hipótesis se fijan **antes** de ejecutar (12.4), los resultados originales no se tocan y las salidas nuevas no sobrescriben nada. |

### 12.2 Principios que acotan lo que se puede concluir

1. **Los resultados originales no se modifican.** Los estados de las 150 condiciones, los `patch.diff` y
   `results/downstream_results_final.jsonl` son la evidencia; la fase 2 solo añade lecturas sobre ellos.
2. **Normalizar un parche no demuestra que el modelo haya resuelto la tarea.** Un parche que pase una comprobación
   tras normalizarse sigue sin haber sido evaluado funcionalmente.
3. **Que `git apply --check` funcione en una reconstrucción local no garantiza que el evaluador oficial lo acepte.**
   Los evaluadores aplican de otra forma (12.3) y corren en otro entorno.
4. **Probar parches LF sobre archivos LF es una prueba de sensibilidad, no una reproducción demostrada del entorno
   oficial Linux/Docker.** No hay forma local de verificar esa equivalencia sin ejecutar el contenedor real.
5. **Se separan siempre hechos observados, hipótesis y conclusiones todavía no sostenibles** (etiquetas de la
   cabecera del documento y tabla 12.8).

### 12.3 Hecho nuevo que motiva el diseño: cómo aplican el parche los evaluadores oficiales

**[INSPECCIÓN DE CÓDIGO]** (el código se ha **leído**; **no** se ha ejecutado ni verificado en un contenedor).
Según ese código, los tres evaluadores corren en contenedores Linux y usan `-p1` (explícito en `patch`; valor por
defecto en `git apply`), pero con estrategias distintas:

| Fuente (tareas de la muestra) | Estrategia de aplicación | Referencia |
|---|---|---|
| SWE-bench Verified (29) | `git apply --verbose`; si falla `--3way`; si falla `--reject`; si falla `patch --batch --forward --fuzz=5 -p1` | `.venv/Lib/site-packages/swebench/harness/run_evaluation.py:54-59` |
| SWE-PolyBench (12) | `git apply -v --ignore-whitespace --reject`; si falla `patch --batch --fuzz=5 -p1 -f` | `external/SWE-PolyBench/src/poly_bench_evaluation/docker_utils.py:243-250` |
| SWE-bench Pro (9) | un único `git apply -v` (estricto) | `external/SWE-bench_Pro/swe_bench_pro_eval.py:120` |

**Consecuencias** (derivadas de lo anterior):
- **[INSPECCIÓN DE CÓDIGO]** El pre-chequeo del TFM (`git apply --check`, `evaluation.py:132-164`) es, según el
  código leído, **más estricto** que SWE-bench y PolyBench, que prueban alternativas con tolerancia
  (`--ignore-whitespace`, `--fuzz=5`). Los parches rechazados por el pre-chequeo no llegaron a esas alternativas.
  **No se ha ejecutado** ningún evaluador sobre estos parches para comprobar que aceptarían alguno de ellos.
- **[INSPECCIÓN + INFERENCIA]** Todos los evaluadores leídos usan `-p1`; de ahí se infiere que un parche sin prefijos
  `a/` `b/` fallaría también en ellos. Lo que **sí está verificado por ejecución** es el comportamiento de
  `git apply -p1` en este equipo: elimina el primer componente de la ruta (44 de los 45 "fichero inexistente",
  sección 3). `-p0` **no** es un comportamiento del evaluador: es una lente para medir cuántos parches se salvarían
  si el pipeline normalizara las rutas.
- **[PENDIENTE]** Confirmar que `src/downstream/probench_runner.py` usa el camino de `swe_bench_pro_eval.py:120`, y
  qué ocurre realmente dentro de los contenedores (no hay ejecución de referencia).

### 12.4 Hipótesis fijadas antes de ejecutar

Se registran ahora para no racionalizar después de ver los datos.

- **H1 [HIPÓTESIS]** El prefijo de ruta explica los fallos de "fichero inexistente" (44 de 45) y poco más.
  Referencia previa: con `-p0`, parche CRLF y árbol CRLF, pasan 9 de 94 (sección 7).
- **H2 [HIPÓTESIS]** Parte de los fallos `patch failed` (contexto que no coincide) es un artefacto del CRLF añadido
  al guardar el parche (`write_text`, `generation.py:194`). Si es cierta, un parche normalizado a LF sobre un árbol LF
  debería aplicarse en más casos que el parche CRLF original sobre un árbol LF. **No se anticipa ninguna cifra.**
- **H3 [HIPÓTESIS]** Los 24 sin diff y los 5 con cabecera defectuosa **no cambian** en ninguna combinación. Los
  `corrupt patch` tampoco deberían cambiar mayoritariamente: la comprobación previa de conteos de hunk (heurística,
  solo lectura) encuentra al menos un hunk con conteo incoherente en 32 de los 41, y un CR final no altera el recuento
  de líneas. Por eso H2 **no** se aplica a `corrupt patch` (corrección respecto de la primera versión de esta sección).

**Observaciones anteriores (no son resultados anticipados).** Estas cifras ya existían y solo sirven de contexto.
- **Observación O-1 (sección 5, `data/p0_reconstruccion_94.json`):** 0 de 94 parches pasaron `git apply --check -p0`
  en la **primera versión de la reconstrucción**, cuyas condiciones fueron exactamente: los **94 parches sin prefijo**;
  árbol reconstruido con los blobs del `base_commit` **en LF** y solo los ficheros de las cabeceras `---`; **parche
  original en CRLF**; **`-p0`**; ejecución fuera de cualquier repositorio; sin regla de finales de línea ni
  `.gitattributes`. En esa misma ejecución, 3 de los 39 casos comparables con el repositorio real dieron resultado
  distinto (el repo real pasaba y la reconstrucción no), de modo que esa reconstrucción **no** se consideró equivalente
  al repo real. No debe leerse como un valor de referencia para la fase 2, ni como "el resultado esperable en LF".
- **Observación O-2 (sección 7):** con árbol CRLF (regla validada 39/39), parche CRLF y `-p0`, pasaron 9 de 94.
- **Observación O-3 (lectura de los 150 `patch.diff`, solo lectura):** ninguno contiene `\r\r\n` ni `\r` aislado. Es
  coherente con que todos los `\r` procedan de la escritura en modo texto (H2), pero no lo demuestra: solo descarta
  que el contenido del parche incluyera CR propios visibles.

### 12.5 Diseño experimental

**Población.** Los 150 `patch.diff`. El análisis principal se hace sobre los 141 `invalid_patch`; los 9 aplicables
sirven de control. Estructura de los 141 (sección 3): 30 con prefijo `a/`, 94 sin prefijo, 17 sin cabeceras. Los 24
sin diff se marcan aparte como control negativo (no coinciden exactamente con los 17 sin cabeceras).

**Factores (diseño factorial 2 × 2 × 2 = 8 celdas por parche, 1 200 comprobaciones):**

| Factor | Niveles | Qué representa |
|---|---|---|
| Finales de línea del **parche** | CRLF original · LF normalizado (copia en memoria) | Efecto del guardado en Windows |
| Nivel **`-p`** | `-p1` · `-p0` | Interpretación de las rutas |
| Finales de línea del **árbol** | CRLF (smudge de `autocrlf=true`) · LF | CRLF = entorno donde se hizo el pre-chequeo original. LF = condición de **sensibilidad** inspirada en que, según el código leído, los evaluadores corren en Linux; **no se afirma equivalencia** con el entorno oficial (principio 4) |

**`-p` natural.** Cada parche tiene un `-p` según sus cabeceras reales: `-p1` si son `--- a/…` / `+++ b/…`; `-p0` si
no llevan prefijo; sin `-p` natural si no hay cabeceras. El análisis principal solo usa el `-p` natural. Las celdas
cruzadas (`-p0` sobre `a/`, `-p1` sobre sin prefijo) son **controles**, no efectos a interpretar.

**Reconstrucción (todas temporales y fuera de cualquier repositorio):**
- Se escriben los ficheros que resultan de aplicar `-p0` y `-p1` a las rutas de las cabeceras `---`, `+++` y
  `diff --git` y que existen en el `base_commit`, leídos en binario con `git cat-file blob` (sin filtros). Es una
  ampliación respecto de las reconstrucciones anteriores (solo `---` y `-p0`): permite que `-p1` sobre un parche sin
  prefijo busque la misma ruta que el repo real y que se detecten ficheros nuevos que ya existen. Como cambia el
  procedimiento validado, la línea base sobre los 150 parches lo revalida.
- Árbol CRLF: regla ya validada 39/39 (sección 7), con `git check-attr --source <base_commit> text eol`.
- Árbol LF: el blob tal cual, salvo `eol=crlf` explícito (se contarán los casos).
- Parche LF: sustitución de `\r\n` por `\n` en memoria; nunca sobre `patch.diff`.

**Puerta de comprobación.** `git apply --check` (mismo criterio que el original, para poder comparar). Cada celda se
clasifica por el mensaje de Git con las mismas categorías de la sección 2 (fichero inexistente, corrupto, contexto,
fragmento sin cabecera, sin diff, aplica).

**Configuración de Git (decisión 2026-11-12).** La matriz principal se ejecuta con `core.autocrlf=true` explícito
(`-c`) y con la configuración global y de sistema **aisladas**, para no depender de la máquina. Aparte, como **réplica
de robustez claramente separada** (ficheros de salida propios), las 4 celdas de árbol LF se repiten con
`core.autocrlf=false`. Diferencias conocidas con el entorno original (árbol parcial, ejecución fuera de un
repositorio, configuración aislada, finales de línea emulados, `LC_ALL=C`) se registran en el `manifest.json` de cada
ejecución; ninguna implica equivalencia con Linux/Docker.

**Controles (si fallan, se detiene la ejecución y se informa):**
1. *Línea base:* `-p1` + parche CRLF + árbol CRLF debe reproducir el **resultado original de `git apply --check`**
   de los 150 parches (aplica / no aplica y, si falla, el mensaje guardado en `detail`). Se compara con eso y **no**
   con el estado final del evaluador (`resolved`, `not_resolved`, `invalid_patch`). Extiende la validación de 39/39 a
   los 150 parches. Si no se reproduce, el script **se detiene y genera un informe de discrepancias**; no cambia
   automáticamente de configuración.
2. Los 9 parches aplicables siguen aplicándose en esa celda.
3. Los 24 sin diff fallan en las 8 celdas.
4. Las celdas cruzadas de `-p` fallan con "No such file".

**Extensión opcional ("como el evaluador"): fuera de esta fase, NO se implementa por ahora (decisión 2026-11-12).**
Se conserva descrita solo como línea futura. Segunda pasada solo con `--dry-run` según la
fuente de cada tarea (12.3): Verified (`git apply --check` o `patch --dry-run --forward --fuzz=5 -p1`), Poly
(`git apply --check --ignore-whitespace` o `patch --dry-run --fuzz=5 -p1`), Pro (`git apply --check` estricto), y con
los parches sin prefijo reescritos a `a/` `b/` en memoria para simular una corrección del pipeline. Se omiten
`--3way` y `--reject` porque escriben. Acota el límite inferior de aplicabilidad; no lo elimina.

### 12.6 Cómo se garantiza que no se modifica nada

- Solo operaciones de lectura: `git show`, `git check-attr --source`, `git cat-file -e`, `git rev-parse` y
  `git apply --check`, con `git --no-optional-locks`. Sin `checkout`, `worktree`, `--reject` ni `--3way`.
- Antes y después de la ejecución se comparan: SHA-256 de los 150 `patch.diff` y de
  `results/downstream_results_final.jsonl`, `HEAD` de cada repositorio de `repos/` y SHA-256 de su `.git/index`.
- Las salidas se escriben solo en `diagnostics/downstream-patches/output/` (ignorado por Git). Tras la revisión
  humana se promueven a `data/` **con nombres nuevos**, sin sobrescribir ningún JSON existente.
- Ninguna llamada al LLM.

### 12.7 Por qué cada decisión metodológica

| Decisión | Por qué |
|---|---|
| Solo lectura sobre repos y resultados | La evidencia original es el objeto de estudio; modificarla impediría saber qué se midió. |
| Reconstruir con `git show` en un directorio temporal, sin `checkout` | Cada carpeta de `repos/` tiene un único `HEAD`; cambiar de commit modificaría el estado compartido y, además, el árbol de trabajo depende de la configuración de esta máquina. |
| Añadir el factor "finales de línea del árbol" | Si solo variase el parche, el efecto quedaría confundido con el entorno: el pre-chequeo original se hizo con árboles CRLF y, según el código leído, los evaluadores corren en Linux, donde cabe esperar árboles LF (no verificado por ejecución). |
| Usar el `-p` natural y tratar las celdas cruzadas como control | `-p` no es un parámetro libre: es la forma en que el evaluador interpreta las cabeceras. Aplicar `-p0` a un parche con `a/` o `-p1` a uno sin prefijo no mide nada útil; sí sirve para comprobar que la reconstrucción falla donde debe. |
| Normalizar el parche solo en memoria | `patch.diff` es evidencia; la normalización es un experimento mental ("¿y si no se hubiera guardado con CRLF?"), no una corrección del resultado. |
| Control de línea base sobre los 150 parches | Una reconstrucción que no reproduce lo ya observado no permite interpretar las demás celdas. Se amplía lo validado hasta ahora (39/39). |
| Controles negativos (24 sin diff, celdas cruzadas) | Demuestran que la prueba no "aplica todo": si un control falla en el sentido contrario, se detiene el análisis. |
| Fijar hipótesis y categorías antes de ejecutar | Evita elegir después la explicación que mejor encaja con los números. |
| Mantener `git apply --check` como puerta principal | Permite comparar con el original en igualdad de condiciones. La emulación de cada evaluador va aparte porque difiere por fuente y usa operaciones que no se pueden simular sin escribir. |
| Análisis descriptivo, sin contrastes estadísticos | La comprobación es determinista y las tres estrategias de una misma tarea no son independientes; lo informativo son las transiciones por parche entre celdas. |
| Salidas en `output/` y promoción posterior a `data/` | Separa lo generado de lo revisado y evita sobrescribir artefactos ya versionados. |

### 12.8 Qué se podrá y qué no se podrá concluir

| Resultado posible | Se podrá afirmar | No se podrá afirmar |
|---|---|---|
| La normalización LF + árbol LF aumenta mucho los parches que aplican | El pre-chequeo original es sensible a los finales de línea; parte de los fallos son compatibles con un artefacto del guardado (H2). | Que el evaluador oficial los habría aceptado, ni que resuelvan la incidencia. |
| No cambia casi nada | Los finales de línea no son el factor principal bajo este criterio de aplicación; los fallos dependen del contenido del diff. | Que el modelo sea el único responsable: el prompt y el formato de salida también intervienen. |
| Con `-p0` mejoran los sin prefijo y el resto no | El prefijo explica una parte acotada y medible (H1). | Que corregirlo en el pipeline equivalga a una evaluación válida sin repetir la generación. |
| Hay parches que solo se aplican con tolerancia (`--ignore-whitespace`, `--fuzz`) | El pre-chequeo infraestimó la aplicabilidad en Verified o Poly. | Cuántos se habrían resuelto. |
| Algún control falla | La reconstrucción no es fiable y no se interpretan las demás celdas. | Nada sobre los factores. |

### 12.9 Limitaciones

1. **[HIPÓTESIS]** No se conoce la salida cruda del modelo: "parche LF" es la suposición de que `write_text` añadió
   los `\r` (los 150 `patch.diff` están en CRLF puro).
2. `git apply --check` no es el evaluador: es más estricto que SWE-bench y PolyBench y no reproduce sus alternativas
   salvo en la extensión opcional.
3. El primer error enmascara a los demás: una causa corregida puede dejar ver otra. Las categorías son por celda, no
   aditivas.
4. El árbol LF no tiene oráculo local: solo se puede validar por analogía con el árbol CRLF.
5. Reconstrucción parcial (solo ficheros de las cabeceras `---`): no se prueban permisos ni enlaces simbólicos; hay 3
   parches con ficheros ausentes en el `base_commit`.
6. El árbol CRLF depende de `core.autocrlf` de esta máquina.
7. Aplicable no es resuelto; no se ejecutan pruebas funcionales.
8. Las 150 condiciones repiten tareas y no son una muestra independiente.
9. Los grupos "sin cabeceras" (17) y "sin diff" (24) se definen con criterios distintos y se tratan por separado.

### 12.10 Registro de resultados (cuando se ejecute)

- **Script nuevo:** `diagnostics/downstream-patches/scripts/eol_prefix_matrix.py`, con la misma convención de rutas
  relativas que los demás.
- **Datos por parche y celda (JSON):** tarea, estrategia, fuente, `-p` natural, factores, resultado, categoría y
  mensaje de Git completo. Más un CSV resumen.
- **Tablas:** por celda (aplican y causa de fallo), transiciones respecto de la línea base y desglose por grupo de
  prefijo y por fuente.
- **Documentación:** resultados en esta sección (con etiquetas hecho / hipótesis / pendiente), registro D-002 y
  preguntas nuevas en `docs/defensa-tfm-preguntas.md`.

### D-002 · 2026-11-12 · Fase 2 de diagnóstico (finales de línea × prefijos)

- **Decisión propuesta:** ejecutar la comparación 2 × 2 × 2 descrita en 12.5, con los controles de 12.5 y las
  salvaguardas de 12.6.
- **Estado:** diseño general aprobado (2026-11-12) con la matriz 2 × 2 × 2 (finales de línea del parche, del árbol y
  `-p0`/`-p1`); la extensión "como el evaluador" queda fuera de esta fase; el script `eol_prefix_matrix.py` está
  implementado (`diagnostics/downstream-patches/scripts/eol_prefix_matrix.py`, v1.0) y revisado solo de forma
  estática; **no se ha ejecutado**. Pendiente: autorización para ejecutar el piloto y, después, la matriz completa.
- **Motivo:** separar errores de generación de efectos del entorno de evaluación (12.1).
- **Alcance:** no cambia ningún estado original, parche ni resultado, y no repite generaciones del LLM.

## 13. Resultados de la fase 2: inspección de código, piloto y línea base completa

**Estado (2026-11-12).** Se han ejecutado la inspección de código, el **piloto de 7 parches** y la **línea base de los
150 parches**. La matriz completa y la réplica de robustez completas **no** se han ejecutado. Todo lo de esta sección
son **pruebas diagnósticas posteriores**, distintas de los resultados originales del TFM, que no cambian (141
`invalid_patch`, 7 `not_resolved`, 2 `resolved`). Los resultados del piloto **no se extrapolan** a los 150 parches.

### 13.1 Inspección de código: cómo entrega el pipeline el parche a cada evaluador

**[INSPECCIÓN DE CÓDIGO]** (solo lectura; no se ha ejecutado ningún evaluador oficial).

| Etapa | Qué recibe | Cómo | Referencia |
|---|---|---|---|
| Filtro previo del pipeline | El **fichero original** `patch.diff` (CRLF) | `git -C <repo> apply --check <ruta>` sin `-p` (es decir, `-p1`) sobre el repo local de Windows. Solo si pasa se llama al evaluador | `evaluation.py:132-164`, `610-647` |
| SWE-bench Verified | Una **copia en memoria** | `patch_path.read_text(encoding="utf-8")` → `model_patch`. El arnés escribe el parche con `Path.write_text` modificado para usar `newline="\n"`. Aplicación: `git apply --verbose`; si falla `--3way`; si falla `--reject`; si falla `patch --batch --forward --fuzz=5 -p1` | `evaluation.py:96-115`, `671-679`; `swebench/harness/run_evaluation.py:54-59` |
| SWE-PolyBench | Una copia (cadena en un JSON de predicciones) | `read_text(encoding="utf-8")`. Aplicación: `git apply -v --ignore-whitespace --reject`; si falla `patch --batch --fuzz=5 -p1 -f` | `polybench_runner.py:47-58`; `external/SWE-PolyBench/.../docker_utils.py:243-250` |
| SWE-bench Pro | Una copia (cadena en un JSON de predicciones) | `read_text(encoding="utf-8")`; el runner adapta la escritura del espacio de trabajo para usar LF. Aplicación: un único `git apply -v`, sin alternativa | `probench_runner.py:13-56`, `113-127`; `external/SWE-bench_Pro/swe_bench_pro_eval.py:120` |

**Verificado por ejecución (solo lectura):** los 150 `patch.diff` contienen CRLF en bytes, pero al leerlos con
`read_text(encoding="utf-8")` (como hacen los tres runners) **ninguno conserva un CR** (0 de 150). Es decir, según el
código, los evaluadores reciben el parche **ya con finales de línea LF**, no el fichero original en CRLF.

**Diferencias entre el filtro original, los evaluadores y este diagnóstico:**

| Aspecto | Filtro original del TFM | Evaluadores (según código) | Diagnóstico fase 2 |
|---|---|---|---|
| Parche | Fichero original, CRLF | Copia con LF | Original (CRLF) y normalizado (LF) |
| Árbol | Repo de Windows, CRLF (`autocrlf=true`) | Contenedor Linux, LF (**no verificado**) | CRLF y LF, ambos emulados |
| Aplicación | `git apply --check` | Verified: 4 intentos; PolyBench: 2 (con `--ignore-whitespace`); Pro: 1 estricto | Solo `git apply --check` |
| `-p` | 1 (por defecto) | 1 | 0 y 1 |

La celda del diagnóstico más parecida a lo que recibe el evaluador es **parche LF + árbol LF con `-p1`**, pero sigue
sin tener sus alternativas (`--3way`, `--ignore-whitespace`, `patch --fuzz`); por tanto **no** es equivalente.
**[HIPÓTESIS]** El problema del CRLF del parche guardado no llega a los evaluadores, pero el filtro previo, que
trabajaba con el fichero CRLF, sí pudo discrepar de lo que habría aceptado el evaluador; no se ha cuantificado.

### 13.2 Piloto de 7 parches

- **Fecha, comando y ubicación:** ejecutado el 2026-11-11 a las 23:41 UTC (nombre del directorio de salida) con
  `python -I diagnostics/downstream-patches/scripts/eol_prefix_matrix.py --pilot --run`. Resultados en
  `diagnostics/downstream-patches/output/eol_prefix_matrix_20261111T234137Z_piloto/` (ignorado por Git: `cells.jsonl`,
  `cells_robustez_autocrlf_false.jsonl`, `controls.json`, `manifest.json`, resúmenes CSV y `run.log`). Código de
  salida 0.
- **Selección de los 7 parches y por qué** (5 explícitos, 2 por regla):

| Parche · método | Estado original | Motivo |
|---|---|---|
| `pytest-dev__pytest-5809` · semantic | `invalid_patch` | Sin prefijo; "fichero inexistente" por `-p1` (caso base de H1) |
| `instance_ansible__ansible-39bd8b99…` · bm25 | `invalid_patch` | Sin prefijo, ruta larga, repositorio con `.gitattributes` |
| `instance_ansible__ansible-39bd8b99…` · semantic | `invalid_patch` | Respuesta sin diff: control negativo |
| `pylint-dev__pylint-4970` · hybrid | `invalid_patch` | Pasó `-p0` en el repo real (observación O-2) |
| `huggingface__transformers-26752` · hybrid | `invalid_patch` | Fichero con `eol=lf` en `.gitattributes` |
| `astropy__astropy-14598` · bm25 | `invalid_patch` | Primero con `a/` y `b/` por regla; `patch failed` |
| `psf__requests-5414` · bm25 | `resolved` | Primer aplicable `resolved` por regla; control |

- **Comprobaciones realizadas: 84** = 7 de línea base + 49 del resto de la matriz principal (`autocrlf=true`) + 28 de
  la réplica de robustez (`autocrlf=false`, solo árboles LF). Casos no evaluables: **0**.
- **Línea base reproducida en 7/7:** mismo resultado de `git apply --check` y mismo mensaje que el original (no se
  compara con el estado final del evaluador). Controles: línea base 7/7; el aplicable de control aplica; el parche sin
  diff falla en las 12 celdas; las 24 celdas cruzadas de `-p` fallan con "fichero inexistente".
- **Integridad:** sin cambios en los 150 `patch.diff`, `results/downstream_results_final.jsonl` ni
  `results/final_tasks.csv`, ni en `HEAD` e índices Git de los 6 repositorios usados (comprobado por el script y de
  forma independiente).

**Resultados por condición** (solo celda del `-p` natural de cada parche; primera letra: parche original **C**RLF o
normalizado **L**F; segunda letra: árbol CRLF o LF; `autocrlf=true`). *Solo describe estos 7 parches.*

| Parche · método | CC | LC | CL | LL |
|---|---|---|---|---|
| pytest-5809 · semantic (`-p0`) | contexto | contexto | contexto | contexto |
| ansible-39bd8b99 · bm25 (`-p0`) | **aplica** | **aplica** | contexto | **aplica** |
| pylint-4970 · hybrid (`-p0`) | **aplica** | **aplica** | contexto | **aplica** |
| transformers-26752 · hybrid (`-p0`) | contexto | **aplica** | contexto | **aplica** |
| astropy-14598 · bm25 (`-p1`) | contexto | contexto | contexto | contexto |
| requests-5414 · bm25 (`-p1`) | **aplica** | **aplica** | contexto | **aplica** |
| ansible-39bd8b99 · semantic (sin diff) | sin diff | sin diff | sin diff | sin diff |

Recuento sobre los 6 parches con `-p` natural: CC 3, LC 4, **CL 0**, LL 4. Entre los 5 `invalid_patch` con `-p`
natural: CC 2, LC 3, CL 0, LL 3; con la configuración original (`-p1`, CC) ninguno de esos 5 aplicaba. Con `-p1`, los 4
parches sin prefijo siguen fallando por "fichero inexistente" en las 4 combinaciones. **Réplica de robustez:** las 28
celdas con `autocrlf=false` dan el mismo resultado y el mismo mensaje que con `autocrlf=true` sobre árbol LF.

**Aplicabilidad no es resolución.** Esta tabla mide únicamente si `git apply --check` acepta el parche. Solo
`requests-5414` tiene resolución funcional original (`resolved`); los demás eran `invalid_patch` y no llegaron a la
evaluación funcional, de modo que aunque ahora apliquen en alguna celda **no se sabe si resolverían la incidencia**.

**Hallazgos confirmados (solo en este piloto):**
- Con su `-p` natural, 2 de los 5 `invalid_patch` pasan de no aplicar a aplicar.
- Con el parche original (CRLF) el resultado depende del árbol: aplica contra CRLF y falla por contexto contra LF; con
  el parche normalizado (LF) el resultado es el mismo en ambos árboles.
- `pytest-5809` y `astropy-14598` fallan por contexto en las 4 celdas: ese fallo no depende de los finales de línea.
- En `transformers-26752` el fichero conserva LF en ambos árboles (`eol=lf`); el parche CRLF falla y el LF aplica.
- El parche `resolved` (`requests-5414`) falla en CL (parche CRLF contra árbol LF) pese a que el evaluador oficial lo
  aceptó. Con 13.1 resulta coherente con que el evaluador reciba el parche en LF; indica que **CL no representa al
  evaluador**.

**Hipótesis pendientes:**
- **[HIPÓTESIS]** El CRLF de los `patch.diff` procede de `write_text` (`generation.py:194`).
- **[HIPÓTESIS]** Que el parche LF aplique sobre un árbol CRLF sugiere que `git apply` convierte finales de línea por
  sí mismo; la réplica de robustez solo cubre árboles LF, así que no se ha probado.
- **[PENDIENTE]** Cuántos de los 141 cambian de resultado en las celdas más cercanas al evaluador.

**Limitaciones del piloto:** 7 parches no aleatorios; ningún `corrupt_patch`, ningún parche mixto ni fichero nuevo; sin
equivalencia con Linux/Docker (el árbol LF es una prueba de sensibilidad); `git apply --check` no incluye las
alternativas de los evaluadores; el parche LF es una suposición sobre la salida cruda del modelo.

### 13.3 Línea base completa de los 150 parches

- **Fecha, comando y ubicación:** 2026-11-11 a las 23:47 UTC (nombre del directorio),
  `python -I diagnostics/downstream-patches/scripts/eol_prefix_matrix.py --only-baseline --run`, resultados en
  `diagnostics/downstream-patches/output/eol_prefix_matrix_20261111T234743Z/` (ignorado por Git). Código de salida 0. No se ejecutaron
  la matriz principal restante ni la réplica de robustez.
- **Resultado: 150 de 150 reproducen exactamente** el resultado original de `git apply --check` (aplica o no, y el
  mensaje completo de Git de los 141 que fallaban). **Discrepancias: 0.** Casos no evaluables: 0.
- Categorías reproducidas en los 141: 45 fichero inexistente, 41 `corrupt_patch`, 24 sin diff, 24 contexto, 7 fragmento
  sin cabecera. Los 9 aplicables originales aplican (9 de 9). Se comprobó también por separado, comparando mensajes
  normalizados contra `detail`.
- **Integridad:** sin cambios en los 150 `patch.diff`, el `.jsonl`, el `.csv` ni en `HEAD` e índices de los 20
  repositorios (script y comprobación independiente). No quedan temporales.
- **Alcance:** valida la reconstrucción como réplica del **filtro original** (parche CRLF, árbol CRLF, `-p1`,
  `autocrlf=true`). **No** valida la reconstrucción LF ni el entorno Linux/Docker. Que 133 parches tengan algún fichero
  candidato ausente en el commit es esperado (se prueban rutas con `-p0` y `-p1`, por ejemplo `a/x`) y no es una
  anomalía.

### 13.4 Incidencia en el registro de configuración Git del `manifest.json`

- **Qué ocurre:** `config_git_aislada(usada)` lista el `.git/config` del repositorio del proyecto (que incluye la URL
  de su remoto), no la configuración efectiva del directorio temporal.
- **Causa [CONFIRMADO por código y por el contenido del manifest]:** las dos llamadas de las líneas 504-505 de
  `eol_prefix_matrix.py` ejecutan `git config --list --show-origin` sin `cwd`, de modo que heredan el directorio del
  proyecto, que es un repositorio. El aislamiento de la configuración global y de sistema sí funciona: el listado
  "aislado" solo tiene el origen `.git/config`, y el "real" tiene `.git/config`, `~/.gitconfig` y el `gitconfig` del
  sistema.
- **Impacto:** exclusivamente de **registro**. Las comprobaciones `git apply --check` se ejecutan con `cwd` en un
  directorio temporal fuera de cualquier repositorio (línea 388), donde no se lee ninguna configuración local; los
  resultados de la línea base (150/150) y del piloto no dependen de ese listado.
- **Corrección mínima propuesta (no implementada):** pasar `cwd=tmp_root` en ambas llamadas y registrar además
  `git -c core.autocrlf=<valor> config --get core.autocrlf` desde ese mismo directorio. Pendiente de autorización.
- **Actualización (2026-11-12):** la corrección se ha implementado en la versión 1.1 del script; el texto anterior
  describe el estado previo, que se conserva. Ver la nota de trazabilidad de D-003.

### 13.5 Qué implica para los 141 `invalid_patch` y próximos pasos

- **[CONFIRMADO]** Los 141 son reproducibles como resultado del **filtro previo tal como se ejecutó** (parche CRLF,
  árbol CRLF, `-p1`, `git apply --check`).
- **[INSPECCIÓN DE CÓDIGO]** Ese filtro no coincide con el camino de evaluación: los evaluadores reciben el parche en
  LF, corren en Linux y usan alternativas de aplicación. Por tanto `invalid_patch` significa "no aplicable según el
  filtro del TFM", **no** "el evaluador oficial lo habría rechazado", y tampoco "el modelo se equivocó". El problema de
  prefijos sí apunta en la misma dirección en el filtro y en los evaluadores (todos usan `-p1`), pero esto es una
  inferencia.
- **[PENDIENTE]** Cuantificar cuántos de los 141 aplican en las celdas más cercanas al evaluador (LL con `-p1` y con su
  `-p` natural). Es lo que mediría la matriz completa.
- **Próximos pasos (todos con autorización previa):** (1) corregir el registro del manifest; (2) ejecutar la matriz
  completa una vez (1 200 celdas principales y 600 de robustez); (3) documentar resultados y actualizar las preguntas
  de defensa; (4) decidir qué se lleva a la memoria y si procede la Fase 2 del plan (formato de edición alternativo).

### D-003 · 2026-11-12 · Ejecución del piloto y de la línea base completa

- **Decisión:** ejecutar el piloto de 7 parches y la línea base de 150 antes de la matriz completa; la línea base se
  compara con el resultado original de `git apply --check`, no con el estado final del evaluador.
- **Resultado:** piloto 7/7 sin discrepancias y línea base 150/150 sin discrepancias; integridad intacta.
- **No cambia:** ningún estado original, parche ni resultado experimental.
- **Pendiente de autorización:** corrección mínima del manifest y matriz completa.

- **Nota de trazabilidad (2026-11-12): corrección del registro de configuración Git (`eol_prefix_matrix.py` v1.1).**
  - **Problema:** `config_git_aislada(usada)` del `manifest.json` listaba el `.git/config` del repositorio del
    proyecto (incluida la URL de su remoto) en lugar de la configuración del directorio temporal, porque
    `git config --list` se ejecutaba sin `cwd` y heredaba el directorio del proyecto (sección 13.4).
  - **Modificación (solo registro):** la configuración de Git se consulta ahora con `cwd` en el directorio temporal,
    fuera de cualquier repositorio, y solo con las claves relevantes (`core.autocrlf`, `core.eol`, `core.safecrlf`,
    `core.whitespace`, `core.ignorecase`, `core.symlinks`, `core.longpaths`, `core.filemode`, `apply.*`); el directorio
    personal se sustituye por `~`. El manifest registra de forma explícita el `core.autocrlf` **efectivo** de la matriz
    principal (`true`) y de la réplica de robustez (`false`). Una comprobación previa detiene la ejecución (código 4) si
    el valor efectivo no es el previsto o si el registro contuviera datos no deseados (`remote.`, `github.com`,
    `user.*`, `.git/config`). Se amplía la lista blanca de `git config` con la lectura `--get-regexp`. Versión
    1.0 → 1.1 y `manifest_esquema: 2`.
  - **Por qué no afecta a los resultados:** las comprobaciones `git apply --check` se ejecutan con `cwd` en el árbol
    temporal, fuera de cualquier repositorio, donde no se lee ninguna configuración local; el listado erróneo era solo
    un registro paralelo. No cambian la reconstrucción, las transformaciones CRLF/LF, las opciones de `git apply` ni los
    criterios de comparación. Los resultados del piloto (7 parches, 84 comprobaciones) y de la línea base de 150
    (150/150) no se ven afectados ni se han vuelto a ejecutar.
  - **Manifiestos históricos:** los `manifest.json` del piloto y de la línea base de 150 (esquema 1) se **conservan sin
    modificar**; los nuevos llevan `manifest_esquema: 2` y una nota que explica la diferencia.
  - **Verificación:** revisión estática y 20 pruebas sintéticas (lista blanca de Git, saneado del directorio
    personal, valor efectivo de `autocrlf`, ausencia de `.git/config` y del remoto en el registro, reproducción del
    fallo de la versión 1.0). Se validará con la próxima ejecución real.
  - **Pendiente de autorización:** la matriz completa (1 200 celdas principales y 600 de robustez).

## 14. Resultados de la matriz completa (ejecución del 2026-11-12)

**Estado.** Matriz principal (1 200 celdas) y réplica de robustez (600 celdas) ejecutadas **una sola vez** sobre los 150
parches. Es una prueba diagnóstica de **aplicabilidad** (`git apply --check`), distinta de los resultados originales del
TFM, que no cambian (141 `invalid_patch`, 7 `not_resolved`, 2 `resolved`). **No mide resolución funcional** ni equivale a la
aceptación del evaluador oficial.

### 14.1 Ejecución, controles e integridad

- **Comando y ubicación:** `python -I diagnostics/downstream-patches/scripts/eol_prefix_matrix.py --run`, script v1.2
  (v1.1 corrigió el registro de configuración; v1.2 endureció la lista blanca de `git config`, sin cambios de lógica).
  Salida en `diagnostics/downstream-patches/output/eol_prefix_matrix_20261112T000024Z/` (ignorado por Git; incluye
  `cells.jsonl`, `cells_robustez_autocrlf_false.jsonl`, `controls.json`, `manifest.json` y los CSV). Análisis descriptivo
  con `scripts/analyze_eol_prefix_matrix.py` (`analisis.md` y `analisis.json` en esa carpeta). Código de salida 0.
- **Validación de configuración del manifest:** `core.autocrlf` efectivo `true` en la matriz principal y `false` en la
  réplica; el listado de configuración visible para `git apply` está vacío. El manifest (esquema 2) no contiene el remoto
  ni datos de usuario; la cadena `.git/config` solo aparece en la nota que explica el fallo de registro del esquema 1.
- **Controles:** línea base **150/150** (resultado y mensaje originales de `git apply --check`); los 9 aplicables
  originales aplican; las 24 respuestas sin diff no aplican en ninguna celda; 0 celdas no evaluables.
- **Control 4 (celdas con `-p` cruzado deben fallar):** 528 celdas, 524 fallan. Las **4 que aplican** son un único parche
  (`instance_ansible__ansible-7e1a3476…` · RRF, `not_resolved`) cuyas cabeceras son `--- /dev/null` y
  `+++ b/lib/…`: solo **crea un fichero nuevo**, no hay fichero previo que buscar y `-p0` y `-p1` lo aceptan. No es un
  fallo de la reconstrucción; es una limitación de la prueba para parches que solo crean ficheros.
- **Integridad:** sin cambios en los 150 `patch.diff`, `results/downstream_results_final.jsonl`, `results/final_tasks.csv`,
  ni en `HEAD` e índices de los 20 repositorios (script y comprobación independiente). Los manifiestos históricos del
  piloto y de la línea base de 150 se conservan sin modificar.
- **Evidencia versionada:** `output/` no se versiona, así que los ficheros imprescindibles de esta ejecución se copiaron,
  idénticos (SHA-256 comprobado) y sin tocar el original, a
  `diagnostics/downstream-patches/data/matriz_completa_20261112T000024Z/`: agregados (`controls.json`, `analisis.json`,
  `analisis.md`, `summary_by_cell*.csv`, `transitions_vs_baseline*.csv`), evidencia por parche (`cells.jsonl`,
  `cells_robustez_autocrlf_false.jsonl`) y `manifest.json`. No se copiaron `run.log` (contiene la ruta de la máquina) ni
  los resultados del piloto ni de la línea base de 150; la matriz los contiene (piloto 84 de 84 y línea base 150 de 150
  coinciden celda a celda con la matriz). Reproducir los agregados: `python -I diagnostics/downstream-patches/scripts/analyze_eol_prefix_matrix.py <carpeta>`
  sobre una copia de esa carpeta sin `analisis.*` (el script no sobrescribe).

### 14.2 Parches que aplican por condición (matriz principal, `autocrlf=true`)

Condiciones: primera letra = parche original (**C**RLF) o normalizado (**L**F); segunda = árbol CRLF o LF.

**Resultado principal, fijado de antemano (12.9):** `invalid_patch` que aplican con el **`-p` natural** de cada parche.
Población: **123 de los 141** (excluidos 17 sin cabeceras y 1 con `-p` indeterminado: el parche mixto de qutebrowser).
En la línea base original (CC con `-p1`) aplican **0 de los 141**.

| Condición | `invalid_patch` que aplican (de 123) | Controles (9 aplicables originales) |
|---|---|---|
| CC (filtro original, `-p` natural) | 9 (7,3 %) | 9 / 9 |
| LC | 11 (8,9 %) | 9 / 9 |
| CL | **0** (0 %) | 1 / 9 |
| LL | 11 (8,9 %) | 9 / 9 |

**Con `-p` forzado** (141 `invalid_patch`; el `-p` que no corresponde actúa como control):

| Celda | `-p1` | `-p0` |
|---|---|---|
| CC | 0 / 141 (controles 9 / 9) | 9 / 141 (controles 1 / 9) |
| LC | 0 / 141 (9 / 9) | 11 / 141 (1 / 9) |
| CL | 0 / 141 (1 / 9) | 0 / 141 (1 / 9) |
| LL | **0 / 141 (9 / 9)** | 11 / 141 (1 / 9) |

(Los controles que aplican con `-p0` son el único parche que crea un fichero nuevo, ver 14.1.)

### 14.3 Transiciones respecto de la línea base original (celda LL con `-p` natural, 123 parches)

| Desde (línea base) | Hasta (LL, `-p` natural) | Parches |
|---|---|---|
| fichero inexistente | **aplica** | 10 |
| fichero inexistente | contexto no coincide | 33 |
| fichero inexistente | fichero inexistente | 2 |
| contexto no coincide | contexto no coincide | 24 |
| corrupt patch | **aplica** | 1 |
| corrupt patch | contexto no coincide | 2 |
| corrupt patch | corrupt patch | 37 |
| fragmento sin cabecera | fragmento sin cabecera | 7 |
| sin diff válido | sin diff válido | 7 |

Frente a CC con su `-p` natural, LL añade **2** parches que aplican (`transformers-26752` · RRF pasa de contexto a aplica;
`requests-1142` · RRF pasa de corrupt a aplica) y cambia la categoría de error de otros 2 (`sphinx-9711`, de corrupt a
contexto, con BM25 y UniXcoder). Es decir, el CRLF cambia el resultado aplica/no aplica en 2 de los 123 y la categoría de
error en 4 en total.

### 14.4 Los 141 `invalid_patch` y los 9 controles por separado

- **141 `invalid_patch`:** con `-p1` (el que usan todos los evaluadores leídos) **0 aplican en las cuatro combinaciones
  CRLF/LF**; con su `-p` natural aplican 9 (CC) a 11 (LL) de 123. Es decir, en esta prueba **ningún** `invalid_patch` cambia de
  resultado por normalizar los finales de línea con `-p1`; lo que cambia es la interpretación de las rutas.
- **9 controles:** aplican 9/9 en CC, LC y LL con `-p1`; con el parche CRLF contra árbol LF (CL) solo 1 de 9 (los otros 8 fallan
  por contexto). Los 9 llegaron a la evaluación funcional oficial, de modo que CL **no representa** al evaluador, lo que es
  coherente con que este reciba el parche en LF (13.1). La celda LL con `-p1` concuerda con el filtro original en los 150
  parches: 9 aplican y 141 no.

### 14.5 Desglose por estrategia (con `-p` natural; descriptivo, no concluyente)

| Estrategia | `invalid_patch` | con `-p` natural | CC | LC | CL | LL | Controles |
|---|---|---|---|---|---|---|---|
| BM25 | 47 | 41 | 4 | 4 | 0 | 4 | 3 / 3 |
| UniXcoder | 48 | 42 | 1 | 1 | 0 | 1 | 2 / 2 |
| RRF | 46 | 40 | 4 | 6 | 0 | 6 | 4 / 4 |

Los recuentos son pequeños y la aplicabilidad depende del formato del parche generado, no solo de la calidad de la
recuperación: no se extraen conclusiones sobre la superioridad de una estrategia. **No se ha realizado ningún contraste
estadístico** (no sería válido sin más: las mismas 50 tareas se repiten en las tres estrategias); las diferencias (1, 4 y 6
parches que aplican) son **descriptivas** y no se interpretan como significativas. Las sumas cuadran: 47 + 48 + 46 = 141;
41 + 42 + 40 = 123; 4 + 1 + 6 = 11 (LL); 4 + 1 + 4 = 9 (CC); 3 + 2 + 4 = 9 controles.

### 14.6 Errores que persisten

- **130 de los 141** no aplican en **ninguna** de las 8 celdas (línea base: 24 sin diff, 40 corrupt, 7 fragmento sin
  cabecera, 35 fichero inexistente, 24 contexto).
- **En LL con su `-p` natural (123):** contexto no coincide 59, corrupt 37, aplica 11, fragmento sin cabecera 7, sin diff 7,
  fichero inexistente 2. Los 2 "fichero inexistente" (`yt-dlp-4841`, RRF y UniXcoder) apuntan a un fichero que **no existe en
  el `base_commit`** (`yt_dlp/extractor/discoveryplus.py`).
- **Lectura (redacción corregida en la revisión de cierre, ver 14.14):** corregir las rutas elimina casi todos los
  "fichero inexistente" (43 de 45 dejan de serlo), pero 33 de ellos pasan a fallar por contexto. Contexto (59) y corrupt
  (37) suman **96 de los 123 (78 %; el 68 % de los 141)**. Son parches en los que el contexto o la estructura del diff no
  coinciden con el código (las líneas de contexto no existen tal cual, o los conteos de hunk son incoherentes) y que **no**
  se explican por los finales de línea ni por las rutas bajo estos criterios. **El origen no está determinado**: pueden
  intervenir el modelo, el prompt (pide un unified diff y el modelo solo ve fragmentos de funciones), el formato de salida
  y el procedimiento (recuperación estática, sin acceso al repositorio).
- **Dato exploratorio a nivel de fichero** (solo lectura de `prompt.txt` y `patch.diff`; no se ha comprobado a nivel de
  línea ni frente al gold context): en **46 de los 96** el parche modifica al menos un fichero que **no aparece** en el
  contexto recuperado que se dio al modelo (41 con ninguno de sus ficheros, 5 con alguno), y en 50 todos sus ficheros sí
  aparecen. Por categoría: contexto 28 + 4 de 59 y corrupt 13 + 1 de 37. Como referencia, de los 11 parches que aplican, 10
  tienen todos sus ficheros en el contexto (el otro, ninguno).
- **Cómo reproducir los 46/96 y los 10/11 (solo lectura):**
  `python -I diagnostics/downstream-patches/scripts/analyze_eol_prefix_matrix.py diagnostics/downstream-patches/data/matriz_completa_20261112T000024Z --ficheros-contexto`.
  Lee `cells.jsonl` de esa carpeta y los `prompt.txt` y `patch.diff` versionados de `logs/downstream/`, y escribe
  `analisis_ficheros_contexto.json` (ya incluido, con el detalle por parche): 96 → 41 ninguno + 5 parcial + 50 todos
  (46 con algún fichero no visto); 11 → 10 todos + 1 ninguno; 9 controles → 8 todos + 1 sin cabeceras (crea un fichero nuevo).
  Es un script añadido durante el cierre (2026-11-12) que sustituye al fragmento en línea con que se obtuvieron
  inicialmente; sus resultados coinciden con los de ese fragmento.

### 14.7 No evaluables y ambiguos

0 celdas no evaluables (principal 0, robustez 0); 0 ambigüedades `a/` `b/`; 1 parche con `-p` indeterminado
(`qutebrowser-3fd8e129…` · BM25, `diff --git` con prefijos pero `---`/`+++` sin ellos), excluido del análisis de `-p`
natural y presente en la línea base; 17 parches sin cabeceras (incluidos entre los 24 sin diff) sin `-p` natural.

### 14.8 Matriz principal frente a la réplica de robustez

Sobre árboles LF, 600 celdas con `autocrlf=false` frente a las mismas con `autocrlf=true`: **0 diferencias** de categoría y
**0** de mensaje de Git. En árboles LF, la configuración `autocrlf` no cambia los resultados (los árboles CRLF no se
repitieron con `autocrlf=false`, así que el efecto de `autocrlf` sobre ellos no está medido).

### 14.9 Hipótesis fijadas (12.4) frente a los datos

| Hipótesis | Resultado | Matiz |
|---|---|---|
| **H1** el prefijo explica "fichero inexistente" y poco más | **Apoyada** | Las rutas con su `-p` natural eliminan 43 de los 45 "fichero inexistente", pero solo 9 (CC) a 11 (LL) de los 141 pasan a aplicar |
| **H2** parte de `patch failed` es artefacto del CRLF guardado | **Apoyada solo marginalmente** | El CRLF cambia el resultado en 2 parches (uno de contexto y uno de `corrupt`); los 24 `patch failed` originales persisten en las 8 celdas |
| **H3** sin diff y cabecera defectuosa no cambian; `corrupt` mayoritariamente no cambia | **Apoyada con matiz** | 0 de 24 sin diff y 0 de 7 fragmentos cambian; de 40 `corrupt`, 37 no cambian y 3 sí |

### 14.10 Aplicabilidad, resolución funcional e hipótesis

- **Aplicabilidad (medida):** lo anterior es solo si `git apply --check` acepta el parche en una reconstrucción temporal.
- **Resolución funcional (no medida):** los 11 parches que aplican tras corregir rutas **no se han evaluado funcionalmente**;
  no se sabe si resolverían la incidencia. Los únicos con resolución original son 2 (`resolved`) de los 9 controles.
- **Hipótesis (no demostradas):** que la aplicabilidad de los 11 se mantuviera en el evaluador oficial; que un formato de edición
  alternativo reduzca los fallos de contexto y corrupt; que el CRLF proceda de `write_text`.

### 14.11 Limitaciones

1. No hay equivalencia demostrada con Linux/Docker: el árbol LF es una prueba de sensibilidad y los árboles se emulan.
2. `git apply --check` estricto no incluye las alternativas de Verified (`--3way`, `--reject`, `patch --fuzz`) ni de PolyBench
   (`--ignore-whitespace`, `patch --fuzz`); estas podrían aceptar parches que aquí fallan. No se midió.
3. El resultado no cuantifica cuántos de los 141 aplicarían en un evaluador tolerante.
4. Reconstrucción parcial (solo ficheros candidatos de las cabeceras); el primer error enmascara los demás.
5. Las 150 condiciones son 50 tareas × 3 estrategias, no independientes; todo es descriptivo.
6. Los parches que solo crean ficheros no permiten distinguir `-p0` de `-p1` (control 4).
7. "Parche LF" supone que los `\r` los añadió el guardado en Windows; no se conoce la salida cruda del modelo.

### 14.12 Qué se puede y qué no se puede concluir

| Se puede afirmar (con los datos) | No se puede afirmar |
|---|---|
| El filtro original es reproducible (150/150) y, **bajo `git apply --check` estricto**, sus 141 rechazos no dependen del CRLF: ninguno cambia con LL y `-p1` | Que el evaluador oficial habría rechazado los 141 (no se probaron sus alternativas tolerantes) |
| Con rutas normalizadas (`-p` natural), 11 de 123 **pasarían `git apply --check`** en LL y 9 en CC | Que esos 11 los acepte el evaluador oficial ni que resuelvan la incidencia (no se han evaluado funcionalmente) |
| 96 de 123 (78 %) siguen sin pasar la comprobación en la mejor celda por discrepancias de contexto o de estructura del diff | Atribuir esos fallos al modelo: el prompt, el formato de salida y el contexto recuperado también intervienen (en 46 de los 96 el parche edita ficheros que el modelo no vio; dato exploratorio a nivel de fichero) |
| Los 9 controles, que el evaluador oficial sí recibió, pasan la comprobación en LL y 8 de 9 fallan en CL (coherente con la inspección de código) | Que la reconstrucción LL equivalga al entorno oficial; extrapolar a otros modelos, tareas o a un evaluador tolerante |

### 14.13 Propuesta de cierre (pendiente de aprobación)

- **Criterio 1 de cierre cumplido (plan, "Seguimiento del diagnóstico"):** línea base reproducida y matriz completa
  ejecutada una vez y documentada. **No ejecutar más celdas, evaluadores ni réplicas.**
- **Qué llevar a la memoria:** una subsección breve de diagnóstico de aplicabilidad (clasificación 117/24 y causas, hallazgo de
  prefijos, resultado "9→11 de 123" y "0 de 141 con `-p1`") y los límites de 14.11 en las limitaciones. Mantener las cifras
  originales (141/7/2) como resultado del experimento.
- **Decisión pendiente:** si se acomete la Fase 2 del plan (formato de edición alternativo del LLM). Los datos dicen que
  arreglar rutas y finales de línea apenas recupera parches y que el resto falla por discrepancias de contexto o de
  estructura del diff, de origen no determinado. Un formato de edición podría ayudar en los casos en que el modelo sí vio los
  ficheros (50 de los 96), pero no en aquellos en que no los vio (46 de 96), que apuntan más bien a la recuperación y al
  procedimiento. **Ambas son hipótesis** y exigirían nuevas generaciones, fuera del plazo del diagnóstico.

### D-004 · 2026-11-12 · Ejecución de la matriz completa

- **Decisión:** ejecutar la matriz completa (1 200 + 600 celdas) una sola vez, con línea base validada primero.
- **Resultado:** línea base 150/150; sin celdas no evaluables; integridad intacta; resultados en 14.2–14.8.
- **No cambia:** ningún estado original, parche ni resultado experimental.
- **Pendiente:** aprobar el cierre propuesto (14.13), actualizar las preguntas de defensa y la memoria, y commitear.

### 14.14 Revisión de consistencia y cierre (2026-11-12)

Revisión de solo lectura sobre `cells.jsonl`, `cells_robustez_autocrlf_false.jsonl` y `controls.json` de la ejecución del
2026-11-12. No se ejecutó ningún experimento ni evaluador.

| Comprobación | Resultado |
|---|---|
| **1. Los 11 de LL son los que aplican en alguna celda** | **Sí, el mismo conjunto** (11 = 11, sin diferencias en ningún sentido). Añadir las 600 celdas de robustez no suma ninguno. Los 9 de CC son un subconjunto; LC (11) = LL. **130 de 141 (92,2 %) no aplican en ninguna de las 8 celdas principales**: confirmado |
| **2. Denominadores** | 141 = 30 con `a/` `b/` + 93 sin prefijo + 17 sin cabeceras + 1 indeterminado. **123 = 30 + 93**; excluidos 18 = 17 + 1. Los 24 sin diff = 17 (sin cabeceras, todos) + 7 (con `-p` natural). Porcentajes: 9/123 = 7,3 %; 11/123 = 8,9 %; 11/141 = 7,8 %; 130/141 = 92,2 %; 96/123 = 78,0 % (96/141 = 68,1 %); 43/45 = 95,6 %. Coherentes con las tablas |
| **3. Los 96 con contexto o corrupt** | Reinterpretados: no se atribuyen al modelo (ver 14.6). Dato exploratorio: en 46 de 96 el parche edita ficheros que no estaban en el contexto recuperado. Medida validada: 10 de los 11 parches que aplican tienen todos sus ficheros en el contexto |
| **4. Estrategias** | Suman 141, 123 y 9; 9 (CC) y 11 (LL) de aplicables. Son diferencias **descriptivas**; no hay contraste estadístico ni se interpreta significación |
| **5. Tres niveles distintos** | Todo lo medido es **`git apply --check` sobre una reconstrucción**. No es aceptación del evaluador oficial (no se probaron sus alternativas tolerantes ni se ejecutó en Linux/Docker) ni resolución funcional (solo 2 de los 150 resuelven, los controles originales) |

**Correcciones introducidas en la sección 14 durante esta revisión** (se citan las redacciones sustituidas):

1. 14.6: "son fallos de contenido del diff … y no de finales de línea ni de rutas" → atribuía implícitamente el fallo al
   contenido generado por el modelo; ahora se dice que el **origen no está determinado** y se añade el dato de ficheros no
   vistos.
2. 14.12, fila 1: "sus 141 rechazos **no se deben al CRLF**" → "**bajo `git apply --check` estricto**, … no dependen del CRLF".
3. 14.12, fila 2: "11 de 123 aplicarían" → "**pasarían `git apply --check`**"; no se afirma aceptación del evaluador.
4. 14.12, fila 3: "sigue fallando por contenido" → "discrepancias de contexto o de estructura del diff"; ya no atribuye al
   modelo.
5. 14.12, fila 4: "se comportan como el evaluador oficial en LL" → "pasan la comprobación en LL y 8 de 9 fallan en CL";
   coherente con la inspección de código, sin afirmar equivalencia.
6. 14.13: "el cuello de botella es el contenido del diff" → fallos "de origen no determinado", con la distinción 50/46.
7. 14.5: se añade que no hay contraste estadístico y las sumas de control.

**Estado: diagnóstico experimental CERRADO.** La revisión no encontró incoherencias numéricas; las imprecisiones eran de
interpretación y están corregidas. Los resultados originales (141 `invalid_patch`, 7 `not_resolved`, 2 `resolved`), los
150 parches, los repositorios y los manifiestos históricos permanecen intactos. Solo se reabriría si se decide medir un
evaluador tolerante o acometer la Fase 2 del plan (nuevas generaciones), que quedaría como un experimento aparte.

**Cambios concretos que habrá que introducir en la memoria (no realizados; el Word no se ha modificado):**

1. **Metodología:** describir brevemente el filtro de aplicabilidad (`git apply --check`, `-p1` por defecto, parche leído
   del fichero CRLF en Windows con `autocrlf=true`) y el protocolo de diagnóstico (matriz 2 × 2 × 2, línea base de 150,
   controles, solo lectura, reconstrucción temporal con `.gitattributes` del `base_commit`).
2. **Resultados, evaluación con LLM:** mantener la Tabla 6 (141 / 7 / 2). Sustituir "113 de los 141 con diff reconocible" por
   **117 (112 con cabeceras completas y 5 con cabecera defectuosa) y 24 sin diff**. Añadir una subsección de "Diagnóstico de
   la aplicabilidad" con una tabla (CC 9, LC 11, CL 0, LL 11 de 123, y controles 9, 9, 1, 9 de 9), el hallazgo de prefijos
   (94 sin prefijo por las líneas `---`, de los cuales 93 con `-p` natural) y "0 de 141 con `-p1`".
3. **Discusión:** reformular `invalid_patch` como "no aplicable según el filtro", no como "rechazado por el evaluador" ni
   "error del modelo"; el CRLF cambia el resultado en 2 de 123; los 96 fallos de contexto o corrupt tienen origen no
   determinado (modelo, prompt, formato, recuperación; 46 de 96 editan ficheros no vistos, dato exploratorio).
4. **Limitaciones:** sin equivalencia con Linux/Docker; evaluadores tolerantes no modelados; los 11 no evaluados
   funcionalmente; tareas no independientes; salida cruda del modelo desconocida.
5. **Conclusiones y trabajo futuro:** mantener que una buena recuperación no garantiza la resolución; añadir como líneas
   futuras el formato de edición alternativo, medir un evaluador tolerante, guardar los parches con LF y normalizar prefijos,
   y estudiar si la recuperación incluye los ficheros que el modelo termina modificando.
6. **Resumen y abstract:** no es necesario cambiar las cifras; opcionalmente una frase sobre el diagnóstico.
7. **Anexos:** en la reproducibilidad, referenciar `diagnostics/downstream-patches/` (scripts, datos y documento de
   diagnóstico) y el commit; indicar que `output/` no se versiona.
8. **Figuras y tablas:** una tabla nueva (aplicabilidad por condición); una figura opcional de barras CC/LC/CL/LL.

- **Actualización de D-004 (2026-11-12):** cerrado tras esta revisión de consistencia.
