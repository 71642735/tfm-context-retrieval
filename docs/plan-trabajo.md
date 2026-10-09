# Plan de trabajo del TFM

Plan de trabajo definido para el desarrollo experimental y la preparación de la
segunda entrega del TFM, prevista para el **9 de noviembre de 2026**.

El objetivo es utilizar este calendario como referencia de planificación. Si se
adelantan tareas, el tiempo ganado se utilizará principalmente como margen ante
posibles bloqueos o días con menor disponibilidad, evitando ampliar
innecesariamente el alcance del TFM.

---

## Plan diario

| Fecha          | Trabajo previsto                                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------------------------- | --- |
| **5 oct.**     | Cerrar implementación y evaluación inicial de BM25.                                                              | [x] |
| **6 oct.**     | Estudiar embeddings, preparar dependencias y realizar una primera prueba del modelo semántico.                   | [x] |
| **7 oct.**     | Implementar la recuperación semántica.                                                                           | [x] |
| **8 oct.**     | Evaluar la recuperación semántica y compararla con BM25.                                                         | [x] |
| **9 oct.**     | Implementar la estrategia híbrida mediante Reciprocal Rank Fusion (RRF).                                         | [x] |
| **10 oct.**    | Evaluar las tres estrategias y realizar tests y limpieza del código.                                             | [x] |
| **11 oct.**    | Revisión ligera del proyecto, Git, actualización del registro experimental y preparación para defensa/reuniones. | [x] |
| **12 oct.**    | Generalizar el pipeline para múltiples tareas y repositorios.                                                    | [x] |
| **13 oct.**    | Implementar la selección reproducible de tareas.                                                                 | [x] |
| **14 oct.**    | Preparar y comenzar el mini-piloto de aproximadamente 5 tareas.                                                  | [x] |
| **15 oct.**    | Ejecutar BM25, recuperación semántica e híbrida sobre las tareas del mini-piloto.                                | [x] |
| **16 oct.**    | Corregir únicamente problemas generales detectados en el pipeline.                                               | [x] |
| **17 oct.**    | Reejecutar el mini-piloto y generar una primera tabla comparativa.                                               | [x] |
| **18 oct.**    | Analizar y documentar el mini-piloto y congelar la configuración experimental.                                   | [x] |
| **19 oct.**    | Seleccionar de forma reproducible la muestra final de 30–50 tareas.                                              |
| **20 oct.**    | Preparar repositorios y `base_commit` de la muestra final.                                                       |
| **21 oct.**    | Ejecutar BM25 sobre la muestra final.                                                                            |
| **22 oct.**    | Ejecutar recuperación semántica sobre la muestra final.                                                          |
| **23 oct.**    | Ejecutar recuperación híbrida sobre la muestra final.                                                            |
| **24 oct.**    | Agregar resultados para K=5, K=10 y K=20.                                                                        |
| **25 oct.**    | Analizar resultados y casos relevantes. Cierre de la fase de recuperación.                                       |
| **26 oct.**    | Diseñar el pipeline de evaluación downstream con LLM.                                                            |
| **27 oct.**    | Ejecutar una primera tarea completa con LLM de extremo a extremo.                                                |
| **28 oct.**    | Automatizar la evaluación mediante LLM.                                                                          |
| **29–30 oct.** | Ejecutar la evaluación LLM y solucionar posibles problemas operativos.                                           |
| **31 oct.**    | Analizar Pass/Fail y la relación entre calidad de recuperación y resolución de incidencias.                      |
| **1 nov.**     | Preparar tablas y gráficas finales de resultados.                                                                |
| **2 nov.**     | Buffer experimental y congelación definitiva del experimento.                                                    |
| **3 nov.**     | Redactar metodología.                                                                                            |
| **4 nov.**     | Redactar resultados.                                                                                             |
| **5 nov.**     | Redactar discusión, limitaciones y amenazas a la validez.                                                        |
| **6 nov.**     | Completar las secciones requeridas para la entrega.                                                              |
| **7 nov.**     | Revisión académica general del documento.                                                                        |
| **8 nov.**     | Buffer final y correcciones.                                                                                     |
| **9 nov.**     | Entrega.                                                                                                         |

---

## Hitos principales

### Hito 1 — Piloto inicial

Validar sobre una tarea de ContextBench el pipeline completo de recuperación:

- chunking;
- BM25;
- recuperación semántica mediante UniXcoder;
- recuperación híbrida mediante RRF;
- evaluación para K=5, K=10 y K=20.

### Hito 2 — Mini-piloto multi-repositorio

Ejecutar el pipeline sobre aproximadamente cinco tareas pertenecientes a
repositorios diferentes.

El objetivo de este mini-piloto no es obtener conclusiones definitivas sobre
qué estrategia es mejor, sino comprobar que la infraestructura experimental
funciona correctamente sobre diferentes tareas y repositorios.

### Hito 3 — Experimento final de recuperación

Ejecutar las tres estrategias sobre una muestra reproducible de aproximadamente
30–50 tareas de ContextBench.

Comparar los resultados principalmente a nivel de fichero y líneas para
K=5, K=10 y K=20.

### Hito 4 — Evaluación downstream con LLM

Proporcionar al mismo LLM el issue y el contexto recuperado por cada estrategia,
manteniendo constantes las demás condiciones experimentales.

Evaluar la resolución de las incidencias mediante la aplicación del parche y
la ejecución de los tests correspondientes.

### Hito 5 — Análisis y redacción

Analizar por separado:

1. calidad de la recuperación de contexto;
2. capacidad del LLM para resolver las incidencias;
3. relación entre ambas.

Posteriormente redactar metodología, resultados, discusión, limitaciones y
resto de apartados necesarios para la entrega.

---

## Reglas de planificación

### Adelanto

El trabajo realizado antes de la fecha inicialmente prevista se utilizará como
margen de seguridad.

**Día con tiempo → adelantar hitos ya planificados.**

**Día sin tiempo → consumir el colchón acumulado.**

**Nunca → utilizar el adelanto para ampliar innecesariamente el alcance.**

### Bloqueos técnicos

Cuando aparezca un problema técnico, se aplicará primero la siguiente pregunta:

> ¿Es imprescindible resolver este problema para responder a la pregunta de
> investigación del TFM?

Si la respuesta es sí, se resolverá.

Si la respuesta es no, se utilizará la alternativa más sencilla posible y,
cuando sea relevante, se documentará como limitación o decisión técnica.

### Congelación experimental

El objetivo es tener el experimento completamente cerrado alrededor del
**2 de noviembre de 2026**.

A partir de ese momento no se modificarán decisiones metodológicas simplemente
porque los resultados obtenidos no sean los esperados.

Solo se realizarán cambios si se detecta un error real en el procedimiento
experimental.

---

## Estado respecto al plan

Esta sección puede actualizarse periódicamente para conocer el adelanto o
retraso respecto al calendario original.

### 7 de octubre de 2026

En esta fecha ya se habían completado o adelantado los siguientes trabajos:

- BM25 implementado y evaluado.
- Recuperación semántica mediante UniXcoder implementada y evaluada.
- Recuperación híbrida mediante RRF implementada y evaluada.
- Comparación inicial de las tres estrategias sobre la tarea piloto.
- Inicio de la generalización del pipeline a múltiples repositorios.
- Preparación automática de repositorios en el `base_commit` de ContextBench.
- Parametrización de BM25 mediante `task_id`.
- Validación de regresión sobre la tarea piloto de Astropy.
- Análisis de la distribución de tareas Python de ContextBench.
- Selección reproducible de las cinco tareas del mini-piloto.
- Inicio de la validación del pipeline sobre un segundo repositorio.

Por tanto, el desarrollo se encuentra trabajando sobre actividades originalmente
previstas aproximadamente para los días **13–14 de octubre**.

El adelanto consolidado se estima actualmente en aproximadamente **4–5 días**,
aunque esta estimación deberá actualizarse cuando se complete el mini-piloto
multi-repositorio.

### Estado del mini-piloto

| Tarea                                | BM25 | Semántico | Híbrido |
| ------------------------------------ | ---- | --------- | ------- |
| `astropy__astropy-12907`             | ✅   | ✅        | ✅      |
| `django__django-12663`               | ✅   | ✅        | ✅      |
| `Significant-Gravitas__AutoGPT-4652` | ⬜   | ⬜        | ⬜      |
| `matplotlib__matplotlib-25479`       | ⬜   | ⬜        | ⬜      |
| `langchain-ai__langchain-6765`       | ⬜   | ⬜        | ⬜      |
| `scikit-learn__scikit-learn-25931`   | ⬜   | ⬜        | ⬜      |
