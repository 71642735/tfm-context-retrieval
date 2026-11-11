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
