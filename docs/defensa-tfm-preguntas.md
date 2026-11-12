# Preparación de la defensa del TFM: preguntas del tribunal y respuestas

Material de estudio para la exposición. Complementa el informe técnico
[`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md) y no sustituye a la memoria.

**Cómo leerlo.** Cada respuesta lleva una etiqueta:

| Etiqueta | Significa | Qué puedes hacer en la defensa |
|---|---|---|
| ✅ **RESPALDADA** | Se apoya en resultados del experimento o en comprobaciones ya realizadas. | Afirmarla con seguridad. |
| 🟡 **PARCIAL** | Parte es dato y parte depende de una prueba pendiente. | Dar el dato y decir claramente qué falta. |
| ⏳ **PENDIENTE** | Depende de comprobaciones que aún no se han hecho. | Presentarla como línea de trabajo o hipótesis, nunca como resultado. |

**Cómo está organizado.**
- **Banco de preguntas del tribunal (secciones 1 a 7):** preguntas con respuestas breves y orales, para la defensa.
- **Preparación técnica del piloto P1 (sección 9):** cinco preguntas sobre el filtro G, la comparación justa entre `O1n` y `E1`, la
  evaluación funcional y el hallazgo de `strip()`. El piloto **no se ha ejecutado**.
- **Guía de estudio del diagnóstico downstream (sección 8):** explicaciones paso a paso para *entender* qué hicimos, por qué,
  cómo lo comprobamos y qué se puede defender. Termina con un resumen de un minuto, cinco ideas clave, un glosario y los
  errores que hay que evitar.
- **Regla para no duplicar:** si ya existía una pregunta equivalente en el banco, la **respuesta oral** sigue en esa pregunta y
  la **explicación para estudiar** está en la guía (cada pregunta del banco lleva una remisión). Las preguntas nuevas llevan
  ambas cosas en la guía.

**Ruta de estudio recomendada** (léela en este orden; P1 a P16 son las preguntas de la guía):

| Bloque | Pregunta de la guía | Respuesta oral |
|---|---|---|
| 1. El problema que señaló Pablo | P1 ¿Por qué solo 9 de 150 llegaron a la evaluación funcional? | 1.1 |
| | P2 ¿Qué significa realmente `invalid_patch`? | Guía (8.1) |
| 2. Qué descubrimos en los 141 rechazos | P3 Causas de rechazo | Guía (8.2); ver también 1.3 y 1.6 |
| | P4 Problema con las rutas · P6 CRLF y LF | 3.1 · 3.4 |
| | P5 Diferencia entre `-p0` y `-p1` | Guía (8.2) |
| 3. Cómo hicimos las 1.800 comprobaciones | P7 De dónde salen las 1.800 | Guía (8.3) |
| | P8 Cómo se ejecutaron · P9 Reproducibilidad | 3.8 · 3.7 |
| 4. Qué descubrimos con la matriz | P10 Cuántos parches se recuperan · P11 Recuperar no es resolver · P12 Ficheros que recibió el modelo | 7.3 · 2.6 · 7.4 |
| 5. Limitaciones y preguntas difíciles | P13 Por qué no en Linux · P15 ¿Qué estrategia es mejor? | Guía (8.5); ver también 2.3, 4.2 y 7.5 |
| | P14 `git apply --check` frente a evaluación funcional · P16 Mejoras | 7.6 · 5.5 |
| 6. Para repasar | Resumen de un minuto, cinco ideas, glosario y errores a evitar | Guía (8.6) |

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
| Parches sin prefijo `a/` `b/` | 94 de los 141 (93 con `-p` natural y 1 mixto; los 9 aplicables sí lo llevan) | Diagnóstico, sec. 3 |
| Recuperados con `git apply --check -p0` (reconstrucción CRLF, observación previa) | 9 de 94 | Diagnóstico, sec. 7 |
| Matriz completa, `-p` natural, de 123 `invalid_patch` | Filtro original reconstruido (CC): 9 · parche LF y árbol CRLF (LC): 11 · parche CRLF y árbol LF (CL): 0 · parche LF y árbol LF (LL): 11 | Diagnóstico, sec. 14.2 |
| Matriz completa, `-p1` (el de los evaluadores) | 0 de 141 aplican en las cuatro combinaciones CRLF/LF; los 9 controles aplican en CC, LC y LL | Diagnóstico, sec. 14.4 |
| No aplican en ninguna de las 8 celdas | 130 de 141 (92,2 %) | Diagnóstico, sec. 14.14 |
| Contexto o corrupt en LL (`-p` natural) | 96 de 123 (78 %; 68 % de los 141); en 46 de los 96 el parche edita ficheros que no estaban en el contexto recuperado (dato exploratorio) | Diagnóstico, sec. 14.6 |
| Parches guardados con CRLF | 150 de 150 | Diagnóstico, sec. 7 |
| F1 a nivel de fichero, K = 5 | BM25 0,2578 · RRF 0,2505 · UniXcoder 0,1673 | Memoria, Tablas 3-5 |
| Comprobaciones del diagnóstico | **1.800** = 1.200 (matriz principal, 150 × 8) + 600 (robustez, 150 × 4); no son generaciones ni evaluaciones funcionales | Diagnóstico, sec. 14 |
| 123 y 18 | 123 parches con `-p` natural interpretable; 18 fuera de ese análisis (17 sin cabeceras y 1 con `-p` indeterminado) | Diagnóstico, sec. 14.2 |
| Los 11 recuperables | 9 tareas en 7 repositorios; 9 necesitan solo prefijos y 2 prefijos y finales de línea; 0 cambios de contenido | Diagnóstico, sec. 15.1 |
| Ficheros que recibió el modelo (96) | 50 con todos sus ficheros en el contexto, 41 con ninguno y 5 parcialmente (46 con algún fichero no visto) | `analisis_ficheros_contexto.json` |
| Los 24 sin diff (lectura manual, orientativa) | 8 rechazos explícitos, 3 textos que argumentan falta de contexto, 2 mensajes de error, 7 solo cabeceras de fichero, 4 otros textos | Lectura de `logs/downstream/*/patch.diff` (no está en un script) |
| Bloques Markdown pese a la instrucción | 60 de 150 salidas | `analisis_anclaje_contenido.json` |

---

## 1. Los 141 parches inválidos y sus causas

### 1.1 ¿Por qué el 94 % de los parches no se pueden aplicar? (es decir, ¿por qué solo 9 de 150 llegaron a la evaluación funcional?)
✅ **RESPALDADA** (descripción) · 🟡 (causa raíz)

> «En el experimento original generamos 150 parches, pero 141 fueron rechazados por una comprobación previa de
> aplicabilidad. Para investigar esta limitación realizamos un diagnóstico reproducible que distinguía problemas de
> rutas, finales de línea y estructura de los parches. Comprobamos que 11 de los 141 parches rechazados podían superar
> una comprobación de aplicabilidad bajo condiciones alternativas, aunque eso no garantiza que resolvieran las tareas.
> También encontramos casos en los que el modelo intentaba modificar ficheros ausentes del contexto recuperado. Por
> tanto, concluimos que los resultados funcionales deben interpretarse con cautela y que es necesario distinguir entre
> la calidad de la recuperación, la generación del parche y su aplicación».
>
> Datos de apoyo: el filtro `git apply --check` clasificó los 141 por el mensaje de Git en 45 fichero inexistente, 41
> parche corrupto, 24 sin diff, 24 contexto que no coincide y 7 fragmentos sin cabecera. Visto de otro modo, 117 de los
> 141 (83 %) tienen estructura de parche que Git reconoce y 24 (17 %) no contienen diff. No es, por tanto, solo un
> problema de formato: la causa última (modelo, prompt, formato de salida o recuperación) **no está determinada**.

*Si la pregunta es «¿no invalida eso las conclusiones del experimento?»: ver la respuesta oral y la precisión en 4.3.*

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
✅ **RESPALDADA** (qué son, por lectura manual) · ⏳ (por qué)

> No son todos iguales. Leyendo los 24 textos: **8** son un rechazo explícito («I cannot… porque el contexto recuperado
> no contiene…»), **3** son explicaciones largas que argumentan que falta contexto, **2** son mensajes de error del propio
> proceso («Failed to generate patch. No context files available…»), **7** contienen solo las dos líneas de cabecera de
> fichero (`---` y `+++`) sin ningún hunk, es decir, un parche vacío, y **4** son otro texto o razonamiento sin diff. En
> unos 13 el texto dice expresamente que falta contexto, pero **no lo he comprobado** contra el gold context: que el "sin
> diff" se deba a una recuperación insuficiente es una hipótesis. Esta clasificación es una lectura manual y **no está en
> un script**.

### 1.4 ¿Cómo los clasificó y de dónde salen los números?
✅ **RESPALDADA**

> De los 150 `patch.diff` y del campo `detail` del fichero de resultados, que conserva el mensaje completo de
> `git apply --check` de cada parche. La clasificación es reproducible con un script de solo lectura
> (`classify_invalid_patches.py`) y queda tabulada por tarea y estrategia en un CSV.

### 1.5 ¿Hay alguna estrategia de recuperación con más parches inválidos?
✅ **RESPALDADA**

> No de forma relevante: 47 con BM25, 48 con UniXcoder y 46 con RRF. El problema es transversal a las tres,
> que no depende de una estrategia concreta. Por sí solo no permite decir si el origen es la generación, el prompt o la
> recuperación.

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

*Para estudiarla con más detalle: guía de estudio, **P11** (sección 8.4).*

---

## 3. Prefijos de rutas, `git apply`, LF/CRLF y reproducibilidad

### 3.1 ¿Qué son los prefijos `a/` y `b/` y por qué importan?
✅ **RESPALDADA**

> Un diff de Git suele escribir las rutas como `a/ruta` y `b/ruta`. `git apply` por defecto usa `-p1`, que
> elimina el primer componente de cada ruta. Si el diff no lleva esos prefijos, Git quita en realidad el
> primer directorio real (por ejemplo `src/` en `src/_pytest/pastebin.py`) y busca un fichero que no existe.

*Para estudiarla con más detalle: guía de estudio, **P4** (sección 8.2).*

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

*Para estudiarla con más detalle: guía de estudio, **P6** (sección 8.2).*

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
✅ **RESPALDADA** (selección, registros y comprobaciones) · 🟡 (entorno)

> La muestra se selecciona con semilla fija (42) y se conserva en `results/final_tasks.csv`; se guardan el prompt, el
> parche y los metadatos de cada condición. En el diagnóstico: (1) la línea base reprodujo **exactamente los 150
> resultados originales**, incluidos los mensajes de error; (2) los resultados por celda, los agregados y el manifest
> están conservados en `diagnostics/downstream-patches/data/matriz_completa_20261112T000024Z/`; (3) los scripts están
> versionados; (4) se compararon los hash SHA-256 de los parches y de los resultados originales antes y después; y (5) se
> comprobó que `HEAD` y el índice de los 20 repositorios no cambiaron. Además, el piloto de 84 comprobaciones coincidió con la
> matriz completa (esta comparación se hizo sobre ficheros locales que no están versionados). Lo que **no** está
> garantizado: la reproducibilidad bit a bit del LLM (una sola generación con un modelo remoto) ni que el diagnóstico
> reproduzca el entorno Linux/Docker de los evaluadores.

*Para estudiarla con más detalle: guía de estudio, **P9** (sección 8.3).*

### 3.8 ¿Cómo comprobó el efecto de LF/CRLF sin repetir el experimento?
✅ **RESPALDADA** (actualizada el 2026-11-12)

> «Para investigar los problemas de aplicabilidad desarrollé un script en Python que automatizaba una matriz de pruebas.
> Utilicé los 150 parches originales y varié tres factores: los finales de línea del parche, los finales de línea de los
> archivos y la opción de Git para interpretar las rutas. Esto produjo ocho combinaciones por parche, es decir, 1.200
> comprobaciones. Añadí otras 600 para comprobar la influencia de la configuración `core.autocrlf` de Git. En cada caso
> ejecuté `git apply --check`, que permite comprobar la aplicabilidad sin aplicar realmente el parche. Registré los
> resultados y verifiqué que los archivos originales no se modificaran. Además, validé que el script reprodujera
> exactamente los 150 resultados iniciales antes de interpretar las nuevas condiciones».

*Para estudiarla con más detalle: guía de estudio, **P7** y **P8** (sección 8.3).*

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

### 4.3 ¿Se pueden fiar de la evaluación con el LLM? ¿Por qué solamente 9 de los 150 parches llegaron a evaluarse funcionalmente? ¿No invalida eso las conclusiones del experimento?
🟡 **PARCIAL** (ampliada el 2026-11-12)

> Los 9 casos evaluados funcionalmente son fiables. Pero 141 de 150 condiciones no llegaron a esa evaluación,
> así que la segunda parte aporta **muy poca información comparativa**. Lo reconozco en las limitaciones, y
> mi director me propuso mejorarlo antes de la entrega final.

**Respuesta oral.** «Detectamos esa limitación y realizamos un diagnóstico adicional reproducible. Ejecutamos 1.800
comprobaciones de aplicabilidad y descubrimos que parte de los rechazos estaba relacionada con la interpretación de rutas y
otros problemas de los parches. También identificamos dificultades relacionadas con el contenido recuperado.

Esto nos permitió explicar mejor los resultados y sus limitaciones, aunque todavía no demuestra una mejora en la resolución
funcional».

**Precisión fundamental.** Los 141 rechazos **limitan las conclusiones sobre resolución funcional**, pero **no invalidan
automáticamente** los resultados independientes de la evaluación de recuperación de contexto (cobertura, precisión y F1 de
BM25, UniXcoder y RRF), que se calculan antes y con independencia del LLM (pregunta 4.1). Lo que sí queda sin respaldo es
cualquier afirmación sobre qué estrategia ayuda más a *resolver* incidencias.

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

> Hay dos líneas de naturaleza distinta. **A. Recuperar mecánicamente** parches ya generados, normalizando rutas y finales
> de línea: según el diagnóstico, 11 de los 141 pasarían la comprobación, pero no sabemos si resolverían la tarea. **B.
> Probar un formato de edición alternativo** (bloques de búsqueda y reemplazo literales que el pipeline convierte en
> parche), con el mismo contexto y modelo. B es una **hipótesis**. De los 96 fallos de contexto o corrupt, en 50 el modelo
> vio todos los ficheros que modificó y en 46 intentó editar al menos uno que no vio; y, como dato distinto, solo 20 de los
> 96 tienen todos sus hunks anclados por contenido en el repositorio (24 algunos y 51 ninguno). Son cifras exploratorias que
> **no predicen** cuánto mejoraría un formato nuevo: un formato de edición podría corregir problemas mecánicos (rutas,
> cabeceras, conteos), pero no hace que el texto citado exista ni que el modelo vea el fichero (la diferencia entre ver,
> citar, aplicar y resolver se explica en 7.4). El diagnóstico D-004 está **cerrado**; el protocolo del piloto P1 (D-005) y el
> análisis secundario S1 son **propuestas**: **no están aprobados ni ejecutados**.

*Para estudiarla con más detalle: guía de estudio, **P16** (sección 8.5). La preparación técnica del piloto (filtro G, comparación
justa y evaluación funcional simulada) está en la sección 9.*

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

*Para estudiarla con más detalle: guía de estudio, **P10** (sección 8.4).*

### 7.4 ¿De quién es la culpa de los 96 parches con contexto o estructura incorrectos?
🟡 **PARCIAL** (ampliada el 2026-11-12)

> No lo atribuyo automáticamente al modelo. Pudo influir el modelo, el prompt (solo pide un unified diff y el modelo ve
> fragmentos), el formato de salida y el procedimiento (recuperación estática, sin acceso al repositorio). Como dato
> exploratorio a nivel de fichero: en 46 de los 96 el parche edita al menos un fichero que no estaba en el contexto
> recuperado; en 50 todos sus ficheros sí estaban. No lo he comprobado a nivel de línea ni frente al gold context.

**Cuatro cosas que no hay que confundir** (cada una exige más que la anterior):

| Nivel | Pregunta | Qué dicen los datos de estos 96 (exploratorio) |
|---|---|---|
| 1. El modelo **vio el fichero** | ¿Estaba en el contexto recuperado? | 50 vieron todos sus ficheros; 46 intentaban editar al menos uno que no vieron |
| 2. El contenido citado **existe** en ese fichero | ¿Aparece, tal cual, el texto que el parche cita (contexto y líneas eliminadas)? | 20 tienen todos sus hunks anclados; 24 solo algunos; 51 ninguno; 1 no verificable |
| 3. El parche **puede aplicarse** | ¿Pasa `git apply --check`? | Estos 96 no (son los que fallan por contexto o estructura); los 11 que sí pasan no están entre ellos |
| 4. La solución **resuelve** la incidencia | ¿Superan las pruebas de la tarea? | No medido para ninguno de ellos; solo 2 de los 150 parches resolvieron |

**Ejemplo sencillo** (inventado para entender, no es un caso real). El modelo recibe el fichero `ventas.py`, donde la función
`calcular_total` termina en `return total * (1 + impuesto)`. Su parche quita la línea `return total + impuesto`.
- Nivel 1: **cumplido**, vio el fichero.
- Nivel 2: **falla**, porque esa línea no existe tal cual en `ventas.py`; haber visto el fichero no garantiza citarlo bien.
- Nivel 3: por eso Git no puede aplicar el parche, aunque la idea fuera buena.
- Si hubiera citado la línea correcta, el parche se aplicaría (nivel 3), pero solo las pruebas dirían si arregla el error
  (nivel 4). Y si nunca hubiera recibido `ventas.py`, solo podría acertar adivinando el código de memoria.

Por eso, en los datos, que 50 de los 96 vieran todos sus ficheros no significa que esos 50 tuvieran el código bien citado
(solo 17 de ellos anclan del todo), y que 46 no los vieran no significa que fueran casos perdidos (3 de ellos sí anclan).

**Respuesta oral.** «Hay cuatro cosas distintas: que el modelo haya visto el fichero, que el texto que cita el parche exista
de verdad en él, que el parche pueda aplicarse y que la solución resuelva la incidencia. En los 96 fallos, 50 habían visto
todos sus ficheros pero solo 20 tenían todos sus bloques anclados en el repositorio. Por eso no atribuyo el fallo
automáticamente al modelo ni solo al formato, y no afirmo nada sobre la resolución. Son análisis exploratorios, a nivel de
fichero y de contenido, y no predicen lo que ocurriría con nuevas generaciones».

*Para estudiarla con más detalle: guía de estudio, **P12** (sección 8.4).*

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

*Para estudiarla con más detalle: guía de estudio, **P14** (sección 8.5).*

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

## 8. Guía de estudio del diagnóstico downstream

Esta sección es para **entender**, no para memorizar. Cada pregunta tiene una explicación para estudiar y la evidencia donde
se puede comprobar; las respuestas orales están en la pregunta del banco (secciones 1 a 7) o, si es nueva, aquí mismo.

**El mapa mental que lo ordena todo** (si te pierden en la defensa, vuelve a este esquema):

```
Incidencia + repositorio
   │
   ├─ [1] RECUPERACIÓN de contexto     BM25 · UniXcoder · RRF            → se mide con cobertura, precisión y F1
   ├─ [2] GENERACIÓN del parche        un parche por tarea y estrategia  → 50 tareas × 3 = 150 parches
   ├─ [3] APLICABILIDAD                filtro `git apply --check`        → aquí se quedan 141 (`invalid_patch`)
   └─ [4] RESOLUCIÓN FUNCIONAL         pruebas oficiales de la tarea     → solo 9 llegan: 2 `resolved`, 7 `not_resolved`
```

**Dónde está la evidencia** (todo versionado salvo lo indicado):
- Resultados originales: `results/downstream_results_final.jsonl`; el filtro, en `src/downstream/evaluation.py`.
- Diagnóstico completo: `docs/downstream-patch-diagnostics.md` y `diagnostics/downstream-patches/`.
- Datos de la matriz: `diagnostics/downstream-patches/data/matriz_completa_20261112T000024Z/` (`cells.jsonl`, `controls.json`,
  `analisis.md`, `manifest.json`…). Los análisis `analisis_anclaje_contenido.json` y `analisis_referencia.json` y los modos
  `--anclaje-contenido` y `--referencia` del script de análisis ya están versionados (commit `67d391b`).

### 8.1 Bloque 1. El problema que nos señaló Pablo

#### P1. ¿Por qué solamente 9 de los 150 parches llegaron a la evaluación funcional?
✅ **RESPALDADA** · *Respuesta oral: pregunta 1.1.*

**Para estudiar.**
- Comparamos **tres métodos de recuperación de contexto**: **BM25** (busca coincidencias de palabras entre la incidencia y
  el código), **UniXcoder** (usa representaciones semánticas del código, es decir, compara significados y no solo palabras) y
  **RRF** (combina los rankings de los otros dos).
- Usamos **50 tareas** y generamos **un parche por tarea y estrategia**: 50 × 3 = **150 parches**.
- Resultados originales: **141 `invalid_patch`, 7 `not_resolved` y 2 `resolved`**.
- Antes de pasar un parche a los evaluadores funcionales, el pipeline ejecuta `git apply --check`. Si falla, el parche se marca
  como `invalid_patch` y **no llega** a evaluarse. Por eso solo **9** parches llegaron a esa fase (7 + 2).
- **Por qué importa la preocupación de Pablo:** con 9 parches evaluados, la parte funcional casi no permite comparar qué
  estrategia de recuperación ayuda más a resolver incidencias. Los 141 restantes no son "fallos funcionales": simplemente no
  se llegó a probarlos.

**Evidencia.** `results/downstream_results_final.jsonl` (150 filas); `src/downstream/evaluation.py:132-164` (el filtro) y
`610-626` (si falla, `invalid_patch` y no se llama al evaluador).

#### P2. ¿Qué significa realmente `invalid_patch`?
✅ **RESPALDADA**

**Para estudiar.** `invalid_patch` significa **una sola cosa**: el parche no superó el filtro de aplicabilidad original
(`git apply --check`, con la configuración con que se ejecutó). Una analogía: es como entregar un trabajo en un formato que el
sistema no sabe abrir; que no se abra no dice si el contenido era bueno o malo. **No significa automáticamente que:**
- el modelo no supiera resolver la incidencia,
- el método de recuperación fuera incorrecto,
- el evaluador oficial hubiera rechazado el parche,
- la solución propuesta no funcionara.

Por eso hay que mantener separadas **cuatro etapas**:

| Etapa | Pregunta que responde | Cómo se mide |
|---|---|---|
| Recuperación de contexto | ¿El contexto contiene lo relevante? | Cobertura, precisión y F1 frente al gold context |
| Generación del parche | ¿El modelo produjo una modificación? | Existe un `patch.diff` con estructura de parche |
| Aplicabilidad | ¿Git puede aplicar el parche al repositorio? | `git apply --check` |
| Resolución funcional | ¿Hace pasar las pruebas de la tarea? | Evaluador oficial: `resolved` o `not_resolved` |

**Respuesta oral.** «`invalid_patch` quiere decir que el parche no superó el filtro de aplicabilidad que usamos antes de
evaluar. No significa que el modelo no supiera resolver la incidencia, ni que el evaluador oficial lo hubiera rechazado, ni
que la solución no funcionara: significa que no pudimos llegar a probarla. Por eso distingo recuperación, generación,
aplicabilidad y resolución funcional».

### 8.2 Bloque 2. Qué descubrimos al analizar los 141 rechazos

#### P3. ¿Cuáles fueron las principales causas de rechazo?
✅ **RESPALDADA** (las categorías) · 🟡 (sus causas últimas)

**Para estudiar.** Clasificamos los 141 por el **mensaje de error de Git**. Son **categorías de error observadas en el
filtro, no necesariamente causas últimas**: por ejemplo, "fichero no encontrado" es el *síntoma*; la causa suele ser una
convención de rutas, y que el parche no se aplique no dice si su código era correcto.

| Categoría | Casos | Qué significa en sencillo | Ejemplo real |
|---|---|---|---|
| Fichero no encontrado | 45 | Git busca un fichero que no existe | `pytest-5809`: el parche escribe `src/_pytest/pastebin.py` y Git busca `_pytest/pastebin.py` |
| Parche corrupto | 41 | Git no sabe interpretar el parche (p. ej. el bloque anuncia un número de líneas y trae otro) | `pytest-5809`: `corrupt patch at line 20` |
| Sin diff | 24 | La respuesta no contiene ningún bloque de cambios | `ansible-39bd8b99`: «I cannot produce the required unified diff patch because…» |
| Contexto que no coincide | 24 | Las líneas de contexto del parche no existen tal cual en el fichero | `astropy-14598`: `patch failed: astropy/io/fits/card.py:1023` |
| Fragmento sin cabecera | 7 | Hay un bloque `@@` pero faltan las cabeceras de fichero | `openlibrary-910b…`: repite `---` y falta `+++` |

**117 frente a 24.** De los 141, **117 (83 %)** tienen una estructura que Git reconoce como parche (112 con cabeceras
completas y 5 con cabecera defectuosa) y **24 (17 %)** no tienen diff. **Tener estructura reconocible no significa que el
parche sea válido**: ninguno de esos 117 pasó el filtro con `-p1`. La cifra inicial de 113 se debía a una heurística más
tosca (pregunta 1.6).

**Los 24 sin diff no son todos iguales** (pregunta 1.3): 8 rechazos explícitos, 3 explicaciones sobre falta de contexto, 2
mensajes de error, 7 con solo cabeceras (parche vacío) y 4 otro texto.

**Evidencia.** `diagnostics/downstream-patches/data/invalid_patches_classification.csv` (una fila por condición, con el
mensaje de Git completo) y `scripts/classify_invalid_patches.py`.

#### P4. ¿Qué problema encontramos con las rutas de los ficheros?
✅ **RESPALDADA** · *Respuesta oral: pregunta 3.1.*

**Para estudiar.** Un parche en formato Git suele escribir las rutas con prefijos: `a/` para el fichero "antes" y `b/` para el
"después". `git apply` quita por defecto el **primer componente** de la ruta (`-p1`), precisamente para descartar esos prefijos.

| Cabecera del parche | Qué entiende `git apply -p1` | ¿Existe en el repositorio? |
|---|---|---|
| `--- a/src/modulo.py` | `src/modulo.py` | Sí |
| `--- src/modulo.py` (sin prefijo) | `modulo.py` | **No**: «No such file or directory» |

Es decir, Git quita `src/` creyendo que es el prefijo y busca un fichero equivocado. **El código del parche podía ser
correcto y aun así no aplicarse.** En los datos: 94 de los 141 no llevan prefijos (93 con `-p` natural y 1 mixto) y 44 de los
45 "fichero no encontrado" son de ese grupo; los 9 parches aplicables sí llevan prefijos. El prompt solo pedía «un unified
diff», sin indicar ninguna convención de rutas; **no sabemos por qué el modelo a veces escribe los prefijos y a veces no**.

**Evidencia.** `invalid_patches_classification.csv` (columnas `prefix` y `cause`); `src/downstream/generation.py` (el prompt).

#### P5. ¿Qué diferencia existe entre `-p0` y `-p1`?
✅ **RESPALDADA**

**Para estudiar.** `-pN` le dice a Git cuántos componentes iniciales de la ruta debe **eliminar**.
- **`-p0`:** no elimina ninguno. `a/src/modulo.py` se queda `a/src/modulo.py`; `src/modulo.py` se queda `src/modulo.py`.
- **`-p1`:** elimina el primero. `a/src/modulo.py` pasa a `src/modulo.py`; `src/modulo.py` pasa a `modulo.py`.

Por tanto, un parche **con** prefijos necesita `-p1` y un parche **sin** prefijos necesita `-p0`. A esa opción que corresponde
a las cabeceras reales de cada parche la llamamos su **`-p` natural**.

**Por qué fue importante y por qué no se cambió en silencio.** El filtro original usaba `-p1` y, según el código leído, los
evaluadores oficiales también usan `-p1`. Cambiar la opción del filtro sin decirlo **cambiaría la definición del experimento** y
no sabríamos si comparamos con el mismo filtro. Por eso la línea base replica `-p1` y `-p0` se usa solo como **condición
diagnóstica documentada**: responde a «¿cuántos pasarían si las rutas estuvieran bien escritas?», no «¿qué hace el
evaluador?». Reescribir los prefijos y usar `-p1` equivale en teoría a usar `-p0`; esa equivalencia no se ha comprobado todavía
sobre los parches reales.

**Evidencia.** Matriz, columnas `p` y `p_natural` de `cells.jsonl`; `docs/downstream-patch-diagnostics.md`, secciones 12 y 14.

#### P6. ¿Qué son CRLF y LF y por qué los investigamos?
✅ **RESPALDADA** · *Respuesta oral: pregunta 3.4.*

**Para estudiar.** Son dos formas de marcar el final de una línea en un fichero de texto: **LF** es un solo carácter (salto de
línea; el habitual en Linux) y **CRLF** son dos (retorno de carro y salto de línea; el habitual en Windows). Dos ficheros con el
mismo texto pero distinto final de línea no son idénticos byte a byte, y eso puede hacer que un parche no encaje.

**Por qué los investigamos.** Los **150 parches** se guardaron con CRLF (probablemente por cómo se escribieron en Windows;
es una hipótesis) y mi filtro usaba parche CRLF contra ficheros CRLF, mientras que, según el código, los evaluadores reciben
el parche en LF y corren en Linux. Había que saber si esa diferencia podía explicar los 141 rechazos.

**Qué descubrimos.**
- Con `-p1`, **ninguno** de los 141 pasa el filtro aunque se normalice a LF.
- Con su `-p` natural, el CRLF cambia si el parche pasa en solo **2 de 123** (y la categoría de error en otros 2).
- Un parche CRLF contra ficheros LF **sí** falla (8 de los 9 controles), pero los evaluadores reciben el parche ya en LF.
- Conclusión: **CRLF no era la causa principal**, aunque sí afectaba a algunos casos concretos. Esto vale **bajo
  comprobación estricta** (`git apply --check`).

**Evidencia.** `cells.jsonl` y `analisis.md` en `data/matriz_completa_20261112T000024Z/`.

### 8.3 Bloque 3. Cómo realizamos las 1.800 comprobaciones

#### P7. ¿De dónde salen exactamente las 1.800 comprobaciones?
✅ **RESPALDADA**

**Para estudiar.** Paso a paso:
1. Partimos de los **150 parches originales**. **No generamos ninguno nuevo.**
2. Variamos **tres factores**: (a) finales de línea del parche (CRLF o LF); (b) finales de línea de los archivos reconstruidos
   (CRLF o LF); (c) interpretación de las rutas (`-p0` o `-p1`).
3. 2 × 2 × 2 = **8 combinaciones** por parche, y 150 × 8 = **1.200** comprobaciones de la **matriz principal**.
4. **Réplica de robustez:** repetimos las combinaciones sobre archivos LF con `core.autocrlf=false` (parche CRLF o LF, `-p0` o
   `-p1`: 4 combinaciones) y 150 × 4 = **600**.
5. Total: 1.200 + 600 = **1.800**.

| Factor | Niveles | Combinaciones |
|---|---|---|
| Parche | CRLF · LF | |
| Archivos reconstruidos | CRLF · LF | 2 × 2 × 2 = 8 por parche |
| Rutas | `-p0` · `-p1` | |
| Robustez (`autocrlf=false`, solo archivos LF) | parche CRLF/LF × `-p0`/`-p1` | 4 por parche |

**Qué es `core.autocrlf`.** Es una opción de Git que **convierte finales de línea** al extraer o guardar ficheros: con `true`
(típico en Windows) los ficheros extraídos pasan a CRLF aunque estén en LF en el repositorio. Quisimos controlar su influencia
porque cambia el contenido de los ficheros sobre los que se aplica el parche. Resultado: las 600 celdas de la réplica dieron
**el mismo resultado y el mismo mensaje** que las equivalentes con `autocrlf=true`.

**Aclaraciones importantes.**
- Las 1.800 comprobaciones **no son 1.800 generaciones del modelo** ni **evaluaciones funcionales**: son comprobaciones de
  aplicabilidad de los mismos 150 parches.
- La combinación «parche CRLF, ficheros CRLF, `-p1`» es el **filtro original reconstruido**: sirve de línea base.
- El piloto (84 comprobaciones) y la línea base de 150 se ejecutaron **antes y aparte**; no forman parte de las 1.800.

**Evidencia.** `cells.jsonl` (1.200 filas) y `cells_robustez_autocrlf_false.jsonl` (600 filas).

#### P8. ¿Cómo ejecutamos técnicamente las 1.800 comprobaciones?
✅ **RESPALDADA** · *Respuesta oral: pregunta 3.8.*

**Para estudiar.** Lo hizo un script de Python, `diagnostics/downstream-patches/scripts/eol_prefix_matrix.py`. **No se ejecutaron
a mano 1.800 comandos.** Para cada parche el script:
1. lee el parche original;
2. identifica el **`base_commit`** de su tarea: el estado exacto del repositorio sobre el que debe aplicarse la solución;
3. **reconstruye en una carpeta temporal** solo los ficheros que el parche puede tocar, leyéndolos de ese commit con
   `git cat-file` (sin cambiar de commit ni tocar el repositorio real);
4. prepara los ficheros con CRLF o LF (siguiendo `.gitattributes` y `core.autocrlf`) y el parche en CRLF o LF;
5. ejecuta `git apply --check` con `-p0` o `-p1`, que **comprueba sin aplicar nada**;
6. guarda si pasó y, si falló, el mensaje completo de Git.

**Garantías de seguridad y de rigor.** Solo se permiten unos pocos comandos de Git de lectura; la configuración de Git se aísla
y se fija `core.autocrlf` de forma explícita; **antes de interpretar nada** el script reproduce los 150 resultados originales
(si no coincidiera, se detiene); y al final compara los hash de los parches y resultados y el estado de los 20 repositorios.

**Evidencia.** `scripts/eol_prefix_matrix.py`, `controls.json` (control 1: 150 de 150) y `manifest.json` (integridad antes y
después).

#### P9. ¿Cómo garantizamos la reproducibilidad?
✅ **RESPALDADA** (con el matiz del piloto) · *Respuesta oral: pregunta 3.7.*

**Para estudiar.** La reproducibilidad se apoya en seis cosas: (1) la **línea base reprodujo exactamente los 150 resultados
originales**, incluidos los mensajes de error; (2) los resultados por celda, los agregados y el manifest están conservados;
(3) los scripts están versionados; (4) se comprobaron los hash de los parches y resultados originales; (5) se comprobó que
los repositorios no cambiaron; (6) el piloto de 84 comprobaciones coincidió con la matriz completa.

**Qué es SHA-256.** Una **huella digital** de un fichero: una función que resume todo su contenido en una cadena de 64
caracteres. Si cambia **un solo byte**, la huella cambia por completo. Guardamos la huella de cada parche y de los resultados
**antes** y la volvimos a calcular **después**; si coinciden, el fichero no se ha modificado.

**Dos matices honestos.** El punto (6) se comprobó sobre ficheros locales del piloto que **no están versionados**, así que
conviene presentarlo como comprobación realizada y no como evidencia ya publicada. Y **reproducibilidad no es equivalencia**:
reproducir nuestro diagnóstico no demuestra que reproduzca el entorno Linux/Docker de los evaluadores oficiales.

**Evidencia.** `controls.json`, `manifest.json` (`integridad_antes` y `integridad_despues`) y los commits del repositorio.

### 8.4 Bloque 4. Qué descubrimos con la matriz

#### P10. ¿Cuántos parches conseguimos recuperar?
✅ **RESPALDADA** · *Respuesta oral: pregunta 7.3.*

**Para estudiar.** **11 de los 141** parches rechazados pasaron `git apply --check` en alguna condición alternativa. Los
otros **130** no pasaron en **ninguna** de las 8 combinaciones de la matriz principal. El resultado principal, con el `-p`
natural de cada parche, se calculó sobre **123** parches con cabeceras interpretables; los otros **18** (17 sin cabeceras y 1
con `-p` indeterminado) quedan fuera de ese análisis concreto.

| Condición | Parches originalmente rechazados que pasan, de 123 |
|---|---|
| CC | 9 |
| LC | 11 |
| CL | 0 |
| LL | 11 |

**Cómo leer las letras:** la **primera** es el final de línea del **parche** y la **segunda** el de los **archivos**; **C** es
CRLF y **L** es LF. Así, CC es el filtro original reconstruido y LL es parche y archivos en LF.

**Lo esencial.**
- El filtro original usaba `-p1` y **ninguno de los 141** pasó con `-p1` en las condiciones estudiadas.
- Los 11 necesitan condiciones distintas del filtro original: **9 solo con corregir prefijos y 2 con prefijos y finales de
  línea**; ninguno necesita cambios en el contenido.
- Son 9 tareas distintas de 7 repositorios (BM25 aporta 4, UniXcoder 1 y RRF 6). No se extraen conclusiones entre estrategias.

**Evidencia.** `analisis.md` (sección 1) y `analisis.json`; `diagnostics/downstream-patches/data/.../analisis_referencia.json`.

#### P11. ¿Por qué recuperar 11 parches no significa resolver 11 incidencias?
✅ **RESPALDADA** · *Respuesta oral: pregunta 2.6.*

**Para estudiar.** Son cuatro etapas distintas, cada una más exigente que la anterior:

| Etapa | Qué exige | Cifras |
|---|---|---|
| 1. Formato interpretable | Tiene forma de parche | 117 de los 141 |
| 2. Supera `git apply --check` | Rutas y contexto encajan en el repositorio | 0 de 141 con `-p1`; 11 en condiciones alternativas |
| 3. Aceptado por un evaluador | Depende de su procedimiento (Linux, `-p1`, alternativas de aplicación) | **No medido** |
| 4. Supera las pruebas funcionales | La incidencia queda resuelta | 2 de 150 (ambos entre los 9 controles originales) |

**No hemos demostrado que esos 11 resuelvan sus tareas**: nunca se evaluaron funcionalmente. Como indicio exploratorio, los
11 editan el mismo fichero que la solución de referencia y 6 solapan con alguna región de ella; pero ese indicador **no
predice** la resolución (uno de los parches `resolved`, `pytest-5809`, no solapa).

#### P12. ¿Qué descubrimos sobre los ficheros que recibió el modelo?
✅ **RESPALDADA** (como dato exploratorio) · *Respuesta oral: pregunta 7.4.*

**Para estudiar.** En los **96** parches con error de contexto o corrupción (en la mejor condición):
- **50** intentaban modificar únicamente ficheros que **sí** estaban en el contexto recuperado;
- **41** intentaban modificar ficheros que **no** estaban;
- **5** combinaban ficheros presentes y ausentes.

Por tanto, **46 de 96 intentaban modificar al menos un fichero no proporcionado al modelo**.

**Por qué es relevante para el TFM.** Estudiamos justamente **qué contexto del repositorio se le da a un modelo para ayudarle
a programar**. El prompt le decía «usa solo el contexto recuperado» y, aun así, el modelo editó ficheros que no vio. De hecho,
85 de los 96 editan el mismo fichero que la solución de referencia, y **38 de ellos sin que ese fichero estuviera en el
contexto**: el modelo parecía saber qué fichero tocar (por ejemplo, por la traza de la incidencia) pero la recuperación no se
lo había dado. Eso apunta a un problema de **recuperación** y no de formato, aunque la causa no está demostrada.

**Qué no se puede decir.** Que un fichero no esté en el contexto **no demuestra por sí solo** que esa sea la causa del fallo.
Es un análisis a nivel de **fichero**, no de línea. Otro dato exploratorio: solo 20 de los 96 anclan todos sus hunks por
contenido en el repositorio (24 anclan algunos y 51 ninguno; 1 no es verificable), de modo que incluso con los ficheros
delante muchos parches citan mal el código. La diferencia entre ver el fichero, citar contenido que existe, aplicar y
resolver se explica con un ejemplo en la pregunta 7.4. Todo esto es exploratorio y no predice nuevas generaciones.

**Evidencia.** `analisis_ficheros_contexto.json`, `analisis_referencia.json` y `analisis_anclaje_contenido.json`, todos en
`data/matriz_completa_20261112T000024Z/`.

### 8.5 Bloque 5. Limitaciones y preguntas difíciles del tribunal

#### P13. ¿Por qué no realizamos las comprobaciones directamente en Linux?
🟡 **PARCIAL** (es una limitación declarada)

**Para estudiar.** El diagnóstico quería **aislar factores concretos** (rutas y finales de línea) que podían influir en el
filtro original; por eso usé reconstrucciones controladas en las que variaba cada factor de forma sistemática. Un entorno real
(Linux/Docker) mezcla muchos factores a la vez y no permitiría atribuir un efecto a uno de ellos. A cambio, el diagnóstico **no
reproduce completamente** el entorno de los evaluadores oficiales: los archivos con finales LF son una **prueba de
sensibilidad**, no una réplica demostrada de Linux, y no se ejecutaron los evaluadores.

**Respuesta oral.** «El objetivo del diagnóstico era aislar factores concretos que podían influir en el filtro original,
especialmente las rutas y los finales de línea. Por eso utilicé reconstrucciones controladas y varié esos factores de forma
sistemática. No considero que estas pruebas reproduzcan completamente el entorno Linux o Docker de los evaluadores oficiales.
Esa diferencia está recogida como limitación metodológica».

#### P14. ¿Por qué `git apply --check` no equivale a una evaluación funcional?
✅ **RESPALDADA** · *Respuesta oral: pregunta 7.6.*

**Para estudiar.** `git apply --check` solo responde: «¿este parche **encaja** en estos ficheros, con estas opciones?». **No
ejecuta ninguna prueba ni comprueba que la solución sea correcta.** Un parche puede encajar y no resolver nada (7 de los 9
aplicables eran así).

**Tampoco equivale a la aceptación de un evaluador oficial.** Según el código que leí (no lo ejecuté): SWE-bench Verified
prueba cuatro intentos (`git apply --verbose`, `--3way`, `--reject` y `patch --fuzz=5`), PolyBench usa `--ignore-whitespace` y
`patch --fuzz=5`, y Pro hace un único `git apply -v` estricto. Por eso **no podemos afirmar que los 141 hubieran sido
rechazados** por ellos.

#### P15. ¿Podemos concluir que BM25, UniXcoder o RRF es mejor generando soluciones?
✅ **RESPALDADA** (que no se puede concluir)

**Para estudiar.** **No.** Con solo **9 parches evaluados funcionalmente** no hay base para hablar de superioridad en la
resolución. Además, las tres estrategias se probaron sobre **las mismas 50 tareas**, así que las observaciones **no son
independientes**. Y hay que separar dos tipos de conclusión:
- **Recuperación de contexto:** BM25 obtiene los F1 medios más altos en las seis configuraciones; **no se ha hecho** aún una
  prueba de significación (pendiente: Wilcoxon o bootstrap).
- **Resolución funcional:** los dos `resolved` son de BM25, pero entre los 9 evaluados BM25 aporta 3, UniXcoder 2 y RRF 4;
  con esos recuentos es una observación descriptiva, no una diferencia.
- **Aplicabilidad** (no es resolución): con el `-p` natural pasan 4 de 41 (BM25), 1 de 42 (UniXcoder) y 6 de 40 (RRF), de nuevo
  descriptivo.

**Respuesta oral.** «No puedo establecer una superioridad funcional con nueve parches evaluados, y además las tres
estrategias se probaron sobre las mismas tareas. Lo que sí puedo decir es cómo se comportan en recuperación de contexto, y aun
ahí estoy pendiente de una prueba de significación».

#### P16. ¿Qué haríamos para mejorar el experimento?
🟡 **PARCIAL** (las líneas) · ⏳ (su efecto) · *Respuesta oral: pregunta 5.5.*

**Para estudiar.** Hay dos líneas distintas:
- **A. Recuperar mecánicamente** parches ya generados normalizando rutas y finales de línea (afectaría a los 11). No requiere
  nuevas llamadas al modelo, pero repara salidas ya generadas: se declararía como "salidas normalizadas".
- **B. Probar un formato de edición alternativo** (el modelo propone bloques de búsqueda y reemplazo literales y el pipeline
  construye el parche) con el mismo contexto y modelo. Respondería si un formato más robusto aumenta los parches que llegan a
  evaluación; no corrige que el modelo cite mal código o no vea el fichero.

**Estado, sin confundir propuestas con resultados.** El diagnóstico **D-004 está cerrado**. Para B existe un **protocolo
preparado** (D-005: 12 tareas, 36 condiciones, criterios de éxito y abandono fijados antes), pero **el piloto no está
aprobado ni ejecutado**; el calendario propuesto (tampoco aprobado) no prevé nada experimental antes de la entrega del
7/12. Cualquier cifra sobre su posible efecto es una **hipótesis**.

### 8.6 Bloque 6. Resumen para estudiar

#### A. Resumen de un minuto
«Comparamos tres formas de dar contexto de un repositorio a un modelo —BM25, UniXcoder y RRF— en 50 tareas, con un parche por
tarea y estrategia: 150 parches. Pero solo 9 superaron el filtro de aplicabilidad y llegaron a la evaluación funcional; 141 se
clasificaron como `invalid_patch`, así que la parte funcional aporta poca información. Para entender por qué hice un
diagnóstico: un script de Python que, sin generar nada nuevo, repitió `git apply --check` 1.800 veces variando los finales de
línea del parche y de los archivos y la interpretación de las rutas, partiendo de una línea base que reprodujo exactamente los
150 resultados originales. Resultado: los prefijos de ruta explican parte de los rechazos y los finales de línea casi nada; 11
de los 141 pasan una comprobación alternativa, pero no sabemos si resolverían la tarea; y 130 no pasan en ninguna condición,
con problemas de contexto o de estructura de origen no determinado —en 46 de 96 el modelo editaba ficheros que no recibió—.
Mi conclusión es prudente: hay que distinguir recuperación, generación, aplicabilidad y resolución; el diagnóstico no demuestra
equivalencia con los evaluadores ni superioridad de una estrategia. Propongo un piloto de formato de edición, pero aún no está
aprobado».

#### B. Cinco ideas fundamentales
1. El filtro de aplicabilidad impidió evaluar funcionalmente **141 de los 150** parches.
2. Investigamos el problema con una **matriz automatizada y reproducible**.
3. Los **prefijos de rutas** explican parte de los rechazos; **CRLF no era la causa principal**.
4. **Once** parches pasan una comprobación alternativa, pero **no sabemos si resuelven** las tareas.
5. Hay que distinguir **recuperación, generación, aplicabilidad y resolución funcional**.

#### C. Glosario sencillo
- **Unified diff:** formato de texto que describe cambios entre dos versiones de un fichero: cabeceras `---`/`+++`, bloques
  `@@` y líneas que empiezan por espacio, `-` o `+`.
- **Patch (parche):** fichero que describe cómo transformar un código en otro; normalmente es un unified diff.
- **Hunk:** cada bloque de cambios de un diff, introducido por `@@ -a,b +c,d @@`, con sus líneas de contexto y cambiadas.
- **`base_commit`:** el estado exacto del repositorio sobre el que se debe aplicar la solución de una tarea.
- **`git apply --check`:** comprueba si un parche se podría aplicar, **sin modificar** ningún fichero.
- **`-p0`:** no quita ningún componente inicial de las rutas del parche.
- **`-p1`:** quita el primer componente de las rutas (normalmente `a/` o `b/`); es el valor por defecto de `git apply`.
- **CRLF:** final de línea de dos caracteres (retorno de carro y salto de línea), típico de Windows.
- **LF:** final de línea de un solo carácter (salto de línea), típico de Linux y macOS.
- **`core.autocrlf`:** opción de Git que convierte finales de línea al extraer o guardar ficheros; con `true` (Windows) los
  ficheros extraídos pasan a CRLF.
- **SHA-256:** función que resume un fichero en una huella de 64 caracteres; si cambia un byte, cambia la huella.
- **Aplicabilidad:** si un parche se puede aplicar a un código (aquí, si pasa `git apply --check`); no dice si es correcto.
- **Evaluación funcional:** ejecutar las pruebas oficiales de la tarea tras aplicar el parche para saber si la incidencia queda
  resuelta.
- *Extras útiles:* **gold context** (el contexto de referencia anotado por humanos en ContextBench; no se da al modelo) y
  **Pass@1** (una sola generación por condición, sin reintentos según la calidad).

#### D. Errores que debo evitar en la defensa
- Confundir las **1.800 comprobaciones** con 1.800 generaciones.
- Afirmar que los **11** parches recuperables resuelven sus incidencias.
- Atribuir automáticamente los **141 rechazos al modelo**.
- Afirmar que el diagnóstico reproduce exactamente **Linux/Docker**.
- Decir que **117 estructuras reconocibles equivalen a 117 parches válidos**.
- **Mezclar** los resultados del diagnóstico con los resultados originales.
- *(Añadidos tras la revisión de los datos)* Decir que **los 24 "sin diff" son todos rechazos explícitos del modelo** (hay
  también cabeceras vacías, mensajes de error y otros textos) y presentar «50 de 96» como si fuera un **techo** de lo que un
  formato nuevo podría arreglar (es solo la cuenta de parches con todos los ficheros visibles).

---

## 9. Piloto P1: preparación técnica de la comparación del formato de edición (2026-11-12)

> **El piloto P1 no se ha ejecutado**: no hay generaciones nuevas, ni llamadas a la API, ni evaluación con el evaluador oficial. Lo que
> sigue es la **preparación técnica**, verificada con datos sintéticos (364 pruebas superadas; no son resultados del piloto). Detalle y
> reproducción: `pilot_p1/README.md`; protocolo: `downstream-patch-diagnostics.md`, sección 15.

### 9.1 ¿Qué es el filtro G y cómo garantiza una comparación justa entre `O1n` y `E1`?
✅ **RESPALDADA** (diseño y pruebas) · ⏳ (resultados sobre salidas reales)

> G es la comprobación común de aplicabilidad: `git apply --check -p1` sobre una copia temporal de los ficheros que toca el parche, leídos
> del `base_commit`. Es **la misma función** para los dos brazos (no recibe el brazo), el parche se pasa **byte a byte sin correcciones
> adicionales**. El único retoque previo es el normalizador N, cuya **única operación de contenido** es añadir `a/` en las líneas `---` y
> `b/` en las `+++` cuando faltan en todas las cabeceras y la correspondencia es inequívoca. N **conserva** los finales de línea de cada
> línea (LF o CRLF) y las marcas de las cabeceras, **no los convierte**, y **no modifica ni repara los hunks** (contenido, contadores y
> números de línea); ante cualquier duda deja el parche sin cambios. Se conservan por separado el parche original, el normalizado y el
> convertido. Las pruebas comprueban que bytes iguales dan veredictos iguales y que un
> parche con CRLF o sin prefijos se rechaza con la misma severidad en ambos. **Limitación:** G mide lo que mide `git apply --check`, no
> si el parche resuelve la tarea ni equivale al evaluador oficial.

### 9.2 ¿Qué compara exactamente `E1` frente a `O1n` y qué no puede demostrar?
✅ **RESPALDADA** (la definición) · ⏳ (el resultado)

> Compara, con el mismo modelo, contexto y estrategias de recuperación, cuántas condiciones producen un parche que pasa G con el formato
> de edición (`E1`) frente al formato original con la normalización mecánica de rutas (`O1n`). La mejora se define de antemano como
> **victorias de `E1` − victorias de `O1n`** (con los empates registrados). El piloto busca **estimar si el formato alternativo mejora
> la aplicabilidad** frente al formato original normalizado, **bajo condiciones controladas** (mismo modelo, contexto y estrategias). No hay
> todavía ningún resultado, **no atribuye causalidad**, no demuestra que mejore la recuperación ni que se resuelvan más tareas, y con 12
> tareas es una prueba piloto, no un contraste de significación.

*Ver también 5.5 y 7.6 (qué diferencia hay entre aplicar y resolver).*

### 9.3 ¿Cómo se evaluaría funcionalmente en P1 y por qué no reutilizó el evaluador original?
🟡 **PARCIAL** (la interfaz) · ⏳ (la evaluación real)

> Solo se evalúan los parches que pasan G, mediante una interfaz con evaluadores intercambiables; hoy solo existe un evaluador **falso**.
> El evaluador original no se reutiliza porque tiene efectos secundarios: hace `git fetch` y `git checkout --force` sobre los repositorios de
> trabajo, usa la red y contenedores, escribe en `logs/` con un identificador de ejecución fijo y modifica globalmente `Path.write_text`.
> En P1 todo se hace en directorios temporales, los artefactos no se sobrescriben y los registros sintéticos no se pueden mezclar con
> los reales. El adaptador del evaluador oficial en un entorno aislado queda pendiente (fase 3B.2). La resolución funcional no tiene
> criterio de éxito en el protocolo: solo se describe.

### 9.4 ¿Qué es el hallazgo de `response.strip() + "\n"`?
✅ **RESPALDADA** (el mecanismo, por código y prueba) · ⏳ (cuántos parches afecta)

> El generador original guarda la respuesta con `strip()`, que elimina los espacios y saltos de línea de los extremos. Si lo que elimina
> es necesario para la estructura de un hunk (por ejemplo, una línea de contexto en blanco que el contador del hunk sí incluye), el hunk
> queda truncado y el parche, corrupto. **No implica que todos los diffs que terminan en una línea de contexto en blanco queden
> corruptos**: depende de si esa línea cuenta en el hunk. Se conserva ese comportamiento para el brazo original y el normalizador
> **no repara** el hunk, para no favorecerlo. **No he medido cuántos de los 150 parches originales se vieron afectados**; por eso no lo uso para explicar los 141
> rechazos (ver 1.1 y 7.4), solo como limitación a tener en cuenta al interpretar `O1n`.

### 9.5 ¿Las 364 pruebas son resultados del piloto?
✅ **RESPALDADA**

> No. Comprueban que las **herramientas** funcionan (aplicabilidad, aislamiento, reintentos, reanudación) con datos y evaluadores
> sintéticos. Los veredictos del simulacro de 72 condiciones se deducen de cómo se construyeron esas respuestas. Los resultados del piloto
> solo existirían tras generar con el modelo y evaluar, que no se ha hecho ni está autorizado.

---

## Frases de seguridad para la defensa

- *"Eso lo he comprobado y los datos están en el repositorio."* (solo para lo etiquetado ✅)
- *"Tengo una hipótesis, pero no la he verificado; lo dejo como trabajo pendiente."* (⏳)
- *"Con 2 casos resueltos no puedo establecer una relación causal; lo presento de forma descriptiva."*
- *"Esa diferencia es pequeña y todavía no he calculado su significación estadística."*
- *"Mi comprobación de aplicabilidad no replica exactamente el entorno del evaluador oficial; lo declaro como limitación."*

## Antes de la defensa: revisar y actualizar

- [ ] Si se repite la fase LLM o se cambia el formato de salida, reescribir las secciones 1, 2, 4.3 y 5.5.
- [ ] Si se ejecuta el piloto P1 (generación real y evaluación), sustituir la sección 9 por sus resultados reales y revisar 5.5.
- [ ] Si se hace la prueba de significación, reescribir 4.2 y la conclusión 6.2.1.
- [x] Efecto de CRLF y prefijos cuantificado con la matriz completa: 3.2, 3.4, 3.6, 3.8 y 4.4 actualizadas (2026-11-12). Pendiente: si se ejecutara el evaluador oficial o uno tolerante, reescribir 3.4, 3.6 y la sección 7.
- [ ] Actualizar la sección 7, la guía (sección 8) y la tabla de cifras si se corrige alguna cifra al incorporar el diagnóstico a la memoria.
- [x] Análisis `--anclaje-contenido` y `--referencia` y sus JSON versionados en el commit `67d391b`.
- [x] Clasificación manual de los 24 sin diff contrastada y corregida en `docs/downstream-patch-diagnostics.md` (sección 2, 2026-11-12). Pendiente solo: pasarla a un script si se quiere reproducible.
- [ ] Contrastar las cifras con la versión final de la memoria (los números cambiarán si se repite el experimento).
- [ ] Comprobar si el director espera que la memoria final recoja estos hallazgos.
- [ ] Actualizar la memoria (sección 6.5, "113 de los 141") a 117, con 24 sin diff, y mantener las preguntas 1.6 y 4.6 coherentes con lo que finalmente figure en ella.
