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
| Recuperados con `git apply --check -p0` | 9 de 94 | Diagnóstico, sec. 7 |
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
🟡 **PARCIAL**

> Ambos influyen. Del lado del pipeline he confirmado dos factores: el prompt solo pide "un unified diff", sin
> ninguna convención de rutas, y los 150 parches están guardados con finales de línea CRLF por escribir en
> modo texto en Windows. Del lado del modelo, 24 respuestas son rechazos en texto (el modelo dice que el
> contexto no contiene el código necesario) y 72 son diffs mal formados (41 corruptos, 24 con contexto que no
> coincide y 7 sin cabecera); los 45 restantes apuntan a un fichero inexistente, en 44 casos por la ruta sin prefijo. **No he cuantificado** cuánto del fallo total es atribuible a cada lado; esa
> prueba (normalizar a LF y repetir la comprobación) está pendiente.

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
✅ **RESPALDADA** (como dato) · 🟡 (como causa total)

> 94 de los 141 parches no llevan prefijos, y 44 de ellos fallan con "fichero inexistente". Pero al repetir la
> comprobación con `-p0` (rutas tal cual), **solo 9 de los 94 pasan**. El resto sigue fallando por contenido:
> 36 corruptos, 34 con contexto que no coincide, 7 sin cabecera, 7 sin diff y 1 fichero inexistente. Por tanto
> el prefijo explica una parte pequeña (menos del 10 %) y no el grueso de los fallos.

### 3.3 ¿Por qué los parches aplicables llevan prefijo y los otros no?
🟡 **PARCIAL**

> El dato es que los 9 aplicables llevan `a/` y `b/`, y ninguno de los que no los llevan llegó a la
> evaluación. La explicación probable es que el modelo a veces sigue la convención de Git y a veces escribe
> la ruta tal cual aparece en el contexto, pero **no he analizado por qué elige una u otra**.

### 3.4 ¿Qué pasa con LF y CRLF?
✅ **RESPALDADA** (hechos) · 🟡 (efecto)

> Hay dos hechos. Primero, `core.autocrlf=true` en mi Git global: los ficheros del repositorio se escriben
> con CRLF en el árbol de trabajo aunque estén en LF en el commit. Segundo, los 150 `patch.diff` están
> guardados con CRLF. Que esto afecte a la aplicabilidad es plausible, y lo vi: ciertos parches pasan contra
> ficheros CRLF y no contra LF. Pero **no he cuantificado cuántos de los 141 fallos son artefacto del
> guardado en Windows**.

### 3.5 ¿Por qué se guardaron los parches con CRLF?
⏳ **PENDIENTE**

> Mi hipótesis es que `Path.write_text` en Windows convierte `\n` en `\r\n`. Lo he observado en los bytes de
> los archivos, pero no he reproducido la causa de forma controlada.

### 3.6 ¿Su comprobación de aplicabilidad es equivalente a la del evaluador oficial?
🟡 **PARCIAL**

> No necesariamente. Mi comprobación se hizo en Windows con árboles de trabajo en CRLF; los evaluadores
> oficiales corren en contenedores Linux con LF. Los 9 parches aplicables sí pasaron por el evaluador
> oficial, así que esos resultados son sólidos. Para los 141 restantes, el estado `invalid_patch` es correcto
> **según el criterio que apliqué**, pero no he demostrado que el evaluador oficial los hubiera rechazado en
> todos los casos. Es una limitación que declaro.

### 3.7 ¿Cómo garantiza la reproducibilidad?
✅ **RESPALDADA** (selección y registros) · 🟡 (entorno)

> La muestra se selecciona con semilla fija (42), se conserva en `results/final_tasks.csv`, y se guardan el
> prompt, el parche y los metadatos de cada condición. La reproducibilidad **bit a bit** del LLM no está
> garantizada (una sola generación por condición con un modelo remoto), y el comportamiento de `git apply`
> depende de la configuración de Git y del sistema operativo, como acabo de ver con `autocrlf`.

### 3.8 ¿Cómo comprobó el efecto de LF/CRLF sin repetir el experimento?
✅ **RESPALDADA**

> Reconstruí en una carpeta temporal solo los ficheros que cada parche modifica, tomados del `base_commit`
> con `git show`, aplicando las reglas de `autocrlf` y `.gitattributes`, y ejecuté únicamente `git apply
> --check`. Validé el método con los 39 casos en los que podía comparar con el repositorio real: coinciden
> los 39 en estado y en mensaje de error. No modifiqué repositorios, parches ni resultados.

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
🟡 **PARCIAL**

> Lo están según el criterio de `git apply --check` que apliqué y con el mensaje de Git conservado. Lo que no
> puedo afirmar todavía es que el evaluador oficial en Linux hubiera dado el mismo veredicto en todos. Por
> eso la comprobación con parches normalizados a LF es el siguiente paso.

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
🟡 **PARCIAL** (la línea) · ⏳ (su efecto)

> Una opción es pedir al modelo un formato de edición más robusto, como bloques de búsqueda y reemplazo o la
> función completa reescrita, y que el pipeline construya el parche. Se aplicaría igual a las tres
> estrategias y se justificaría como corrección del formato de salida, no del modelo. Los datos apuntan en
> esa dirección porque la mayoría de los fallos restantes son de contenido del diff (corruptos y contexto),
> pero **no he probado** que mejore el resultado.

### 5.6 ¿Cambiaría cómo se guardan los parches?
⏳ **PENDIENTE**

> Sí, si se repite el experimento: guardar con finales de línea LF explícitos y normalizar antes de aplicar.
> Cualquier cambio se aplicaría igual a las tres estrategias y se documentaría como corrección del
> protocolo, no del resultado.

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
> 2. Repetir la comprobación de aplicabilidad en entorno LF y comprobar cómo aplican los evaluadores oficiales.
> 3. Rediseñar el formato de salida del modelo y repetir la fase LLM igual para las tres estrategias.
> 4. Después, ampliar tareas, modelos y valores de K.

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
- [ ] Si se confirma el efecto de CRLF en el entorno oficial, reescribir 3.4, 3.5, 3.6 y 4.4.
- [ ] Contrastar las cifras con la versión final de la memoria (los números cambiarán si se repite el experimento).
- [ ] Comprobar si el director espera que la memoria final recoja estos hallazgos.
- [ ] Actualizar la memoria (sección 6.5, "113 de los 141") a 117, con 24 sin diff, y mantener las preguntas 1.6 y 4.6 coherentes con lo que finalmente figure en ella.
