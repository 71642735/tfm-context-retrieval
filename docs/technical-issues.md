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

## TI-005 — Fallo de checkout de AutoGPT por rutas largas en Windows

**Problema:**  
El clonado de `Significant-Gravitas/AutoGPT` finalizó la descarga de los
objetos, pero Git no pudo completar el checkout.

**Error principal:**

`fatal: cannot create directory ... Filename too long`

**Causa:**  
El repositorio contiene rutas cuya longitud supera la configuración
admitida por defecto por Git en Windows.

**Impacto:**  
El pipeline no podía preparar el repositorio de AutoGPT y, por tanto,
no podía ejecutar las estrategias de recuperación sobre esta tarea.

**Solución adoptada:**  
Se habilitó el soporte de rutas largas de Git para el repositorio de
trabajo mediante:

`git config core.longpaths true`

Posteriormente se eliminó el clon incompleto y se repitió la preparación
del repositorio.

**Estado:**  
Pendiente de validar mediante una nueva ejecución sobre AutoGPT.

**Solución adoptada:**  
Inicialmente se habilitó `core.longpaths=true` únicamente en la
configuración local del repositorio del TFM. Esta configuración no se
aplicaba al checkout realizado durante el clonado de un nuevo repositorio.

Se habilitó posteriormente el soporte de rutas largas a nivel global:

`git config --global core.longpaths true`

Tras eliminar el clon incompleto y repetir la ejecución, AutoGPT se clonó
correctamente y se realizó checkout del `base_commit` requerido por
ContextBench.

**Estado:**  
Resuelto y validado mediante la ejecución de BM25 sobre
`Significant-Gravitas__AutoGPT-4652`.

### Descarga de imágenes SWE-bench mediante Podman

Durante la primera ejecución del harness de SWE-bench con Podman, la imagen de evaluación no se encontraba disponible localmente. SWE-bench intentó descargarla mediante el Docker SDK utilizando la API compatible con Docker expuesta por Podman, pero la conexión se cerró durante la operación `images.pull`, produciendo `RemoteDisconnected`.

Se comprobó de forma aislada que la misma imagen podía descargarse correctamente mediante el CLI de Podman:

`podman pull docker.io/swebench/sweb.eval.x86_64.pytest-dev_1776_pytest-5809:latest`

La descarga finalizó correctamente. Por tanto, el problema no estaba en la disponibilidad de la imagen ni en el acceso al registro, sino en la operación de descarga realizada a través de la capa de compatibilidad Docker SDK → Podman.

Como solución se precargan directamente con Podman las imágenes de evaluación necesarias antes de ejecutar el harness de SWE-bench.

### Incompatibilidades entre SWE-bench 5.0.2 y Podman en Windows

Tras precargar correctamente la imagen mediante `podman pull`, la evaluación superó la fase de descarga de la imagen. Durante las primeras ejecuciones se identificaron varias incompatibilidades entre SWE-bench 5.0.2, Windows y Podman.

En primer lugar, la función `cleanup_container()` de SWE-bench utiliza llamadas directas al ejecutable `docker` para detener y eliminar contenedores. Este comportamiento no es compatible con el entorno utilizado, donde Docker no está disponible y se utiliza Podman como motor de contenedores.

La limpieza se adaptó para realizar estas operaciones mediante el Docker SDK, aprovechando la API compatible con Docker expuesta por Podman.

Posteriormente se detectó que el script `eval.sh` generado por SWE-bench podía escribirse con finales de línea incompatibles con el entorno Linux del contenedor. Esto provocaba errores durante la ejecución del script. Se aseguró la escritura del script con finales de línea LF.

También se produjo un problema de codificación al escribir en Windows la salida de los tests, debido a que la codificación predeterminada del entorno era `cp1252` y la salida contenía caracteres Unicode. La ejecución se realizó posteriormente en modo UTF-8.

Finalmente, en una ejecución los tests finalizaron correctamente pero la conexión con la API compatible con Docker de Podman se cerró antes de que SWE-bench pudiera completar el grading. Para conservar la separación entre ejecución y evaluación, se utilizó la funcionalidad `rewrite_reports=True` del propio harness para regenerar el informe a partir del `test_output.txt` producido por la ejecución.

La capa reutilizable de evaluación downstream automatiza esta recuperación. Si la ejecución normal de `run_instance()` no devuelve un informe, se comprueba si existe un `test_output.txt` completo mediante el marcador `>>>>> Test Exit Code:` generado por SWE-bench. Cuando la salida es completa, se ejecuta únicamente el grader oficial mediante `rewrite_reports=True`, evitando repetir los tests. Si la salida no existe o está incompleta, el caso se mantiene como `infrastructure_error` y no se contabiliza como un fallo de resolución del modelo.

Con estas adaptaciones, el harness produjo finalmente para la instancia piloto `pytest-dev__pytest-5809`:

- `patch_successfully_applied=True`
- `resolved=True`
- `infra_failure=False`

El test `FAIL_TO_PASS` pasó correctamente y los tres tests `PASS_TO_PASS` continuaron pasando.

Estas incidencias se consideran problemas de compatibilidad de infraestructura entre SWE-bench 5.0.2, Windows y Podman, y no fallos del patch generado ni de la lógica experimental.

Como medida preventiva para la ejecución automatizada, el evaluador comprueba ahora si la imagen indicada por `TestSpec.image` está disponible localmente mediante `podman image exists`. Si no está disponible, se descarga explícitamente mediante `podman pull` antes de iniciar SWE-bench. De este modo se evita depender de la descarga de imágenes a través de Docker SDK, que había mostrado problemas de compatibilidad con Podman en Windows.

**Estado:** resuelto y automatizado en la capa reutilizable de evaluación downstream.

### Múltiples fuentes de benchmark en ContextBench

Durante la validación de la evaluación downstream se detectó que no todas las tareas de la muestra final de ContextBench podían cargarse mediante el dataset de SWE-bench utilizado inicialmente por el evaluador.

La inspección de los metadatos de ContextBench mostró que las tareas proceden de distintas fuentes. Por ejemplo:

- `pytest-dev__pytest-5809` → `source: Verified`
- `langchain-ai__langchain-5609` → `source: Poly`
- `Significant-Gravitas__AutoGPT-4652` → `source: Poly`
- una instancia de `ansible/ansible` → `source: Pro`

Esto demuestra que el supuesto inicial de que todas las tareas de ContextBench podían evaluarse utilizando una única fuente de SWE-bench era incorrecto.

El problema afecta únicamente a la fase de evaluación downstream; la evaluación de recuperación ya realizada no depende de este mecanismo.

Como comprobación adicional, se contrastaron las 50 tareas de la muestra final con el cargador de SWE-bench utilizado inicialmente. Solo 29 de las 50 tareas pudieron localizarse, mientras que 21 no fueron encontradas.

Posteriormente se comprobó que la distribución de fuentes de la muestra era:

- `Verified`: 29 tareas
- `Poly`: 12 tareas
- `Pro`: 9 tareas

La coincidencia entre las 29 tareas localizables y las 29 tareas de tipo `Verified` permitió identificar que el evaluador inicial solo estaba cubriendo correctamente esa fuente.

**Evidencias:**

- `docs/screenshots/42-swebench-coverage-final-sample.png`
- `docs/screenshots/43-contextbench-multiple-sources.png`

**Estado:** pendiente de adaptar el evaluador para soportar correctamente las distintas fuentes sin modificar la muestra final congelada.

#### SWE-PolyBench: instancia no localizada por `instance_id`

Durante la primera evaluación efectiva mediante el adaptador oficial de SWE-PolyBench, la condición semántica de `keras-team__keras-19201` produjo un patch aplicable y alcanzó correctamente la rama de evaluación Poly.

El adaptador intentó localizar inicialmente la instancia mediante el identificador sintético de ContextBench:

`SWE-PolyBench__python__maintenance__bugfix__3f3ff585`

Sin embargo, el dataset oficial `AmazonScience/SWE-PolyBench` utiliza como `instance_id` el identificador original:

`keras-team__keras-19201`

Se corrigió el adaptador para utilizar `original_inst_id` de ContextBench al invocar SWE-PolyBench.

Durante el primer intento posterior, la imagen preconstruida de la instancia se descargó y etiquetó correctamente mediante Podman, pero se produjo una desconexión temporal de la API compatible con Docker al intentar inspeccionarla. Se comprobó posteriormente que Podman estaba operativo, que la imagen estaba disponible localmente y que el Docker SDK podía acceder a ella correctamente (`WORKDIR=/testbed`).

Al repetir únicamente la evaluación, se reutilizó exactamente el patch previamente generado para preservar Pass@1. SWE-PolyBench reutilizó la imagen local y completó correctamente la evaluación, obteniendo un resultado definitivo `not_resolved` (`resolved=False`).

No fue necesario regenerar el patch ni modificar el protocolo experimental.

**Estado:** resuelto.

**Evidencia:** `docs/screenshots/45-polybench-instance-id-mismatch.png` y `docs/screenshots/46-polybench-first-official-result.png`

### Compatibilidad local de SWE-bench Pro V1 en Windows/Podman

Durante la integración del evaluador oficial de SWE-bench Pro V1 se detectaron dos problemas de infraestructura al ejecutar la evaluación local mediante Docker SDK sobre Podman.

1. **Resolución de rutas relativas del evaluador.**
   El evaluador oficial utilizaba rutas relativas para acceder a `dockerfiles/base_dockerfile/...`. Al ejecutarlo desde el directorio raíz del TFM no encontraba estos recursos, aunque existían dentro del repositorio oficial. Se solucionó ejecutando el evaluador con el repositorio de SWE-bench Pro como directorio de trabajo (`cwd`) y utilizando rutas absolutas para los argumentos proporcionados por el adaptador.

2. **Finales de línea CRLF en los scripts del workspace.**
   Los scripts `run_script.sh` llegaban al workspace montado en el contenedor con finales de línea CRLF, incompatibles con Bash/Linux. Se comprobó que el script fuente contenía 0 caracteres CR, mientras que el fichero materializado en el workspace contenía 57. La causa era la escritura en modo texto realizada por `write_files_local()` en Windows. Se validó la solución escribiendo estos ficheros con `newline="\n"`, preservando finales de línea LF.

En ambos casos el adaptador mantuvo la condición como `infrastructure_error`, evitando contabilizar los fallos de infraestructura como fallos del modelo. Tras corregirlos se reutilizó exactamente el patch generado originalmente para preservar Pass@1, sin realizar una nueva llamada al LLM.

La evaluación posterior finalizó correctamente mediante el evaluador oficial de SWE-bench Pro V1 y produjo un resultado experimental válido: `not_resolved`.

**Evidencia:** `docs/screenshots/48-probench-first-official-result.png`
