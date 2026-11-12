# Plan de trabajo — Entrega 3 del TFM

**Proyecto:** Evaluación de estrategias de recuperación de contexto para agentes de programación basados en LLM  
**Director:** Pablo Negre Rodríguez  
**Fecha de planificación:** 11/11/2026  
**Próxima entrega:** 07/12/2026  
**Entrega definitiva prevista:** Febrero de 2027

## 1. Objetivo

Aplicar las correcciones de la segunda entrega indicadas por el director, priorizando los cambios técnicos de mayor incertidumbre y mejorando la estructura, el rigor metodológico y la presentación de la memoria.

El trabajo se organizará teniendo en cuenta que no habrá disponibilidad durante la semana del 16 al 22 de noviembre.

### Prioridades

1. Investigar y, si es viable, mejorar la aplicabilidad de los parches generados por el LLM.
2. Incorporar análisis estadístico pareado de las estrategias.
3. Reestructurar la memoria de nueve a cinco capítulos y eliminar repeticiones.
4. Completar las explicaciones teóricas y las ecuaciones.
5. Revisar formato, figuras, tablas, resumen y referencias.

## 2. Calendario

| Fechas                   | Actividad principal                        | Tiempo estimado     |
| ------------------------ | ------------------------------------------ | ------------------- |
| 11–12 noviembre          | Diagnóstico de los parches del LLM         | 2–4 h               |
| 13–15 noviembre          | Implementación y prueba piloto de mejora   | 4–6 h               |
| 16–22 noviembre          | Sin disponibilidad                         | —                   |
| 23–25 noviembre          | Experimentos y análisis estadístico        | 3–6 h + ejecuciones |
| 26–29 noviembre          | Reestructuración de la memoria             | 4–6 h               |
| 30 noviembre–2 diciembre | Teoría y metodología                       | 2–4 h               |
| 3–4 diciembre            | Formato, figuras, tablas y resúmenes       | 2–3 h               |
| 5–6 diciembre            | Revisión integral y preparación de entrega | 2–3 h               |
| 7 diciembre              | Entrega 3                                  | —                   |

**Estimación total:** 19–32 horas de trabajo efectivo, sin incluir posibles tiempos largos de ejecución o depuración.

## 3. Fase 1 — Diagnóstico de la evaluación con LLM

**Fechas:** 11–12 de noviembre

### Situación actual

- 50 tareas de ContextBench.
- Tres estrategias: BM25, UniXcoder y RRF.
- 150 generaciones de parches.
- 141 parches no aplicables (94 %).
- 9 parches aplicables.
- 113 de los 141 parches rechazados tienen un formato de diff reconocible.

### Tareas

- [ ] Guardar una copia de seguridad del código y los resultados originales.
- [ ] Localizar los módulos responsables de generar, validar y aplicar los parches.
- [ ] Revisar los errores de `git apply --check`.
- [ ] Clasificar los fallos por causa: formato, rutas, contexto, coincidencia con el código original u otros.
- [ ] Inspeccionar ejemplos representativos de parches rechazados.
- [ ] Identificar las causas predominantes.
- [ ] Documentar los hallazgos antes de modificar la implementación.

**Entregable:** diagnóstico técnico de los fallos de aplicación.

## 4. Fase 2 — Prueba piloto de mejora del LLM

**Fechas:** 13–15 de noviembre

### Objetivo

Evaluar un formato de edición alternativo que permita aplicar los cambios generados por el LLM de forma más robusta.

### Tareas

- [ ] Seleccionar un formato alternativo: búsqueda y reemplazo o reescritura de funciones.
- [ ] Diseñar el mecanismo de conversión de la salida del modelo a modificaciones aplicables.
- [ ] Implementar una primera versión.
- [ ] Ejecutar una prueba piloto sobre una muestra pequeña de tareas.
- [ ] Comparar la aplicabilidad frente al protocolo original.
- [ ] Verificar que el procedimiento se puede aplicar de manera equivalente a BM25, UniXcoder y RRF.
- [ ] Documentar los resultados del piloto.
- [ ] Decidir si procede repetir el experimento completo.

### Criterio de decisión

**Fecha límite: 15 de noviembre.**

- Si el piloto muestra una mejora clara y el procedimiento es reproducible, preparar la repetición de la evaluación.
- Si no mejora o introduce demasiados problemas, conservar el experimento original y documentar el diagnóstico y las limitaciones.

En cualquier caso, mantener intactos los resultados originales para garantizar la trazabilidad.

## 5. Fase 3 — Experimentos y análisis estadístico

**Fechas:** 23–25 de noviembre

### Evaluación con LLM

- [ ] Repetir las ejecuciones si la prueba piloto resulta satisfactoria.
- [ ] Mantener condiciones equivalentes para las tres estrategias.
- [ ] Registrar parches generados, aplicabilidad, errores y resolución funcional.
- [ ] Comparar los resultados originales con los del protocolo alternativo.
- [ ] Actualizar los resultados y sus limitaciones si corresponde.

### Análisis estadístico

- [ ] Recuperar las métricas individuales de las 50 tareas.
- [ ] Comprobar que los resultados están emparejados por tarea.
- [ ] Calcular intervalos de confianza mediante bootstrap pareado para las diferencias entre estrategias.
- [ ] Comparar BM25 frente a UniXcoder, BM25 frente a RRF y UniXcoder frente a RRF.
- [ ] Analizar las diferencias para los valores de K y niveles de evaluación relevantes.
- [ ] Interpretar los resultados sin confundir diferencias numéricas con evidencia estadística concluyente.
- [ ] Preparar una tabla o figura para la memoria.

**Entregable:** resultados experimentales consolidados y análisis estadístico.

## 6. Fase 4 — Reestructuración de la memoria

**Fechas:** 26–29 de noviembre

### Estructura objetivo

1. Introducción.
2. Contexto y estado del arte.
3. Objetivos y metodología.
4. Resultados.
5. Conclusiones y trabajo futuro.

Las referencias, la declaración de uso responsable de IA y los anexos quedarán fuera de la numeración de capítulos.

### Tareas

- [ ] Crear una copia de trabajo de la versión 8.0.
- [ ] Fusionar el capítulo de planteamiento de la comparativa con objetivos y metodología.
- [ ] Eliminar descripciones duplicadas de preparación de datos, BM25, UniXcoder, RRF y evaluación.
- [ ] Integrar la discusión en el capítulo de resultados.
- [ ] Eliminar los apartados de resumen redundantes.
- [ ] Conservar la información técnica relevante de los capítulos originales.
- [ ] Situar los problemas de desarrollo en metodología o en un anexo.
- [ ] Reubicar la declaración de uso responsable de IA.
- [ ] Actualizar el párrafo de la introducción que describe la organización de la memoria.
- [ ] Revisar la continuidad y fluidez entre apartados.
- [ ] Mantener los anexos de reproducibilidad.

**Entregable:** memoria reorganizada en cinco capítulos.

## 7. Fase 5 — Ampliación teórica y ecuaciones

**Fechas:** 30 de noviembre–2 de diciembre

### BM25

- [ ] Explicar su fundamento léxico.
- [ ] Incorporar la fórmula de puntuación BM25.
- [ ] Explicar el peso IDF.
- [ ] Describir los parámetros `k₁` y `b`.
- [ ] Explicar la normalización por longitud del documento.

### UniXcoder

- [ ] Describir su arquitectura.
- [ ] Explicar los modos encoder-only, decoder-only y encoder-decoder.
- [ ] Describir el preentrenamiento y el aprendizaje contrastivo.
- [ ] Justificar su uso para representar código y lenguaje natural en un espacio compartido.

### Métricas y ecuaciones

- [ ] Añadir fórmulas de cobertura, precisión y F1 a nivel de fichero y línea, coherentes con las definiciones utilizadas en el experimento.
- [ ] Corregir el subíndice de la fórmula RRF a `rank_r(d)`.
- [ ] Numerar todas las ecuaciones consecutivamente.
- [ ] Incorporar referencias a las ecuaciones desde el texto.

**Entregable:** metodología teóricamente completa y con ecuaciones correctamente presentadas.

## 8. Fase 6 — Formato y presentación

**Fechas:** 3–4 de diciembre

### Portada y resúmenes

- [ ] Añadir «Febrero de 2027» en la portada.
- [ ] Completar el nombre del director: Pablo Negre Rodríguez.
- [ ] Añadir una frase de estado del arte y contribución al resumen.
- [ ] Aplicar la misma mejora al abstract.

### Estilos

- [ ] Capítulos: 18 pt.
- [ ] Apartados de primer nivel: 16 pt.
- [ ] Apartados de segundo nivel: 14 pt.
- [ ] Texto principal: 12 pt.
- [ ] Mantener el azul de la plantilla.
- [ ] Eliminar tabulaciones y sangrías innecesarias de los títulos.
- [ ] Acortar los títulos de los subapartados metodológicos.
- [ ] Revisar cursivas de términos ingleses.
- [ ] Aplicar monoespaciado a identificadores, comandos, rutas y estados del código.

### Figuras y tablas

- [ ] Colocar los títulos de las figuras debajo de cada figura.
- [ ] Mejorar la legibilidad de las Figuras 1 y 2.
- [ ] Unificar el estilo de los títulos de las Figuras 3–7.
- [ ] Unificar el estilo de los títulos de las Tablas 6 y 7.
- [ ] Explicar qué representa N en la Tabla 7.
- [ ] Indicar que las métricas de la Tabla 7 corresponden a K = 10.
- [ ] Reducir los resultados numéricos a tres decimales cuando sea apropiado.
- [ ] Comprobar que figuras y tablas se entienden sin depender del texto circundante.

## 9. Fase 7 — Revisión final

**Fechas:** 5–6 de diciembre

- [ ] Verificar que se han atendido todas las correcciones de Pablo.
- [ ] Comprobar que no quedan repeticiones importantes.
- [ ] Revisar la coherencia entre objetivos, metodología, resultados y conclusiones.
- [ ] Comprobar que los resultados numéricos coinciden con los archivos experimentales.
- [ ] Revisar citas y bibliografía.
- [ ] Comprobar títulos, numeración y referencias cruzadas.
- [ ] Actualizar el índice general, el índice de figuras y el índice de tablas.
- [ ] Revisar anexos y referencias a ellos.
- [ ] Comprobar saltos de página, paginación y espacios en blanco.
- [ ] Realizar una lectura final de la memoria.
- [ ] Preparar el documento para la entrega.

**Fecha objetivo de finalización:** 6 de diciembre.

## 10. Riesgos y medidas de contingencia

| Riesgo                                                  | Medida                                                            |
| ------------------------------------------------------- | ----------------------------------------------------------------- |
| No se identifica la causa de los parches rechazados     | Conservar resultados originales y documentar el diagnóstico       |
| El nuevo formato no mejora la aplicabilidad             | No repetir el experimento completo                                |
| La repetición del experimento requiere demasiado tiempo | Priorizar una evaluación reproducible y correctamente documentada |
| Las diferencias estadísticas son poco concluyentes      | Presentar intervalos y reconocer la incertidumbre                 |
| La reestructuración provoca pérdida de contenido        | Trabajar sobre una copia y revisar cada apartado fusionado        |
| Aparecen problemas de formato en Word                   | Reservar los últimos días para revisión visual e índices          |

## 11. Hitos de control

- **15/11:** diagnóstico y decisión sobre el piloto del LLM.
- **25/11:** experimentos y análisis estadístico cerrados, si son viables.
- **29/11:** estructura de cinco capítulos completada.
- **02/12:** teoría y metodología completadas.
- **04/12:** formato, figuras, tablas y resúmenes revisados.
- **06/12:** versión preparada para entrega.
- **07/12:** Entrega 3.

## 12. Criterios de finalización

El trabajo se considerará preparado para la tercera entrega cuando:

- La memoria tenga una estructura clara de cinco capítulos.
- Se hayan eliminado las duplicidades señaladas por el director.
- Las explicaciones de BM25, UniXcoder, RRF y las métricas estén completas.
- Las comparaciones entre estrategias incorporen análisis de incertidumbre.
- La evaluación con LLM esté mejorada o sus limitaciones estén justificadas con evidencia.
- Las figuras, tablas, ecuaciones y estilos sean consistentes.
- Los resultados sean trazables y reproducibles.
- Se hayan revisado todas las observaciones de la segunda entrega.

---

**Estado inicial:** pendiente de comenzar.

**Primera tarea:** analizar los fallos de aplicación de los parches generados por el LLM.

---

## Seguimiento del diagnóstico downstream — noviembre 2026

**Última actualización:** 12/11/2026. Los detalles técnicos están en
[`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md) (secciones 2.1, 11 y 12); aquí solo se
resume el estado para retomar el trabajo.

### Objetivo

Investigar los 141 parches `invalid_patch` para **distinguir errores de generación del modelo, de formato del
parche y del entorno de evaluación**, sin modificar los resultados originales. Es un medio para justificar
limitaciones o mejoras (Fase 2 de este plan), no un fin en sí mismo.

### Estado

- **Diagnóstico inicial documentado** y guardado en el commit local `4fa7f48` (clasificación por causa, prefijos,
  `-p0`, reconstrucciones temporales, LF/CRLF, validación 39/39, decisión D-001 sobre 117 frente a 113).
- **Script de matriz LF/CRLF × `-p` implementado, pendiente de ejecución real:**
  `diagnostics/downstream-patches/scripts/eol_prefix_matrix.py` (v1.0). Revisado solo de forma estática; solo se ha
  ejecutado el **modo plan** del piloto (7 parches, 84 comprobaciones previstas), que no ejecuta ninguna
  comprobación de aplicabilidad.
- La sección 12 del diagnóstico, el script y esta nota **no están commiteados** a fecha de esta actualización.

### Hallazgos confirmados

- Los 141 `invalid_patch` se reparten en 45 fichero inexistente, 41 parche corrupto, 24 sin diff, 24 contexto que no
  coincide y 7 fragmento sin cabecera.
- **117 de 141** tienen estructura de parche reconocible por Git (112 con cabeceras completas, 5 con cabecera
  defectuosa) y **24** no contienen diff. Esta cifra **sustituye al 113** de la sección 3 de este plan (se conserva
  el texto original como registro histórico).
- 94 parches no llevan prefijos `a/` `b/` (criterio sobre las líneas `---`); con `-p1`, Git elimina el primer
  componente de la ruta, lo que explica 44 de los 45 "fichero inexistente". Los 9 parches aplicables sí llevan
  prefijos.
- Con `-p0`, parche CRLF y árbol CRLF (reconstrucción validada 39/39), pasan `git apply --check` 9 de los 94.
- Los 150 `patch.diff` están guardados con finales de línea CRLF y el equipo tiene `core.autocrlf=true`.

### Limitaciones (lo que no se puede afirmar)

- **No hay equivalencia demostrada con el entorno oficial Linux/Docker.** La lectura del código de los evaluadores es
  una inspección, no una ejecución; un árbol LF es solo una prueba de sensibilidad.
- Que `git apply --check` funcione tras normalizar no implica que el evaluador acepte el parche ni que resuelva la
  incidencia.
- **Siguen siendo hipótesis, no resultados:** que el CRLF proceda de `write_text`; que explique parte de los fallos de
  contexto; que los 24 sin diff sean fallos de recuperación; que un formato de edición alternativo mejore la
  aplicabilidad.

### Próximos pasos

1. Revisar el plan del piloto (selección, reparto de comprobaciones y casos especiales).
2. Ejecutar el piloto (`--pilot --run`) **solo con autorización**.
3. Validar la línea base: debe reproducir el resultado original de `git apply --check`; si no, el script se detiene
   y se genera un informe de discrepancias.
4. Si procede, ejecutar la matriz completa una sola vez (1 200 celdas principales y 600 de robustez).
5. Documentar los resultados en el diagnóstico y en las preguntas de defensa, y decidir qué entra en la memoria.

### Decisiones pendientes

- Autorizar la ejecución del piloto y, después, la de la matriz completa.
- Cómo tratar el parche mixto `qutebrowser-3fd8e129…` (bm25), que el script clasifica como indeterminado.
- Si la Fase 2 de este plan (formato de edición alternativo del LLM) se ejecuta o se documenta como línea futura.
- Qué cifras (117 y 24) se trasladan a la sección 6.5 de la memoria.
- Cuándo commitear la documentación y el script.

### Criterio propuesto para cerrar la investigación (a confirmar)

Cerrar cuando se cumpla **una** de estas condiciones, sin añadir celdas, evaluadores ni réplicas:

1. La línea base se reproduce, la matriz completa se ejecuta una vez y los resultados quedan documentados con sus
   limitaciones.
2. La línea base no se reproduce: se documenta el informe de discrepancias como limitación, con a lo sumo un ajuste
   justificado y un único reintento.
3. Se llega al **15/11** sin resultados: se documenta el estado y las limitaciones y se continúa con el resto del plan.

### Fechas y prioridad

- **Próxima entrega:** 07/12/2026. **Predepósito:** 03/02/2027.
- **Prioridad:** proteger el tiempo de revisión del Word (reestructuración, teoría y formato entre el 26/11 y el
  06/12) y **no ampliar innecesariamente el experimento**. Plazo máximo para el diagnóstico: 15/11, antes de la
  semana sin disponibilidad (16–22/11).

### Actualización del 12/11/2026

Esta actualización **no sustituye** el texto anterior del apartado; solo lo pone al día. Detalles y tablas en
[`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md), sección 13.

- **Piloto ejecutado** (7 parches, 84 comprobaciones): línea base reproducida en 7/7, sin discrepancias ni casos no
  evaluables, integridad intacta. Son resultados diagnósticos del piloto y no se extrapolan a los 150.
- **Línea base completa validada:** 150 de 150 reproducen el resultado original de `git apply --check`, sin
  discrepancias; integridad intacta (parches, resultados, 20 repositorios e índices). La matriz completa y la réplica
  de robustez **no** se han ejecutado.
- **Hallazgo por inspección de código** (no ejecutado en los evaluadores): los evaluadores reciben el parche leído con
  `read_text`, es decir, con finales de línea LF, mientras que el filtro previo usaba el fichero CRLF. Por eso
  `invalid_patch` equivale a "no aplicable según el filtro del TFM", no a "rechazado por el evaluador".
- **Incidencia menor** en el registro del `manifest.json` (muestra la configuración del repositorio principal): no
  afecta a los resultados; corrección mínima propuesta y pendiente de autorización.
- **Pendiente:** autorización para la matriz completa (1 200 celdas principales y 600 de robustez), una única vez.
- **Fechas:** próxima entrega **07/12/2026**; predepósito **03/02/2027**. El plazo propuesto para cerrar el
  diagnóstico sigue siendo el 15/11. La prioridad se mantiene: proteger el tiempo de revisión del Word y no ampliar
  innecesariamente el experimento.

- **Estado de la tarea "corrección del manifest" (12/11/2026):** realizada en la versión 1.1 del script; pendiente de
  validación en la próxima ejecución real. No afecta a los resultados ya documentados. La matriz completa sigue
  pendiente de autorización.

### Actualización del 12/11/2026 (matriz completa)

Detalles y tablas en [`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md), sección 14. Lo anterior se
conserva como registro histórico.

- **Estado:** matriz completa ejecutada **una vez** (1 200 celdas principales y 600 de robustez) tras validar la línea base
  de 150 (150/150). Sin celdas no evaluables, integridad intacta. Es aplicabilidad (`git apply --check`), no resolución.
- **Resultado principal:** con el `-p` natural de cada parche aplican 11 de 123 (8,9 %) en la mejor celda (LL) y 9 en el
  filtro original reconstruido (CC); con `-p1`, como los evaluadores, **0 de 141** en cualquier combinación CRLF/LF. Los
  fallos restantes son sobre todo de contenido del diff (78 %: contexto o `corrupt`).
- **Cierre propuesto, pendiente de aprobación:** el criterio 1 de cierre se cumple; no ejecutar más celdas ni evaluadores.
  Llevar a la memoria una subsección breve de diagnóstico y las limitaciones.
- **Siguientes pasos:** (1) decidir el cierre; (2) actualizar las preguntas de defensa; (3) incorporar el diagnóstico a la
  memoria sin ampliar el experimento; (4) decidir si se aborda la Fase 2 (formato de edición alternativo) o se deja como
  trabajo futuro; (5) commitear documentación y scripts.
- **Fechas y prioridad:** próxima entrega **07/12/2026**; predepósito **03/02/2027**. Proteger el tiempo de revisión del Word.

### Cierre del diagnóstico experimental (12/11/2026)

Tras una revisión de consistencia de solo lectura (detalle en [`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md),
sección 14.14), **el diagnóstico experimental queda cerrado** (D-004). Cumple el criterio 1 de cierre de este apartado: línea
base reproducida (150/150), matriz ejecutada una vez y documentada.

- **Comprobado:** los 11 parches que aplican en LL son exactamente los que aplican en alguna celda y 130 de 141 no aplican en
  ninguna; denominadores y porcentajes coherentes (141 = 30 + 93 + 17 + 1; 123 = 30 + 93); las sumas por estrategia cuadran.
- **Precisiones introducidas:** los 96 fallos de contexto o `corrupt` ya no se describen como "de contenido del diff": su origen
  no está determinado (modelo, prompt, formato, recuperación; en 46 de los 96 el parche edita ficheros que el modelo no vio,
  dato exploratorio); no se interpretan diferencias entre estrategias como significativas; se distingue siempre entre pasar
  `git apply --check`, aceptación del evaluador y resolución funcional. Lo escrito arriba ("contenido del diff") queda
  sustituido por esta precisión.
- **Siguiente:** incorporar el diagnóstico a la memoria según la lista de cambios de 14.14 (el Word no se ha modificado),
  sin ampliar el experimento; decidir si la Fase 2 de este plan (formato de edición alternativo) se hace o queda como trabajo
  futuro; actualizar `defensa-tfm-preguntas.md` (hecho, sección 7) y commitear.
- **Fechas:** próxima entrega **07/12/2026**; predepósito **03/02/2027**. Prioridad: proteger el tiempo de revisión del Word.

### Piloto de formato de edición: pendiente de decisión (12/11/2026)

**Estado: análisis de viabilidad y protocolo P1 documentados** en [`downstream-patch-diagnostics.md`](downstream-patch-diagnostics.md),
sección 15. **El experimento NO está aprobado ni ejecutado**; esta nota no lo autoriza.

- **Avance técnico (12/11/2026; no es ejecución del piloto):** la implementación técnica del conversor SEARCH/REPLACE → diff
  (parser y aplicador, en `pilot_p1/`) está **realizada y validada localmente** (139 pruebas correctas, contraste con parches
  ya conocidos e integridad del experimento original verificada; detalle en `pilot_p1/README.md` y `experiment-log.md`).
  **Siguen pendientes** la preparación de los prompts, el normalizador, la selección y congelación de las 12 tareas y la
  orquestación. **No se han ejecutado** las 72 generaciones ni la evaluación funcional, y no se ha verificado el conversor en
  Linux/Docker. Continuar con el piloto completo sigue **pendiente de autorización y de viabilidad temporal** (nada
  experimental antes de la entrega del 07/12/2026).

- **Qué se propone (resumen):** un piloto pequeño del formato de edición alternativo que pidió el director: 12 tareas × 3
  estrategias = 36 condiciones, con cuatro brazos (originales `O0`, nueva generación con el prompt original `O1`, `O1`
  normalizado `O1n` y formato de edición `E1`), comparación primaria `E1` frente a `O1n`, una generación por condición y sin
  reintentos, y criterios de éxito y de abandono fijados antes de ejecutar. Como análisis secundario opcional, la recuperación
  mecánica de los 11 parches (`S1`), siempre separada de P1.
- **Hallazgo que condiciona la propuesta:** el formato no corrige que el modelo cite código que no existe ni que edite ficheros
  que no vio; de los 96 fallos de contexto o corrupt, solo 20 anclan todos sus hunks por contenido en el repositorio. La cifra
  "50 de 96" de visibilidad de ficheros no es un techo de convertibilidad (sección 15.2).
- **Fechas propuestas (no aprobadas):** nada experimental antes de la entrega del **07/12/2026**; implementar y congelar el
  protocolo el 8–12/12; ejecutar el 14–18/12; decisión hacia el 20/12; solo si hay éxito, una ampliación a las 50 tareas el
  5–16/1 con protocolo propio; integrar en la memoria el 26/1–2/2; **predepósito el 03/02/2027**. La Fase 2 original de este plan
  (13–15/11, con decisión el 15/11) no se ejecutaría en esas fechas si se aprueba esta propuesta; hasta entonces sigue pendiente.
- **Prioridad:** proteger el tiempo de revisión del Word y no ampliar el experimento sin aprobación.
- **Decisiones pendientes:** aprobar o modificar P1 (formato, selección, brazos y umbrales); incluir o no S1; aprobar el
  calendario; comentarlo o no con el director antes del 7/12; etiquetar en Git los resultados originales.
