# Incidencias técnicas

Registro de problemas técnicos encontrados durante el desarrollo experimental,
su causa, impacto y la solución o decisión adoptada.

El objetivo de este documento es conservar información potencialmente útil
para la redacción posterior de la memoria del TFM y para garantizar la
trazabilidad de las decisiones técnicas tomadas durante el desarrollo.

No todas las incidencias registradas tendrán que incluirse finalmente en la
memoria.

---

## TI-001 — ContextBench no disponible como módulo de Python

**Fecha:** 7 de octubre de 2026

**Fase:** Generalización del pipeline a múltiples tareas y repositorios.

### Problema

Al ejecutar el pipeline BM25 generalizado mediante:

`python -m src.retrieval.bm25`

se produjo el siguiente error:

`ModuleNotFoundError: No module named 'contextbench'`

### Causa

El módulo de evaluación utiliza funciones del código oficial de ContextBench:

- `contextbench.core.fileio.line_to_byte`
- `contextbench.extractors.extract_def_set_in_spans`

El código oficial de ContextBench se encuentra clonado en
`external/ContextBench`, pero dicha ubicación no estaba disponible en la ruta
de búsqueda de módulos de Python durante esta ejecución.

### Impacto

El problema impide ejecutar las métricas de evaluación que dependen de estas
funciones de ContextBench.

No afecta directamente a la implementación de BM25 ni al proceso de
recuperación de contexto.

### Solución adoptada

Se añadió `external/ContextBench` a la ruta de búsqueda de módulos de Python
mediante la variable de entorno `PYTHONPATH`.

Tras aplicar esta configuración, el módulo oficial `contextbench` pudo
importarse correctamente y el pipeline BM25 generalizado se ejecutó de forma
completa.

La ejecución reprodujo los resultados obtenidos previamente en la tarea
piloto, confirmando que el problema estaba limitado a la resolución de módulos
de Python.

---

## TI-002 — Incompatibilidad del modelo semántico inicialmente seleccionado

**Fecha:** octubre de 2026

**Fase:** Implementación de la recuperación semántica.

### Problema

Inicialmente se valoró utilizar el modelo
`Salesforce/SFR-Embedding-Code-400M_R` para implementar la estrategia de
recuperación semántica.

Durante su integración aparecieron problemas de compatibilidad con el entorno
experimental utilizado.

Se intentó utilizar una versión anterior de `transformers`, pero una de sus
dependencias, `tokenizers`, no disponía de una distribución compatible con
Python 3.14 para el entorno utilizado.

Como consecuencia, el proceso intentó realizar una compilación nativa que
requería herramientas adicionales de compilación en Windows.

### Impacto

Continuar con este modelo habría requerido modificar el entorno experimental
o instalar herramientas adicionales únicamente para satisfacer sus
dependencias.

Esto habría incrementado la complejidad técnica sin aportar directamente
información relevante para la pregunta de investigación del TFM.

### Decisión adoptada

Se decidió no modificar de forma significativa el entorno de desarrollo ni
instalar herramientas adicionales únicamente para hacer funcionar este
modelo.

Dado que el objetivo del TFM es comparar estrategias de recuperación y no
comparar diferentes modelos de embeddings, se seleccionó
`microsoft/unixcoder-base` (UniXcoder) como modelo para implementar la
recuperación semántica.

### Justificación

Esta decisión permite mantener el foco del experimento en la comparación entre
recuperación léxica, semántica e híbrida, evitando introducir complejidad
técnica que no responde directamente a la pregunta de investigación.

---

## TI-003 — Avisos de Hugging Face durante el acceso a modelos y datasets

**Fecha:** octubre de 2026

**Fase:** Preparación y ejecución del entorno experimental.

### Problema

Durante el acceso a recursos de Hugging Face aparecieron avisos relacionados
con la realización de solicitudes sin autenticación y con determinadas
características del entorno Windows, como el uso de enlaces simbólicos.

### Impacto

Los avisos no impidieron la descarga ni la utilización de los modelos y
datasets necesarios para el experimento.

No se observó un impacto sobre los resultados obtenidos.

### Decisión adoptada

No se realizaron cambios adicionales en el entorno al comprobarse que estos
avisos no impedían el funcionamiento del pipeline experimental.

### Relevancia para la memoria

Incidencia menor. Se conserva como registro técnico, pero previsiblemente no
será necesario incluirla en la memoria final.

## TI-004 — Acoplamiento inicial del pipeline al repositorio piloto

**Fecha:** 7 de octubre de 2026

**Fase:** Generalización del pipeline a múltiples tareas y repositorios.

### Problema

La primera versión del pipeline experimental fue desarrollada y validada
utilizando una única incidencia de Astropy.

Como consecuencia, algunos parámetros estaban definidos directamente en los
scripts, entre ellos el repositorio, su ruta local y la tarea de ContextBench.

Esta configuración era suficiente para validar el primer piloto, pero no
permitía ejecutar de forma automática tareas pertenecientes a distintos
repositorios.

### Impacto

El pipeline requería modificaciones manuales para cambiar de repositorio o
tarea, lo que dificultaba su utilización sobre el conjunto de tareas previsto
para el experimento.

Además, realizar manualmente la preparación de cada repositorio incrementaría
el riesgo de errores al trabajar con diferentes `base_commit`.

### Solución adoptada

Se inició la generalización del pipeline separando las responsabilidades de
carga de tareas y preparación de repositorios.

Se creó un módulo para obtener dinámicamente la información de las tareas de
ContextBench y otro para preparar el repositorio correspondiente en el
`base_commit` especificado.

La solución permite reutilizar repositorios ya clonados y cambiar
automáticamente al estado del repositorio requerido por cada tarea.

### Justificación

La generalización permite ejecutar posteriormente el mismo procedimiento sobre
múltiples tareas y repositorios sin modificar manualmente la configuración para
cada incidencia, mejorando la reproducibilidad del experimento.
