# Prueba independiente de reproducibilidad del TFM

**Fecha de inicio:** 5 de noviembre de 2026

**Estado:** Validación de recuperación completada el 6 de noviembre de 2026; evaluación downstream no verificada

**Objetivo:** Verificar hasta qué punto es posible reconstruir el entorno experimental y reproducir los resultados del TFM a partir del código, los datos y los artefactos conservados.

## 1. Principios de la prueba

- No modificar el proyecto original `tfm-context-retrieval`.

- No sobrescribir los resultados experimentales originales.

- Ejecutar todas las pruebas en una copia independiente: `tfm-reproducibilidad`.

- Registrar los comandos, las versiones, los resultados y cualquier incidencia.

- Distinguir entre reproducir el análisis de los resultados, repetir la recuperación y repetir la evaluación downstream.

- No considerar demostrada la reproducibilidad hasta completar y comparar las pruebas.

## 2. Preparación del entorno independiente

### 2.1. Copia del proyecto

Se creó la carpeta `tfm-reproducibilidad` junto al repositorio original.

Comando utilizado:

```powershell

New-Item -ItemType Directory -Path ..\tfm-reproducibilidad -Force

```

Se copió el proyecto mediante:

```powershell

robocopy . ..\tfm-reproducibilidad /E /XD .venv .git __pycache__ /XF *.pyc

```

Resultado de la copia:

- Directorios copiados: 17.712.

- Archivos copiados: 68.029.

- Volumen copiado: aproximadamente 3,043 GB.

- Errores registrados por Robocopy: 0.

- Duración total: 12 minutos y 25 segundos.

La copia excluyó el entorno virtual original y los metadatos de Git.

### 2.2. Creación del entorno virtual

Se creó un entorno virtual nuevo:

```powershell

py -3.14 -m venv ..\tfm-reproducibilidad\\.venv

```

Se activó desde la carpeta de reproducibilidad:

```powershell

.\\.venv\Scripts\Activate.ps1

```

Comprobación realizada:

```powershell

python -c "import sys; print('Python:', sys.version); print('Entorno:', sys.executable)"

```

Resultado:

- Python 3.14.4.

- Ejecutable: `tfm-reproducibilidad\\.venv\Scripts\python.exe`.

### 2.3. Aislamiento de PYTHONPATH

Inicialmente, el entorno nuevo heredó rutas de los repositorios externos del proyecto original.

Se corrigió mediante:

```powershell

$env:PYTHONPATH = "$PWD;$PWD\external\ContextBench;$PWD\external\SWE-PolyBench\src"

```

Se verificó que las rutas apuntaban exclusivamente a `tfm-reproducibilidad`.

La comprobación:

```powershell

python -m pip show poly_bench_evaluation

```

mostró que los metadatos de SWE-PolyBench se detectaban desde la copia independiente.

Finalmente:

```powershell

python -m pip list --local

```

mostró únicamente:

```text

pip 26.0.1

```

Esto confirmó que no se habían instalado dependencias adicionales en el nuevo entorno virtual.

## 3. Código externo identificado

### ContextBench

Commit registrado y comprobado:

`1436c28a8eb95496da4ea69ad458b9f8a8eb7d61`

Estado del repositorio original: sin modificaciones locales detectadas por Git.

### SWE-PolyBench

Commit registrado y comprobado:

`9c836c5d7f3cb991934132b77d29e6941d912a07`

Estado del repositorio original: sin modificaciones locales detectadas por Git.

## 4. Incidencia de compatibilidad detectada previamente

En el entorno original actual se detectó un error al importar el evaluador de SWE-PolyBench.

Versiones observadas:

- `tree-sitter==0.26.0`.

- `tree-sitter-language-pack==1.21.0`.

- `tree-sitter-languages`: no instalado.

El evaluador intenta importar `get_language` desde `tree_sitter_languages` y, cuando no está disponible, utiliza una alternativa basada en una interfaz antigua de `tree_sitter.Language`.

Esta alternativa produce un `TypeError` con la versión actual.

El archivo `languages.so` existe.

**Estado:** incompatibilidad identificada; pendiente de comprobar una configuración funcional en el entorno independiente.

No se ha demostrado que esta combinación de dependencias fuera la utilizada durante las evaluaciones originales.

## 5. Instalación de dependencias

### 5.1. Primera instalación: dependencias de recuperación

**Estado: completada correctamente.**

Se ejecutó el siguiente comando desde el entorno virtual independiente de `tfm-reproducibilidad`:

```powershell

python -m pip install "datasets==5.0.1" "rank-bm25==0.2.2" "torch==2.14.1" "transformers==5.18.0" "numpy==2.5.3" "pandas==3.0.6"

```

Las seis dependencias solicitadas se instalaron correctamente:

| Dependencia  | Versión instalada |

| ------------ | ----------------- |

| datasets     | 5.0.1             |

| rank-bm25    | 0.2.2             |

| torch        | 2.14.1            |

| transformers | 5.18.0            |

| numpy        | 2.5.3             |

| pandas       | 3.0.6             |

También se instalaron automáticamente las dependencias transitivas necesarias.

**Incidencia observada:** durante la instalación, `pip` mostró advertencias de dependencias pendientes para `poly-bench-evaluation==0.1.0`, entre ellas `boto3`, `docker`, `GitPython`, `loguru`, `pydantic`, `scikit-learn`, `tree-sitter`, `tree-sitter-languages`, `unidiff` y `whatthepatch`.

Estas advertencias no impidieron completar la instalación. La configuración de SWE-PolyBench se abordará posteriormente, debido a las incompatibilidades ya identificadas.

**Resultado:** instalación completada, pendiente de verificar las importaciones y el funcionamiento de los componentes de recuperación.

### 5.2. Verificación de importaciones

**Estado: superada.**

Se ejecutó el siguiente comando desde el entorno virtual independiente:

```powershell

python -c "import datasets, rank_bm25, torch, transformers, numpy, pandas; print('OK: todas las importaciones funcionan')"

```

Resultado obtenido:

```text

OK: todas las importaciones funcionan

```

Las seis bibliotecas se importaron correctamente, sin errores.

**Conclusión:** las dependencias básicas de recuperación están operativas a nivel de importación. Queda pendiente comprobar la ejecución del código experimental y la reproducción de sus resultados.

### 5.3. Instalación de sentence-transformers

**Estado: instalación completada; importación pendiente de verificar.**

Se ejecutó:

```powershell

python -m pip install "sentence-transformers==6.1.0"

```

La instalación finalizó con `Successfully installed`.

Versiones instaladas:

- `sentence-transformers==6.1.0`

- `scikit-learn==1.9.1`

- `scipy==1.18.1`

- `joblib==1.6.0`

- `threadpoolctl==3.8.0`

Se instalaron también otras dependencias transitivas.

**Incidencia:** pip informó de dependencias ausentes de SWE-PolyBench y de una incompatibilidad entre `scikit-learn==1.9.1`, instalado en este entorno, y `scikit-learn==1.3.2`, requerido por SWE-PolyBench.

La instalación de `sentence-transformers` se completó a pesar de estas advertencias.

**Decisión:** mantener las versiones registradas para la recuperación y abordar por separado la compatibilidad del evaluador downstream.

**Pendiente:** verificar la importación de `sentence-transformers` y posteriormente la carga de UniXcoder.

**Verificación de importación: superada.**

Se ejecutó:

```powershell

python -c "from sentence_transformers import SentenceTransformer; print('OK: SentenceTransformer funciona')"

```

Resultado:

```text

OK: SentenceTransformer funciona

```

La clase `SentenceTransformer` se importó correctamente desde el entorno virtual independiente.

Esta comprobación no implica todavía que se haya cargado el modelo UniXcoder ni que se hayan reproducido resultados experimentales.

### 5.4. Revisión de la implementación semántica

**Estado: revisión del código completada; carga del modelo pendiente.**

Se inspeccionó `src/retrieval/semantic.py`.

La implementación utiliza:

- Modelo: `microsoft/unixcoder-base`.

- Bibliotecas: `torch` y `transformers`.

- Carga mediante `AutoTokenizer.from_pretrained()` y `AutoModel.from_pretrained()`.

- Modo de codificación: `encoder-only`.

- Longitud máxima: 512 tokens.

- Texto de cada chunk: ruta del archivo, símbolo y código.

- Embeddings: mean pooling con máscara de atención y normalización L2.

- Ranking: producto escalar y ordenación descendente.

Los embeddings de los repositorios se almacenan en archivos `.pt` dentro de `cache/`.

El código valida repositorio, commit, modelo, modo de codificación, longitud máxima y número de chunks antes de reutilizar una caché.

**Consideración de reproducibilidad:** se deberá distinguir entre las pruebas que reutilicen los embeddings previamente generados y aquellas que los regeneren desde el modelo.

La revisión del código no demuestra todavía que el modelo pueda cargarse correctamente en el nuevo entorno.

**Verificación de carga de UniXcoder: superada.**

Se ejecutó:

```powershell

python -c "from transformers import AutoTokenizer, AutoModel; m='microsoft/unixcoder-base'; t=AutoTokenizer.from_pretrained(m); model=AutoModel.from_pretrained(m); print('OK: UniXcoder cargado correctamente')"

```

Resultado:

```text

Loading weights: 100%|...| 199/199

OK: UniXcoder cargado correctamente

```

El tokenizador y el modelo `microsoft/unixcoder-base` se cargaron correctamente en el entorno independiente.

Se mostró una advertencia por realizar solicitudes no autenticadas a Hugging Face, sin impedir la carga.

**Conclusión:** la carga del modelo semántico funciona. Queda pendiente comprobar la generación de embeddings, la recuperación y la comparación con los resultados originales.

### 5.5. Revisión del procedimiento de ejecución experimental

**Estado: revisión completada; ejecución de reproducción pendiente.**

Se revisó el funcionamiento de `run_experiments.py`.

El programa:

- Lee las tareas seleccionadas desde `results/final_tasks.csv`.

- Permite seleccionar una tarea mediante `--task`.

- Lee los resultados existentes de `results/final_retrieval_results.csv`.

- Considera completada una tarea cuando dispone de las 18 combinaciones esperadas: 3 métodos × 3 valores de K × 2 niveles.

- Omite las tareas ya completadas.

- Guarda los resultados mediante una escritura que reemplaza el contenido del CSV.

- Registra los fallos en `results/final_retrieval_failures.csv`.

**Riesgo identificado:** ejecutar directamente una tarea pendiente puede modificar el archivo de resultados existente. Ejecutar una tarea ya completada no reproduce sus resultados, porque el programa la omite.

**Decisión:** preparar una ejecución aislada que utilice el mismo código experimental y un archivo de resultados independiente.

La prueba deberá conservar los resultados originales para permitir una comparación posterior, sin sobrescribirlos.

## 6. Pruebas de reproducción independientes

### 6.1. Preparación de una ejecución aislada

Se ha preparado una primera prueba de reproducción en el directorio `reproduction_runs/test_01`, utilizando una copia independiente del proyecto y un entorno virtual nuevo con Python 3.14.4.

Se ha seleccionado la tarea `pytest-dev__pytest-5809`, perteneciente al conjunto original de 50 tareas. Se ha comprobado que dispone de 18 resultados de referencia en `results/final_retrieval_results.csv`, correspondientes a las combinaciones de método, valor de K y nivel de evaluación.

Para evitar sobrescribir resultados existentes, se ha creado el directorio `reproduction_runs/test_01/results` y se ha copiado únicamente `final_tasks.csv`. No se han copiado resultados experimentales ni cachés semánticas.

La revisión del código ha confirmado que las rutas de resultados (`results/`), repositorios (`repos/`) y caché semántica (`cache/`) son relativas al directorio de ejecución. Por tanto, ejecutar el programa desde `reproduction_runs/test_01` permite mantener estos artefactos separados de los originales.

También se ha verificado satisfactoriamente la importación de `run_experiments.py` desde el entorno virtual independiente.

**Estado:** preparación completada. La ejecución de la tarea y la comparación de resultados están pendientes.

### 6.2. Primera ejecución: dependencia Tree-sitter ausente

Se realizó una primera ejecución aislada de la tarea `pytest-dev__pytest-5809` mediante el comando:

```powershell

python ..\\..\run_experiments.py --task "pytest-dev__pytest-5809"

```

La ejecución se inició desde `reproduction_runs/test_01`, utilizando el entorno virtual independiente con Python 3.14.4.

**Operaciones completadas correctamente:**

- Carga del modelo semántico `microsoft/unixcoder-base` (UniXcoder).

- Clonación independiente del repositorio `pytest-dev/pytest`.

- Preparación del repositorio en el commit `8aba863a634f40560e25055d179220f0eefabe9a`.

- Construcción de 3.921 chunks.

- Inicio del procedimiento de recuperación BM25.

**Incidencia detectada:**

La ejecución se interrumpió durante la evaluación a nivel de símbolo, al intentar utilizar el extractor Tree-sitter de ContextBench:

```text

RuntimeError: tree-sitter is required for symbol extraction.

Install: pip install tree-sitter-language-pack

```

El programa registró una tarea fallida y no generó ninguna fila de resultados de recuperación.

**Corrección aplicada:**

Se instalaron en el entorno aislado las versiones identificadas previamente en el entorno original:

```powershell

python -m pip install "tree-sitter-language-pack==1.21.0"

```

La instalación incorporó `tree-sitter==0.26.0` y `tree-sitter-language-pack==1.21.0`.

Posteriormente, se comprobó que ContextBench podía utilizar Tree-sitter:

```powershell

python -c "from contextbench.extractors.treesitter import _require_tree_sitter; _require_tree_sitter(); print('OK: Tree-sitter disponible para ContextBench')"

```

La comprobación finalizó correctamente.

Durante la instalación, pip notificó conflictos de dependencias asociados a `poly-bench-evaluation`, componente utilizado en la evaluación downstream. Estos avisos no impidieron la instalación de Tree-sitter, pero quedan pendientes de análisis específico.

**Estado:** incidencia de importación resuelta. Pendiente repetir la tarea y comparar las métricas obtenidas con los resultados originales.

### 6.3. Ejecución independiente completada y comparación de resultados

Tras resolver la dependencia de Tree-sitter, se repitió la ejecución de la tarea `pytest-dev__pytest-5809` desde el directorio aislado `reproduction_runs/test_01`.

La ejecución finalizó correctamente, con las siguientes características:

- Repositorio: `pytest-dev/pytest`.

- Commit base: `8aba863a634f40560e25055d179220f0eefabe9a`.

- Chunks generados: 3.921.

- Modelo semántico: `microsoft/unixcoder-base` (UniXcoder).

- Caché semántica original: no reutilizada.

- Embeddings generados desde cero: 3.921.

- Tiempo de generación del índice semántico: 15,11 minutos.

- Tiempo total de la tarea: 15,24 minutos.

- Tareas completadas: 1.

- Fallos durante esta ejecución: 0.

- Filas de resultados generadas: 18.

Los resultados independientes se almacenaron en:

`reproduction_runs/test_01/results/final_retrieval_results.csv`

Posteriormente, se compararon con los resultados originales de la misma tarea, conservados en:

`results/final_retrieval_results.csv`

La comparación se realizó utilizando como identificadores la tarea, el método de recuperación, el valor de K y el nivel de evaluación. Se contrastaron las métricas `coverage`, `precision` y `f1` de cada combinación.

**Resultados de la comparación:**

| Comprobación                                    | Resultado |

| ----------------------------------------------- | --------: |

| Filas originales                                |        18 |

| Filas reproducidas                              |        18 |

| Combinaciones emparejadas                       |        18 |

| Combinaciones sin correspondencia               |         0 |

| Combinaciones con diferencias superiores a 1e-9 |         0 |

| Diferencia máxima absoluta                      |       0,0 |

Las 18 combinaciones experimentales reprodujeron exactamente los valores numéricos originales, sin diferencias detectadas en las métricas comparadas.

**Conclusión:** se ha demostrado la reproducibilidad numérica de los resultados de recuperación de la tarea `pytest-dev__pytest-5809` mediante una ejecución independiente que regeneró los embeddings semánticos y utilizó un directorio de trabajo aislado.

Esta comprobación constituye una primera evidencia de reproducibilidad del pipeline experimental. Su alcance se limita a la tarea evaluada y no permite afirmar todavía que se hayan reproducido independientemente los resultados de las 50 tareas de la muestra final.

### 6.4. Segunda reproducción independiente: psf/requests

Con el objetivo de ampliar la validación a un repositorio diferente y comprobar un caso con diferencias entre los métodos de recuperación, se seleccionó la tarea `psf__requests-1142`.

En los resultados originales, para K=10 y evaluación a nivel de líneas, esta tarea presentaba los siguientes valores de F1:

| Método      | F1 original |

| ----------- | ----------: |

| BM25        |    0,261283 |

| UniXcoder   |    0,044944 |

| Híbrido RRF |    0,297170 |

Este caso resulta especialmente relevante porque el método híbrido supera a los dos métodos individuales.

La reproducción se realizó desde `reproduction_runs/test_02`, utilizando un directorio independiente del empleado en la primera prueba.

**Características de la ejecución:**

- Repositorio: `psf/requests`.

- Commit base: `22623bd8c265b78b161542663ee980738441c307`.

- Chunks generados: 428.

- Modelo semántico: `microsoft/unixcoder-base`.

- Embeddings del corpus generados desde cero: 428.

- Tiempo de generación del índice semántico: 1,36 minutos.

- Tiempo total de ejecución: 1,54 minutos.

- Tareas completadas: 1.

- Fallos de ejecución: 0.

- Filas de resultados generadas: 18.

Durante la construcción de chunks aparecieron advertencias `SyntaxWarning` relacionadas con secuencias de escape y un aviso de imposibilidad de procesar el archivo `requests/packages/urllib3/contrib/ntlmpool.py`, debido a un error `unicodeescape`. Estas incidencias no impidieron completar la ejecución. La comparación posterior confirmó la coincidencia de las métricas finales, aunque no se realizó una comparación individual de todos los chunks generados.

**Comparación con los resultados originales:**

| Comprobación                                    | Resultado |

| ----------------------------------------------- | --------: |

| Filas originales                                |        18 |

| Filas reproducidas                              |        18 |

| Combinaciones emparejadas                       |        18 |

| Combinaciones sin correspondencia               |         0 |

| Combinaciones con diferencias superiores a 1e-9 |         0 |

| Diferencia máxima absoluta                      |       0,0 |

Las 18 combinaciones reprodujeron exactamente los valores originales de `coverage`, `precision` y `f1`.

**Conclusión:** la segunda prueba confirma la reproducibilidad numérica de los resultados de recuperación para una tarea de un repositorio diferente, incluyendo un caso en el que la fusión híbrida RRF obtiene mejores resultados que BM25 y UniXcoder individualmente.

### 6.5. Balance de las pruebas independientes

Se han completado dos reproducciones independientes:

| Prueba    | Repositorio        |    Chunks | Combinaciones coincidentes |

| --------- | ------------------ | --------: | -------------------------: |

| 01        | pytest-dev/pytest  |     3.921 |                      18/18 |

| 02        | psf/requests       |       428 |                      18/18 |

| **Total** | **2 repositorios** | **4.349** |                  **36/36** |

En ambas pruebas se regeneraron los índices semánticos sin reutilizar las cachés originales y se compararon las métricas obtenidas con los resultados previamente registrados.

No se detectaron diferencias numéricas en ninguna de las 36 combinaciones verificadas, considerando las métricas `coverage`, `precision` y `f1`, con una tolerancia absoluta de `1e-9`. Estos resultados motivaron la ampliación de la validación a una muestra de 20 tareas, una por cada repositorio representado en el benchmark original.

### 6.6. Ampliación de la prueba: selección y aislamiento

La muestra original del experimento de recuperación consta de 50 tareas, distribuidas en 20 repositorios, y genera 900 combinaciones de resultados (50 tareas × 3 métodos × 3 valores de K × 2 niveles de evaluación). Para la comprobación independiente se seleccionó una tarea por repositorio, hasta cubrir los 20 repositorios. La selección constituye una **muestra de validación**, no una repetición completa de las 50 tareas.

Se conservaron las dos pruebas individuales descritas en las secciones 6.3 y 6.4 y se añadieron dos lotes aislados:

| Ejecución | Ubicación | Tareas | Filas de resultados |
| --- | --- | ---: | ---: |
| Prueba 01: pytest | `reproduction_runs/test_01/` | 1 | 18 |
| Prueba 02: requests | `reproduction_runs/test_02/` | 1 | 18 |
| Primer lote, incluido SymPy | `reproduction_runs/batch_18/` | 11 | 198 |
| Segundo lote, excluido SymPy | `reproduction_runs/batch_07/` | 7 | 126 |
| **Total** | | **20** | **360** |

El lote `batch_18` contenía inicialmente 18 tareas (una por cada repositorio no cubierto en las dos pruebas individuales). Después de completar 10 tareas, se separaron las siete tareas posteriores a SymPy en `batch_07`, evitando repetir cálculos mientras se investigaba la incidencia de ese repositorio. Finalmente se completó SymPy en `batch_18`. Por ello, los dos lotes tienen **11 y 7 tareas efectivamente completadas**, respectivamente, aunque el CSV de selección de `batch_18` contiene 18 tareas.

Las ejecuciones utilizaron el mismo código de recuperación y evaluación de métricas, repositorios preparados en los commits de referencia y directorios de trabajo separados para los resultados, repositorios e índices. Se generaron índices semánticos nuevos en las pruebas, sin reutilizar las cachés semánticas originales. El procedimiento de recuperación abarcó BM25, UniXcoder y fusión híbrida RRF, para K=5, 10 y 20, con evaluación a nivel de archivo y de línea.

### 6.7. Incidencias en la ejecución ampliada

**Falta de espacio durante la preparación de SymPy.** El primer intento de clonación de `sympy/sympy` se interrumpió al agotarse el espacio disponible. Tras liberar espacio y eliminar únicamente la clonación parcial del entorno aislado, se reanudó el lote. Los 180 resultados de las diez tareas ya completadas se conservaron.

**Cierre inesperado de Python durante SymPy.** En un intento posterior, el repositorio SymPy se preparó en el commit `63f8f465d48559fecb4e4bf3c48b75bf15a3e0ef` y se construyeron 38.897 chunks. BM25 terminó, pero el proceso se cerró durante la generación de embeddings semánticos, después de informar de aproximadamente 8.800 embeddings procesados. Windows registró un fallo `APPCRASH` de `python.exe` con código `0xc0000005` (violación de acceso a memoria). También aparecieron eventos `LiveKernelEvent 141`, pero la información disponible **no permite establecer una causa definitiva**. Se verificó que PyTorch era la compilación `2.14.1+cpu`, sin CUDA, y que utilizaba ocho hilos de CPU.

**Reintento satisfactorio.** Se volvió a ejecutar el lote con la configuración original, sin modificar el algoritmo ni reducir el número de hilos. SymPy completó la generación de embeddings y produjo las 18 combinaciones esperadas. Sus métricas coincidieron con las originales en las tres métricas. La incidencia anterior se documenta como un fallo transitorio del proceso o del entorno cuya causa exacta no se determinó; no como una discrepancia experimental.

**Cierre de Visual Studio Code durante el segundo lote.** Se comprobó el CSV de resultados antes de reanudar: cinco tareas tenían 18 filas cada una y las otras dos no tenían resultados. El programa omitió las cinco ya completadas y finalizó Flask y Pylint. Las 126 filas del segundo lote quedaron guardadas y se verificaron posteriormente.

### 6.8. Comparación automatizada de los resultados

Se creó el script `scripts/validate_reproducibility.py` para convertir las comprobaciones manuales en un procedimiento repetible. Desde la raíz de `tfm-reproducibilidad` se ejecuta:

```powershell
python scripts/validate_reproducibility.py
```

El script lee el archivo original `results/final_retrieval_results.csv` y los cuatro archivos de resultados reproducidos de `test_01`, `test_02`, `batch_18` y `batch_07`. Comprueba que existan 20 tareas y 360 filas, que no haya claves duplicadas y que cada tarea contenga las 18 combinaciones esperadas. Empareja los registros mediante `task_id`, `method`, `k` y `level`, comprueba la correspondencia con los originales y compara `coverage`, `precision` y `f1` con `rtol=0`, `atol=1e-9` y sin aceptar valores ausentes.

Solo cuando todas las comprobaciones se superan, el script genera el archivo consolidado:

`results/reproducibility_validation.csv`

Este CSV conserva las métricas originales y reproducidas junto con sus claves de identificación. No sustituye a los cuatro CSV de ejecución, que constituyen la evidencia primaria de los resultados regenerados.

La ejecución definitiva del script el 6 de noviembre de 2026 produjo:

```text
VALIDACION DE REPRODUCIBILIDAD EXPERIMENTAL
Tareas reproducidas: 20
Combinaciones reproducidas: 360
Combinaciones sin correspondencia original: 0
coverage     | Diferencias: 0 | Diferencia maxima: 0
precision    | Diferencias: 0 | Diferencia maxima: 0
f1           | Diferencias: 0 | Diferencia maxima: 0
RESULTADO: REPRODUCCION NUMERICA CORRECTA
Tareas verificadas: 20
Combinaciones verificadas: 360
Repositorios representados: 20
Diferencias numericas: 0
Tolerancia absoluta: 1e-09
```

### 6.9. Balance final de la validación de recuperación

| Indicador | Resultado |
| --- | ---: |
| Repositorios originales representados | 20 de 20 (100 %) |
| Tareas originales reproducidas | 20 de 50 (40 %) |
| Combinaciones originales verificadas | 360 de 900 (40 %) |
| Combinaciones sin correspondencia | 0 |
| Diferencias en `coverage` | 0 |
| Diferencias en `precision` | 0 |
| Diferencias en `f1` | 0 |
| Máxima diferencia absoluta observada | 0,0 |
| Tolerancia absoluta de comparación | `1e-9` |

Las 360 combinaciones de la muestra reprodujeron los valores originales de las tres métricas. La validación cubre todos los repositorios, pero solo una tarea por repositorio. Por tanto, el resultado demuestra **reproducibilidad numérica de la recuperación en la muestra seleccionada**, no una reproducción completa de las 900 combinaciones del experimento original.

## 7. Alcance, limitaciones y conclusiones

La reconstrucción del entorno virtual, la instalación de dependencias, la preparación de repositorios en los commits de referencia, la regeneración de índices semánticos y la repetición del procedimiento de recuperación permitieron obtener resultados numéricamente coincidentes con los originales en las 20 tareas verificadas. La comparación automatizada no detectó diferencias en `coverage`, `precision` ni `f1` para ninguna de las 360 combinaciones, con una tolerancia absoluta de `1e-9`.

El alcance de esta evidencia está delimitado por los siguientes aspectos:

- **Cobertura parcial de tareas:** se repitieron 20 de las 50 tareas, aunque se representaron los 20 repositorios.
- **Ámbito de evaluación:** se verificaron los resultados de recuperación y sus métricas a nivel de archivo y línea; **no se ha reproducido ni validado en esta prueba la evaluación downstream de parches o respuestas generadas por un LLM**.
- **Independencia del entorno:** la ejecución se realizó en una copia de trabajo y un entorno virtual nuevos, pero sobre la misma máquina. No constituye por sí sola una validación externa realizada por un tercero en otro sistema.
- **Dependencias externas:** las versiones y los commits utilizados se registran en este documento; para facilitar la repetición por terceros conviene conservar también una especificación instalable de dependencias y las instrucciones de preparación.
- **Incidencias operativas:** se produjeron una falta de espacio y un cierre inesperado de Python durante SymPy. La tarea se completó posteriormente sin cambios metodológicos; no se identificó con certeza la causa del cierre anterior.

**Conclusión:** la prueba independiente proporciona evidencia sólida y verificable de que el procedimiento de recuperación del TFM es numéricamente reproducible en una muestra que cubre los 20 repositorios originales. Esta afirmación no debe extenderse a las 30 tareas no repetidas ni a la evaluación downstream sin nuevas comprobaciones.
