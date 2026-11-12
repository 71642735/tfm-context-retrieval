# Analisis de eol_prefix_matrix_20261112T000024Z
Parches: 150 (141 `invalid_patch` esperados: 141; controles con aplicabilidad original: 9). Celdas principales: 1200; robustez: 600. Script v1.2, manifest esquema 2.
Integridad: sin cambios = True; codigo de salida = 0. `core.autocrlf` efectivo: principal=true, robustez=false.

## 0. Controles

- **Control 1 (linea base = resultado original de `git apply --check`)**: 150 de 150 coinciden; discrepancias: 0.
- **Control 2** (los 9 aplicables originales aplican en la linea base): fallan 0.
- **Control 3** (respuestas sin diff nunca aplican): violaciones 0.
- **Control 4** (celdas con `-p` cruzado deben fallar): n=528, categorias={'corrupt_patch': 154, 'fragmento_sin_cabecera': 28, 'fichero_inexistente': 314, 'sin_diff_valido': 28, 'aplica': 4}, que aplican (anomalia)=4.

## 1. Parches que pasan `git apply --check` por condicion (matriz principal, `autocrlf=true`)

**A. Con el `-p` natural de cada parche** (resultado principal fijado de antemano). Poblacion: 123 de los 141 `invalid_patch` con `-p` natural no ambiguo; excluidos 18 (sin cabeceras o `-p` indeterminado). En la linea base original (CC con `-p1`) aplican 0 de los 141.

| Condicion | `invalid_patch` que aplican (de 123) | no evaluables | Controles (9 aplicables originales) |
|---|---|---|---|
| CC (parche CRLF, arbol CRLF) | 9 / 123 (7.3 %) | 0 | 9 / 9 |
| LC (parche LF, arbol CRLF) | 11 / 123 (8.9 %) | 0 | 9 / 9 |
| CL (parche CRLF, arbol LF) | 0 / 123 (0.0 %) | 0 | 1 / 9 |
| LL (parche LF, arbol LF) | 11 / 123 (8.9 %) | 0 | 9 / 9 |

**B. Con `-p` forzado** (los 141 `invalid_patch`, sin tener en cuenta el `-p` natural; el que no corresponde es un control):

| Celda | `invalid_patch` que aplican (de 141) | Controles |
|---|---|---|
| CC con -p1 | 0 / 141 | 9 / 9 |
| LC con -p1 | 0 / 141 | 9 / 9 |
| CL con -p1 | 0 / 141 | 1 / 9 |
| LL con -p1 | 0 / 141 | 9 / 9 |
| CC con -p0 | 9 / 141 | 1 / 9 |
| LC con -p0 | 11 / 141 | 1 / 9 |
| CL con -p0 | 0 / 141 | 1 / 9 |
| LL con -p0 | 11 / 141 | 1 / 9 |

Leyenda: primera letra = parche original (C = CRLF) o normalizado (L = LF); segunda = arbol CRLF o LF. **CC con `-p1` es el filtro original; LL con `-p1` es la celda mas parecida a lo que reciben los evaluadores (parche LF, `-p1`, Linux), sin sus alternativas de aplicacion (sin equivalencia demostrada).**

## 2. Desglose por estrategia de recuperacion (con `-p` natural)

| Estrategia | `invalid_patch` | con -p natural | CC | LC | CL | LL | controles en linea base |
|---|---|---|---|---|---|---|---|
| BM25 | 47 | 41 | 4 / 41 | 4 / 41 | 0 / 41 | 4 / 41 | 3 / 3 |
| UniXcoder | 48 | 42 | 1 / 42 | 1 / 42 | 0 / 42 | 1 / 42 | 2 / 2 |
| RRF | 46 | 40 | 4 / 40 | 6 / 40 | 0 / 40 | 6 / 40 | 4 / 4 |

## 3. Transiciones respecto de la linea base original (CC con `-p1`), solo `invalid_patch` con `-p` natural

**LL con su `-p` natural** (desde la categoria de la linea base hasta la de esta celda):

| desde (linea base) | hasta (esta celda) | parches |
|---|---|---|
| contexto_no_coincide | contexto_no_coincide | 24 |
| corrupt_patch | aplica | 1 |
| corrupt_patch | contexto_no_coincide | 2 |
| corrupt_patch | corrupt_patch | 37 |
| fichero_inexistente | aplica | 10 |
| fichero_inexistente | contexto_no_coincide | 33 |
| fichero_inexistente | fichero_inexistente | 2 |
| fragmento_sin_cabecera | fragmento_sin_cabecera | 7 |
| sin_diff_valido | sin_diff_valido | 7 |

**CC con su `-p` natural** (desde la categoria de la linea base hasta la de esta celda):

| desde (linea base) | hasta (esta celda) | parches |
|---|---|---|
| contexto_no_coincide | contexto_no_coincide | 24 |
| corrupt_patch | corrupt_patch | 40 |
| fichero_inexistente | aplica | 9 |
| fichero_inexistente | contexto_no_coincide | 34 |
| fichero_inexistente | fichero_inexistente | 2 |
| fragmento_sin_cabecera | fragmento_sin_cabecera | 7 |
| sin_diff_valido | sin_diff_valido | 7 |

**LC con su `-p` natural** (desde la categoria de la linea base hasta la de esta celda):

| desde (linea base) | hasta (esta celda) | parches |
|---|---|---|
| contexto_no_coincide | contexto_no_coincide | 24 |
| corrupt_patch | aplica | 1 |
| corrupt_patch | contexto_no_coincide | 2 |
| corrupt_patch | corrupt_patch | 37 |
| fichero_inexistente | aplica | 10 |
| fichero_inexistente | contexto_no_coincide | 33 |
| fichero_inexistente | fichero_inexistente | 2 |
| fragmento_sin_cabecera | fragmento_sin_cabecera | 7 |
| sin_diff_valido | sin_diff_valido | 7 |

**CL con su `-p` natural** (desde la categoria de la linea base hasta la de esta celda):

| desde (linea base) | hasta (esta celda) | parches |
|---|---|---|
| contexto_no_coincide | contexto_no_coincide | 24 |
| corrupt_patch | corrupt_patch | 40 |
| fichero_inexistente | contexto_no_coincide | 43 |
| fichero_inexistente | fichero_inexistente | 2 |
| fragmento_sin_cabecera | fragmento_sin_cabecera | 7 |
| sin_diff_valido | sin_diff_valido | 7 |

## 4. Errores que persisten

- **Nunca aplican en ninguna de las 8 celdas de la matriz principal:** 130 de 141 `invalid_patch`. Categoria en la linea base: {'sin_diff_valido': 24, 'corrupt_patch': 40, 'fragmento_sin_cabecera': 7, 'fichero_inexistente': 35, 'contexto_no_coincide': 24}.

**Categoria en la celda LL con su `-p` natural** (los que siguen sin aplicar):

| categoria (LL, -p natural) | parches |
|---|---|
| contexto_no_coincide | 59 |
| corrupt_patch | 37 |
| aplica | 11 |
| fragmento_sin_cabecera | 7 |
| sin_diff_valido | 7 |
| fichero_inexistente | 2 |

- Para comparar, categorias de la linea base sobre los 141: {'sin_diff_valido': 24, 'corrupt_patch': 41, 'fragmento_sin_cabecera': 7, 'fichero_inexistente': 45, 'contexto_no_coincide': 24}.

- **Respuestas sin diff:** 24; aplican en alguna celda: 0 (control 3).
- **`corrupt_patch` en la linea base:** 41; aplican en alguna celda: 1 (H3 esperaba pocos o ninguno).

## 5. Casos no evaluables o ambiguos

- **Celdas no evaluables:** 0 (principal 0, robustez 0). Motivos: {}.
- **Grupos de prefijo (150 parches):** {'sin_cabeceras': 17, 'sin_prefijo': 93, 'todo_a/': 39, 'indeterminado': 1}.
- **Ambiguedad `a/` `b/` (directorio real llamado a o b):** 0.
- **`-p` indeterminado (excluidos del analisis de `-p` natural):** ['instance_qutebrowser__qutebrowser-3fd8e12949b bm25'].

## 6. Matriz principal (`autocrlf=true`) frente a la replica de robustez (`autocrlf=false`), arboles LF

- Celdas comparadas: 600. Distinta categoria: 0. Distinto mensaje de Git: 0.

## 7. Filtro original (CC, `-p1`) frente a la celda mas parecida a los evaluadores (LL, `-p1`)

- `invalid_patch` que **aplican en LL con `-p1`**: 0 de 141 (rechazados por el filtro original). Por grupo: {}. Por estrategia: {}.
- Controles (aplicaban en el filtro original) que **no aplican en LL con `-p1`**: 0 de 9.
- Esto es una prueba de sensibilidad: `git apply --check` estricto, sin las alternativas de los evaluadores y con un arbol emulado; no equivale a la aceptacion del evaluador oficial ni a la resolucion de la tarea.

