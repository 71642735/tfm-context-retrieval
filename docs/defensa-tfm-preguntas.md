# Preparación de la defensa del TFM: preguntas del tribunal y respuestas

Material de estudio para la exposición. Complementa el informe técnico
[`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md) y no sustituye a la memoria.

**Cómo leerlo.** Cada respuesta lleva una etiqueta:

| Etiqueta | Significa | Qué puedes hacer en la defensa |
|---|---|---|
| ✅ **RESPALDADA** | Se apoya en resultados del experimento o en comprobaciones ya realizadas. | Afirmarla con seguridad. |
| 🟡 **PARCIAL** | Parte es dato y parte depende de una prueba pendiente. | Dar el dato y decir claramente qué falta. |
| ⏳ **PENDIENTE** | Depende de comprobaciones que aún no se han hecho. | Presentarla como línea de trabajo o hipótesis, nunca como resultado. |

Las cifras proceden de `results/downstream_results_final.jsonl`, de las tablas de la memoria (v2.6) y de
`diagnostics/downstream-patches/`. **Antes de la defensa, actualiza este documento con lo que cambie en la
memoria final** (por ejemplo, si se repite la evaluación con el LLM).

## Cifras clave para tener a mano

| Dato | Valor | Fuente |
|---|---|---|
| Tareas / repositorios / condiciones | 50 / 20 / 150 (3 estrategias × 50) | Memoria, cap. 3 y 5 |
| Modelo y configuración | `gemini-3.5-flash-lite`, K = 10, Pass@1, 4096 tokens, razonamiento *minimal* | Memoria, 3.3.5 |
| Resultado downstream | 141 `invalid_patch`, 7 `not_resolved`, 2 `resolved` | `results/downstream_results_final.jsonl` |
| `resolved` | 2, ambos con BM25 | Memoria, Tabla 6 |
| Causas de los 141 | 45 fichero inexistente, 41 parche corrupto, 24 sin diff, 24 contexto no coincide, 7 fragmento sin cabecera | `diagnostics/.../invalid_patches_classification.csv` |
| `invalid_patch` con estructura de parche reconocible por Git | 117 de 141 (83 %): 112 con cabeceras completas y 5 con cabecera defectuosa. Sin diff: 24 (17 %) | Diagnóstico, sec. 2.1 y D-001 |
| Parches sin prefijo `a/` `b/` | 94 de los 141 (los 9 aplicables sí lo llevan) | Diagnóstico, sec. 3 |
| Recuperados con `git apply --check -p0` (reconstrucción CRLF, observación previa) | 9 de 94 | Diagnóstico, sec. 7 |
| Matriz completa, `-p` natural, de 123 `invalid_patch` | Filtro original reconstruido (CC): 9 · parche LF y árbol CRLF (LC): 11 · parche CRLF y árbol LF (CL): 0 · parche LF y árbol LF (LL): 11 | Diagnóstico, sec. 14.2 |
| Matriz completa, `-p1` (el de los evaluadores) | 0 de 141 aplican en las cuatro combinaciones CRLF/LF; los 9 controles aplican en CC, LC y LL | Diagnóstico, sec. 14.4 |
| No aplican en ninguna de las 8 celdas | 130 de 141 (92,2 %) | Diagnóstico, sec. 14.14 |
| Contexto o corrupt en LL (`-p` natural) | 96 de 123 (78 %; 68 % de los 141); en 46 de los 96 el parche edita ficheros que no estaban en el contexto recuperado (dato exploratorio) | Diagnóstico, sec. 14.6 |
| Parches guardados con CRLF | 150 de 150 | Diagnóstico, sec. 7 |
| F1 a nivel de fichero, K = 5 | BM25 0,2578 · RRF 0,2505 · UniXcoder 0,1673 | Memoria, Tablas 3-5 |

---

## 1. Los 141 parches inválidos y sus causas

### 1.1 ¿Por qué el 94 % de los parches no se pueden aplicar?
✅ **RESPALDADA** (descripción) · 🟡 (causa raíz)

> De las 150 condiciones, 141 generan un parche que `git apply --check` rechaza. Clasificados por el mensaje
> de Git: 45 apuntan a un fichero inexistente, 41 son parches corruptos, 24 ni siquiera contienen un diff,
> 24 tienen un contexto que no coincide con el código y 7 son fragmentos sin cabecera. Visto de otro modo, 117 de los 141 (83 %) tienen una estructura de parche que
> Git reconoce, y 24 (17 %) no contienen diff. Es decir, la mayoría
> son fallos de **formato** del diff, no de lógica. La causa raíz última (formato de salida del modelo frente
> a artefactos de mi entorno Windows) la he empezado a separar y lo explico a continuación.

### 1.2 ¿Es un problema del modelo o de su pipeline?
🟡 **PARCIAL** (actualizada el 2026-11-12 tras la matriz completa)

> No puedo repartirlo con precisión y por eso no atribuyo los fallos solo al modelo. Hechos: el prompt solo pide
> "un unified diff", sin convención de rutas; los 150 parches se guardaron con CRLF; y el modelo solo ve
> fragmentos de funciones, sin acceso al repositorio. Tras la matriz completa, las rutas y el CRLF explican poco: con
> rutas normalizadas pasan la comprobación 11 de los 141 y el CRLF cambia el resultado en 2. El resto (130 de 141 no
> pasan en ninguna condición) son diffs sin estructura válida, con conteos de hunk incoherentes o con contexto que no
> coincide. De los 96 con contexto o corrupt, **46 editan ficheros que el modelo no vio**. Puede haber influido el
> modelo, el prompt, el formato de salida o la recuperación: **no está determinado**.

### 1.3 ¿Qué son los 24 casos en los que no hay diff?
✅ **RESPALDADA** (qué son) · ⏳ (por qué)

> Son respuestas en las que el modelo declara que no puede producir el parche porque el contexto recuperado
> no incluye el código relevante. Revisé dos ejemplos concretos. Mi hipótesis es que se trata de fallos de
> recuperación (el contexto era insuficiente), pero **no la he comprobado** contra el gold context. Si se
> confirmara, serían casos donde la recuperación, no el formato, es el factor limitante.

### 1.4 ¿Cómo los clasificó y de dónde salen los números?
✅ **RESPALDADA**

> De los 150 `patch.diff` y del campo `detail` del fichero de resultados, que conserva el mensaje completo de
> `git apply --check` de cada parche. La clasificación es reproducible con un script de solo lectura
> (`classify_invalid_patches.py`) y queda tabulada por tarea y estrategia en un CSV.

### 1.5 ¿Hay alguna estrategia de recuperación con más parches inválidos?
✅ **RESPALDADA**

> No de forma relevante: 47 con BM25, 48 con UniXcoder y 46 con RRF. El problema es transversal a las tres,
> lo que apunta a la generación y no a una estrategia concreta.

### 1.6 ¿Por qué inicialmente se contabilizaron 113 parches con estructura de diff y posteriormente 117?
✅ **RESPALDADA**

> Porque eran dos criterios distintos. La auditoría inicial usaba una heurística de subcadenas: buscaba `--- `,
> `+++ ` y `@@` en cualquier parte del texto. Esa heurística tuvo un **falso positivo** (una respuesta de texto
> del modelo que contenía esas cadenas) y **omitió cinco parches** con la cabecera de fichero defectuosa (la
> línea `---` repetida y sin `+++`), que sí tienen un hunk válido. Al revisarlo adopté el criterio de Git: un
> parche es reconocible si `git apply --check` detecta estructura de parche. Con él son 117, de los que 112
> tienen cabeceras completas y 5 defectuosas; los 24 restantes no contienen diff. Son seis parches de
> diferencia (113 − 1 + 5 = 117) y están identificados en el diagnóstico.

---

## 2. Recuperación de contexto, aplicabilidad del parche y resolución funcional

### 2.1 Explique la diferencia entre las tres cosas.
✅ **RESPALDADA**

> Son tres etapas encadenadas con métricas distintas.
> 1. **Recuperación**: ¿el contexto seleccionado contiene lo relevante? Se mide con cobertura, precisión y F1
>    frente al gold context, a nivel de fichero y de línea.
> 2. **Aplicabilidad**: ¿el parche generado por el LLM se puede aplicar al repositorio? Se mide con
>    `git apply --check` (`invalid_patch` frente a aplicable).
> 3. **Resolución funcional**: ¿el parche aplicado hace pasar las pruebas oficiales de la tarea? Se mide con
>    el evaluador de cada benchmark (`resolved` frente a `not_resolved`).
>
> Cada etapa depende de la anterior: sin buen contexto es difícil un buen parche; sin parche aplicable no
> hay evaluación funcional.

### 2.2 ¿Por qué BM25 recupera mejor si luego casi nada se resuelve?
🟡 **PARCIAL**

> Porque son etapas distintas. BM25 obtiene el mayor F1 de recuperación en las seis configuraciones, pero la
> resolución depende también de que el modelo genere un diff aplicable y correcto. En mi experimento, solo 9
> de 150 condiciones llegaron a la evaluación funcional y 2 se resolvieron, ambas con BM25. Con 2 casos no
> puedo afirmar que BM25 *cause* más resoluciones; es una observación descriptiva.

### 2.3 ¿Demuestra su experimento que mejor recuperación implica más resoluciones?
✅ **RESPALDADA** (que **no** lo demuestra)

> No. Los dos casos resueltos tienen valores medios de cobertura y F1 más altos (a nivel de línea, cobertura
> 0,67 frente a 0,30 y 0,19), pero son solo dos y la relación no es causal. Lo que el experimento sí muestra
> es que una recuperación razonable no basta si el parche no se puede aplicar.

### 2.4 ¿Por qué solo evaluó el LLM con K = 10?
✅ **RESPALDADA**

> Para mantener una cantidad de contexto fija y comparable entre estrategias, y elegida **antes** de ver los
> resultados, como punto intermedio entre 5, 10 y 20. Es una limitación reconocida: no sé cómo cambiaría la
> resolución con K = 5 o K = 20.

### 2.5 ¿Por qué no usó un agente que explore el repositorio?
✅ **RESPALDADA**

> El objetivo era aislar el efecto de la **estrategia de recuperación**. Un agente interactivo (por ejemplo
> SWE-agent) introduce muchas más variables. Lo dejo como trabajo futuro y lo señalo como limitación: la
> recuperación aquí es estática, antes de la generación.

### 2.6 ¿Qué diferencia hay entre un parche reconocible, uno aplicable y uno que resuelve la incidencia?
✅ **RESPALDADA**

> Son tres etapas distintas y cada una exige más que la anterior.
> 1. **Reconocible**: el texto del modelo tiene estructura de parche y Git la detecta. Es una propiedad del
>    **formato**. 117 de los 141 `invalid_patch` cumplen esto.
> 2. **Aplicable**: además, `git apply --check` acepta el parche sobre el repositorio en el commit de la tarea:
>    rutas, números de línea y contexto coinciden con el código real. Solo 9 de las 150 condiciones llegan aquí.
> 3. **Resuelve la incidencia**: el parche aplicado hace pasar las pruebas oficiales (`FAIL_TO_PASS` y
>    `PASS_TO_PASS`). Solo 2 de las 150 condiciones lo consiguen.
>
> No deben confundirse porque un parche puede tener un formato perfectamente reconocible y no aplicarse (así
> les ocurre a 117 de los 141), y uno aplicable puede no resolver nada (7 de 9). Por eso la cifra de "diff
> reconocible" no demuestra que el modelo acierte, sino solo que produce algo con forma de parche. Esta pregunta
> es distinta de la 2.1, que separa recuperación, aplicabilidad y resolución.

---

## 3. Prefijos de rutas, `git apply`, LF/CRLF y reproducibilidad

### 3.1 ¿Qué son los prefijos `a/` y `b/` y por qué importan?
✅ **RESPALDADA**

> Un diff de Git suele escribir las rutas como `a/ruta` y `b/ruta`. `git apply` por defecto usa `-p1`, que
> elimina el primer componente de cada ruta. Si el diff no lleva esos prefijos, Git quita en realidad el
> primer directorio real (por ejemplo `src/` en `src/_pytest/pastebin.py`) y busca un fichero que no existe.

### 3.2 ¿Cuántos fallos se deben a ese problema?
✅ **RESPALDADA** (actualizada el 2026-11-12)

> 94 de los 141 parches no llevan prefijos `a/` `b/` (93 con `-p` natural y 1 mixto), y 44 de los 45 "fichero
> inexistente" son de ese grupo. Con las rutas normalizadas (`-p0` en esos casos) y la comprobación estricta, pasan
> **9 (filtro original reconstruido) a 11 (parche LF y árbol LF) de los 123** con `-p` natural, es decir, el 6-8 % de
> los 141. Elimina 43 de los 45 errores de "fichero inexistente", pero 33 de ellos pasan a fallar por contexto. Por
> tanto el prefijo explica una parte pequeña. Y como todos los evaluadores usan `-p1`, `-p0` es una lente de
> diagnóstico, no un comportamiento del evaluador.

### 3.3 ¿Por qué los parches aplicables llevan prefijo y los otros no?
🟡 **PARCIAL**

> El dato es que los 9 aplicables llevan `a/` y `b/`, y ninguno de los que no los llevan llegó a la
> evaluación. La explicación probable es que el modelo a veces sigue la convención de Git y a veces escribe
> la ruta tal cual aparece en el contexto, pero **no he analizado por qué elige una u otra**.

### 3.4 ¿Qué pasa con LF y CRLF?
✅ **RESPALDADA** (actualizada el 2026-11-12)

> Dos hechos: `core.autocrlf=true` en mi Git global, de modo que el árbol de trabajo está en CRLF, y los 150
> `patch.diff` guardados con CRLF. Lo he cuantificado con la matriz: con `-p1`, **ninguno** de los 141 cambia de
> resultado al usar parche LF y árbol LF; con su `-p` natural, el CRLF cambia si el parche pasa la comprobación en solo
> 2 de 123 (y la categoría de error en otros 2). Sí importa en un caso concreto: un parche CRLF contra un árbol LF
> falla (8 de los 9 controles fallan en esa combinación), pero según el código los evaluadores reciben el parche leído con
> `read_text`, es decir, en LF.

### 3.5 ¿Por qué se guardaron los parches con CRLF?
⏳ **PENDIENTE**

> Mi hipótesis es que `Path.write_text` en Windows convierte `\n` en `\r\n`. Lo he observado en los bytes de
> los archivos, pero no he reproducido la causa de forma controlada.

### 3.6 ¿Su comprobación de aplicabilidad es equivalente a la del evaluador oficial?
🟡 **PARCIAL** (actualizada el 2026-11-12)

> No es equivalente y no lo afirmo. Mi filtro usaba el parche CRLF, el árbol de Windows y `git apply --check`
> estricto. Según el código, los evaluadores reciben el parche en LF, corren en Linux y usan `-p1`; Verified y
> PolyBench añaden alternativas más tolerantes (`--3way`, `--ignore-whitespace`, `patch --fuzz`) y Pro no. La celda
> más parecida (parche LF, árbol LF, `-p1`) da el mismo resultado que mi filtro en los 150 parches: 9 aplican y 141 no.
> Pero eso **no demuestra equivalencia**: no ejecuté los evaluadores ni modelé sus alternativas.

### 3.7 ¿Cómo garantiza la reproducibilidad?
✅ **RESPALDADA** (selección y registros) · 🟡 (entorno)

> La muestra se selecciona con semilla fija (42), se conserva en `results/final_tasks.csv`, y se guardan el
> prompt, el parche y los metadatos de cada condición. La reproducibilidad **bit a bit** del LLM no está
> garantizada (una sola generación por condición con un modelo remoto), y el comportamiento de `git apply`
> depende de la configuración de Git y del sistema operativo, como acabo de ver con `autocrlf`.

### 3.8 ¿Cómo comprobó el efecto de LF/CRLF sin repetir el experimento?
✅ **RESPALDADA** (actualizada el 2026-11-12)

> Reconstruí en una carpeta temporal solo los ficheros que cada parche puede tocar, tomados del `base_commit` con
> `git cat-file`, aplicando las reglas de `autocrlf` y `.gitattributes`, y ejecuté únicamente `git apply --check`.
> Validé el método con 39 casos y después con la línea base de los 150 parches: reproduce 150 de 150 el resultado y el
> mensaje originales. Luego ejecuté 1.200 comprobaciones de la matriz principal y 600 de la réplica, con hashes de los
> parches, los resultados, los repositorios y sus índices antes y después, sin cambios.

---

## 4. Validez de los resultados originales

### 4.1 ¿Son fiables los resultados de recuperación (BM25, UniXcoder, RRF)?
✅ **RESPALDADA**

> Sí en lo que miden: los rankings y las métricas se calculan antes y con independencia del LLM, con las mismas
> 50 tareas, el mismo chunking y los mismos puntos de corte. Los hallazgos sobre `git apply` y CRLF afectan
> a la fase de generación y aplicación, **no** al cálculo de cobertura, precisión y F1.

### 4.2 ¿Es significativa la ventaja de BM25 sobre RRF?
⏳ **PENDIENTE**

> BM25 obtiene el mayor F1 medio en todas las configuraciones, pero algunas diferencias son pequeñas (por
> ejemplo 0,2578 frente a 0,2505 en F1 a nivel de fichero con K = 5). Con 50 tareas **no he hecho** una
> prueba de significación. La corrección natural es una prueba pareada por tarea (Wilcoxon) o intervalos de
> confianza por bootstrap. Hasta entonces afirmo que BM25 obtiene valores medios más altos, no que sea
> significativamente mejor.

### 4.3 ¿Se pueden fiar de la evaluación con el LLM?
🟡 **PARCIAL**

> Los 9 casos evaluados funcionalmente son fiables. Pero 141 de 150 condiciones no llegaron a esa evaluación,
> así que la segunda parte aporta **muy poca información comparativa**. Lo reconozco en las limitaciones, y
> mi director me propuso mejorarlo antes de la entrega final.

### 4.4 ¿Los 141 `invalid_patch` están correctamente etiquetados?
✅ **RESPALDADA** (el etiquetado) · 🟡 (su significado)

> Sí: son reproducibles como resultado del filtro que apliqué (150 de 150 en la línea base, con el mensaje de Git
> original). Lo que no puedo afirmar es que el evaluador oficial los hubiera rechazado, porque no modelé sus
> alternativas de aplicación. Por eso describo `invalid_patch` como "no aplicable según el filtro del TFM", no como
> "rechazado por el evaluador" ni como "error del modelo".

### 4.5 ¿Comprobó que no se contabilizaran errores de infraestructura como fallos del modelo?
✅ **RESPALDADA**

> Sí. El pipeline distingue `infrastructure_error` de `invalid_patch`, `resolved` y `not_resolved`, y los
> fallos de infraestructura (Windows, Podman, imágenes) se corrigieron y se reevaluó el **mismo** parche sin
> volver a llamar al modelo, para respetar Pass@1. En los resultados finales no hay ninguna condición
> marcada como fallo de infraestructura.

### 4.6 ¿Cambiar de 113 a 117 invalida los resultados originales?
✅ **RESPALDADA**

> No. Es una corrección de la **clasificación descriptiva** de los parches inválidos, no una modificación de los
> resultados del experimento. Los estados originales de las 150 condiciones no cambian: 141 `invalid_patch`,
> 7 `not_resolved` y 2 `resolved`. Tampoco cambian los parches, la recuperación ni las métricas. Lo que se
> corrige es cuántos de los 141 tienen estructura de diff (117 en lugar de 113) y, por tanto, cuántos no la
> tienen (24 en lugar de 28). La conclusión de fondo se mantiene e incluso se refuerza: la mayoría de los parches
> rechazados tiene forma de parche y aun así no se puede aplicar, así que el fallo no se debe solo a que el
> modelo no produzca un diff. La corrección está registrada con fecha y justificación en el diagnóstico.

---

## 5. Decisiones metodológicas y alternativas de mejora

### 5.1 ¿Por qué solo 50 tareas?
✅ **RESPALDADA**

> Es un compromiso entre diversidad, coste computacional y tiempo. Selección reproducible, con rondas por
> repositorio (20 repositorios representados, entre 1 y 3 tareas cada uno). No afirmo que sea una muestra
> estadísticamente representativa de ContextBench.

### 5.2 ¿Por qué UniXcoder y no un modelo de embeddings más reciente?
✅ **RESPALDADA**

> Inicialmente consideré `Salesforce/SFR-Embedding-Code-400M_R`, pero tuvo incompatibilidades con el entorno.
> Como el objetivo es comparar **estrategias** y no modelos de embeddings, elegí UniXcoder con una
> configuración fija. Reconozco que mi conclusión sobre "semántica" se refiere a esta instancia concreta.

### 5.3 ¿Por qué chunking por funciones?
✅ **RESPALDADA**

> Para tener unidades comparables y deterministas usando la estructura sintáctica de Python, igual para las
> tres estrategias. Limitación: el código a nivel de módulo y las importaciones no son unidades
> independientes, lo que puede perjudicar a algunas tareas.

### 5.4 ¿Por qué no cambió el prompt al ver tantos parches inválidos?
✅ **RESPALDADA**

> Para no introducir una variable nueva a mitad del experimento y mantener comparables las tres estrategias.
> El objetivo era medir el efecto del contexto, no optimizar la generación. Pero reconozco que esa decisión
> dejó la segunda fase con poca información, y por eso mi director sugiere abordarla.

### 5.5 ¿Cómo mejoraría la evaluación con el LLM?
🟡 **PARCIAL** (la línea) · ⏳ (su efecto) (actualizada el 2026-11-12)

> Una opción es pedir un formato de edición más robusto, como bloques de búsqueda y reemplazo o la función completa
> reescrita, y que el pipeline construya el parche, aplicado igual a las tres estrategias. Es una **hipótesis**: de
> los 96 fallos de contexto o corrupt, en 50 el modelo vio todos los ficheros que modificó (ahí un formato de edición
> podría ayudar), pero en 46 editó ficheros que no vio, y eso apunta más a la recuperación y al procedimiento. No lo he
> probado y lo dejo como trabajo futuro.

### 5.6 ¿Cambiaría cómo se guardan los parches?
🟡 **PARCIAL** (actualizada el 2026-11-12)

> Sí, si se repite el experimento: guardar con finales de línea LF explícitos y normalizar prefijos. La matriz indica
> que el efecto del CRLF es pequeño (2 de 123), pero es una corrección barata que elimina una fuente de discrepancia
> entre el filtro y los evaluadores. Se documentaría como corrección del protocolo, no del resultado.

### 5.7 ¿Por qué no hizo ajuste de hiperparámetros?
✅ **RESPALDADA**

> Para evitar adaptar la configuración a las tareas evaluadas y mantener las condiciones comunes. UniXcoder
> se usa en modo encoder-only con parámetros fijos; BM25 y RRF también con valores fijos (RRF con k = 60 y
> profundidad 100).

---

## 6. Limitaciones y conclusiones defendibles

### 6.1 ¿Cuáles son las principales limitaciones?
✅ **RESPALDADA**

> Muestra pequeña de 50 tareas en Python; un solo modelo y una sola generación por condición; K = 10 fijo en
> la fase LLM; chunking solo por funciones; recuperación estática; y, sobre todo, que el 94 % de los parches
> no es aplicable, lo que limita el análisis downstream. A esto añado el hallazgo sobre el entorno de
> comprobación (Windows, CRLF) frente al evaluador oficial.

### 6.2 ¿Qué conclusiones puede defender con seguridad?
✅ **RESPALDADA**

> 1. En mi muestra, BM25 obtiene los valores medios de F1 más altos; RRF se acerca y UniXcoder queda por debajo.
> 2. Al aumentar K, sube la cobertura y baja la precisión y el F1, en las tres estrategias.
> 3. Recuperar contexto adecuado no garantiza resolver la incidencia: 9 de 150 llegan a evaluación funcional
>    y 2 se resuelven.
> 4. La mayor parte de los fallos de la fase LLM se produce **antes** de poder juzgar la solución, en la
>    aplicación del parche.

### 6.3 ¿Qué no puede defender?
✅ **RESPALDADA**

> Que BM25 sea significativamente mejor (falta la prueba estadística); que BM25 *cause* más resoluciones (hay
> 2 casos); que la recuperación semántica sea peor en general (solo evalúo UniXcoder con una configuración);
> que los 141 `invalid_patch` sean errores del modelo (parte puede ser formato o entorno); y que los
> resultados se mantengan en otros lenguajes, repositorios o modelos.

### 6.4 ¿Qué aporta entonces el trabajo?
✅ **RESPALDADA**

> Un procedimiento común y reproducible para comparar estrategias de recuperación en dos niveles, recuperación
> y resolución; una comparativa de tres estrategias bajo las mismas condiciones; y un análisis honesto de
> por qué la segunda fase aporta poca evidencia, con un diagnóstico documentado de las causas.

### 6.5 Si tuviera más tiempo, ¿qué haría primero?
🟡 **PARCIAL**

> 1. Una prueba de significación pareada (Wilcoxon o bootstrap) sobre el F1 por tarea.
> 2. Medir cuántos de los 141 aceptaría un evaluador tolerante (alternativas de Verified y PolyBench) y ejecutarlo en Linux/Docker.
> 3. Rediseñar el formato de salida del modelo y repetir la fase LLM igual para las tres estrategias.
> 4. Después, ampliar tareas, modelos y valores de K.

---

## 7. Diagnóstico de aplicabilidad: conclusiones definitivas (2026-11-12)

Diagnóstico **cerrado** el 2026-11-12 (Diagnóstico, secciones 14.14 y D-004). Todo lo de esta sección es aplicabilidad
medida con `git apply --check` sobre una reconstrucción; **no** es aceptación del evaluador oficial ni resolución
funcional. Los resultados originales no cambian.

### 7.1 ¿Cuál es la conclusión definitiva del diagnóstico?
✅ **RESPALDADA**

> Los 141 `invalid_patch` son reproducibles como resultado del filtro que apliqué (150 de 150 en la línea base). Su
> causa principal no es el entorno: ni las rutas ni el CRLF explican más de 11 de los 141 (7,8 %), y 130 no pasan la
> comprobación en ninguna de las ocho condiciones. Lo que domina (96 de los 123 con `-p` natural) son parches cuyo
> contexto o estructura no coinciden con el código, de origen no determinado. El resultado downstream original (141, 7,
> 2) se mantiene.

### 7.2 ¿Se debieron los 141 al CRLF o al entorno de Windows?
✅ **RESPALDADA** (bajo comprobación estricta)

> No. Con parche LF, árbol LF y `-p1` (la combinación más parecida al evaluador), 0 de los 141 pasan la comprobación;
> el CRLF solo cambia el resultado en 2 de 123 cuando se usa el `-p` natural. Lo que sí muestra es que un parche CRLF
> contra un árbol LF falla, pero los evaluadores reciben el parche en LF (inspección de código, no ejecutada).

### 7.3 ¿Qué pasaría si se corrigieran los prefijos?
✅ **RESPALDADA** (aplicabilidad) · ⏳ (resolución)

> Con el `-p` natural de cada parche, pasarían la comprobación 11 de 123 (8,9 %) con parche LF, frente a 9 en el filtro
> original reconstruido y 0 de 141 con `-p1`. Esos 11 no se han evaluado funcionalmente: no sé si resolverían la
> incidencia ni si el evaluador los aceptaría.

### 7.4 ¿De quién es la culpa de los 96 parches con contexto o estructura incorrectos?
🟡 **PARCIAL**

> No lo atribuyo automáticamente al modelo. Pudo influir el modelo, el prompt (solo pide un unified diff y el modelo ve
> fragmentos), el formato de salida y el procedimiento (recuperación estática, sin acceso al repositorio). Como dato
> exploratorio a nivel de fichero: en 46 de los 96 el parche edita al menos un fichero que no estaba en el contexto
> recuperado; en 50 todos sus ficheros sí estaban. No lo he comprobado a nivel de línea ni frente al gold context.

### 7.5 ¿Qué estrategia genera parches más aplicables?
✅ **RESPALDADA** (que no se afirma)

> Con el `-p` natural pasan la comprobación 4 de 41 (BM25), 1 de 42 (UniXcoder) y 6 de 40 (RRF). Son diferencias
> descriptivas con recuentos pequeños y las mismas 50 tareas en las tres estrategias; no he hecho contraste
> estadístico y no las presento como significativas.

### 7.6 ¿Qué diferencia hay entre pasar la comprobación, ser aceptado por el evaluador y resolver la tarea?
✅ **RESPALDADA**

> Tres niveles. (1) Pasar `git apply --check` en mi reconstrucción: lo que he medido. (2) Que el evaluador oficial lo
> acepte: depende de su procedimiento (Linux, `-p1`, alternativas de aplicación) que no ejecuté ni modelé. (3) Resolver:
> que el parche, ya aplicado, haga pasar las pruebas de la tarea. Solo 2 de los 150 llegan a este nivel.

### 7.7 ¿Por qué cerró el diagnóstico sin repetir la generación ni probar evaluadores tolerantes?
🟡 **PARCIAL** (decisión de alcance)

> Porque el objetivo era distinguir errores de generación de efectos del entorno, y eso ya está acotado: el entorno
> explica poco. Probar evaluadores tolerantes o un formato de edición alternativo exige nuevas ejecuciones y
> generaciones, fuera del plazo; los dejo como trabajo futuro justificado con estos datos.

### 7.8 ¿Cómo garantiza que el diagnóstico no alteró los resultados originales?
✅ **RESPALDADA**

> Todo fue de solo lectura sobre los repositorios y los resultados: reconstrucción en un directorio temporal fuera de
> cualquier repositorio, lista blanca de comandos de Git y comparación de hashes de los 150 parches, los resultados y
> `HEAD` e índices de los 20 repositorios antes y después. Los manifiestos y registros históricos se conservan y las
> correcciones quedan anotadas con fecha.

---

## Frases de seguridad para la defensa

- *"Eso lo he comprobado y los datos están en el repositorio."* (solo para lo etiquetado ✅)
- *"Tengo una hipótesis, pero no la he verificado; lo dejo como trabajo pendiente."* (⏳)
- *"Con 2 casos resueltos no puedo establecer una relación causal; lo presento de forma descriptiva."*
- *"Esa diferencia es pequeña y todavía no he calculado su significación estadística."*
- *"Mi comprobación de aplicabilidad no replica exactamente el entorno del evaluador oficial; lo declaro como limitación."*

## Antes de la defensa: revisar y actualizar

- [ ] Si se repite la fase LLM o se cambia el formato de salida, reescribir las secciones 1, 2, 4.3 y 5.5.
- [ ] Si se hace la prueba de significación, reescribir 4.2 y la conclusión 6.2.1.
- [x] Efecto de CRLF y prefijos cuantificado con la matriz completa: 3.2, 3.4, 3.6, 3.8 y 4.4 actualizadas (2026-11-12). Pendiente: si se ejecutara el evaluador oficial o uno tolerante, reescribir 3.4, 3.6 y la sección 7.
- [ ] Actualizar la sección 7 y la tabla de cifras si se corrige alguna cifra al incorporar el diagnóstico a la memoria.
- [ ] Contrastar las cifras con la versión final de la memoria (los números cambiarán si se repite el experimento).
- [ ] Comprobar si el director espera que la memoria final recoja estos hallazgos.
- [ ] Actualizar la memoria (sección 6.5, "113 de los 141") a 117, con 24 sin diff, y mantener las preguntas 1.6 y 4.6 coherentes con lo que finalmente figure en ella.
