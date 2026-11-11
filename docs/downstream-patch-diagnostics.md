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
