# Registro experimental del TFM

## Objetivo

Evaluar la influencia de diferentes estrategias de recuperación de contexto
en la capacidad de un LLM para resolver incidencias software a nivel de repositorio.

Estrategias previstas:

- Recuperación léxica mediante BM25.
- Recuperación semántica mediante embeddings.
- Recuperación híbrida mediante BM25 + embeddings + RRF.

La calidad del retrieval y la capacidad posterior del LLM para resolver la
incidencia se evaluarán de forma separada.

---

## Entorno experimental

### Lenguaje de implementación

Se utiliza Python para implementar el pipeline experimental.

Motivos:

- Facilitar la integración con ContextBench y Hugging Face Datasets.
- Facilitar posteriormente el uso de modelos de embeddings y herramientas
  del ecosistema ML/IR.
- Reducir la complejidad de integración durante la experimentación.

La posible reutilización posterior de las estrategias obtenidas en un agente
implementado en TypeScript queda fuera del experimento principal.

### Entorno

- Python: 3.14.4
- Entorno virtual: `.venv`
- Hugging Face Datasets: 5.0.1

---

## Benchmark

Benchmark seleccionado: ContextBench.

El dataset se carga mediante Hugging Face Datasets.

En la versión utilizada se han observado:

- Split: `train`
- Número de tareas: 1136

Campos disponibles:

- `instance_id`
- `original_inst_id`
- `repo`
- `repo_url`
- `language`
- `base_commit`
- `gold_context`
- `patch`
- `test_patch`
- `problem_statement`
- `f2p`
- `p2p`
- `source`

---

## Piloto

### Primera tarea

- `original_inst_id`: `astropy__astropy-12907`
- `instance_id`: `SWE-Bench-Verified__python__maintenance__bugfix__8adb3e00`
- Repositorio: `astropy/astropy`
- Lenguaje: Python
- `base_commit`: `d16bfe05a744909de4b27f5875fe0d4ed41ce607`

El repositorio se obtiene mediante Git y se realiza checkout exactamente sobre
el `base_commit` proporcionado por ContextBench.

Se verificó mediante:

`git rev-parse HEAD`

Resultado:

`d16bfe05a744909de4b27f5875fe0d4ed41ce607`

El working tree estaba limpio.

---

## Chunking

### Estrategia inicial

Se utiliza chunking estructural basado en el AST de Python.

Unidad principal de chunk:

- funciones;
- métodos;
- funciones anidadas.

Cada chunk conserva:

- `repository`
- `file_path`
- `symbol`
- `start_line`
- `end_line`
- `code`

Los símbolos anidados conservan su ámbito para evitar identificadores ambiguos.

Ejemplos:

- `_arith_oper._n_inputs_outputs`
- `_cdot._n_inputs_outputs`

### Decisión experimental

El mismo conjunto de chunks se utilizará para las estrategias léxica,
semántica e híbrida con el objetivo de mantener constante el chunking y
aislar la estrategia de recuperación.

### Corpus del piloto

Para el repositorio `astropy/astropy` en el commit seleccionado:

- Chunks generados: 15.765
- Archivos Python con al menos un chunk: 739

El recorrido de archivos se ordena para mantener un comportamiento
determinista.

Los errores de parsing o codificación se registrarán como exclusiones técnicas
en lugar de interrumpir la construcción completa del corpus.

En esta ejecución no se observaron errores de parsing ni de codificación.

### Limitaciones actuales del chunking

La versión inicial no genera chunks independientes para:

- imports;
- código a nivel de módulo;
- clases completas.

Estas limitaciones se mantienen para evitar convertir el TFM en una
comparación de estrategias de chunking. Solo se modificarán si se identifica
un problema general que impida ejecutar correctamente el experimento.

## Recuperación léxica: BM25

Se implementó la estrategia de recuperación léxica mediante BM25.

Configuración:

- Corpus: 15.765 chunks.
- Consulta: `problem_statement` de ContextBench.
- Representación de cada documento: `file_path + symbol + code`.
- Tokenización: extracción mediante la expresión regular `[A-Za-z0-9_]+`
  y conversión a minúsculas.
- Valores de evaluación: K = 5, 10 y 20.
- No se utiliza `gold_context`, `patch` ni `test_patch` durante la recuperación.

Para la tarea piloto, los dos primeros resultados del ranking fueron:

1. `astropy/modeling/separable.py:66-102` — `separability_matrix`
   — score 330.4252.
2. `astropy/modeling/separable.py:27-63` — `is_separable`
   — score 243.0295.

El resto del Top-20 contiene principalmente funciones de tests y otros módulos.

---

## Evaluación de recuperación

Para estudiar las métricas de ContextBench se obtuvo una copia del
repositorio oficial.

Versión utilizada:

- Commit de ContextBench:
  `1436c28a8eb95496da4ea69ad458b9f8a8eb7d61`

Se fija explícitamente el commit para garantizar que la definición e
implementación de las métricas utilizadas durante el experimento sea
reproducible.

### Granularidades utilizadas

Para la evaluación principal se utilizan dos granularidades:

- **File-level:** permite comprobar si el recuperador identifica los
  ficheros relevantes.
- **Line-level:** permite medir cuánto del contexto gold concreto está
  cubierto por los chunks recuperados.

Durante el piloto se exploró también la evaluación a nivel de símbolo
proporcionada por ContextBench. Finalmente no se incluyó como métrica
principal debido a que el chunking empleado está basado principalmente
en funciones y métodos, por lo que esta granularidad está estrechamente
relacionada con la propia unidad de recuperación.

Se optó por mantener fichero como granularidad gruesa y líneas como
granularidad fina para simplificar el diseño experimental.

Los intervalos de líneas solapados o adyacentes de un mismo fichero se
fusionan antes de calcular las métricas, evitando contar una misma línea
varias veces.

### Métricas

Se utilizan:

- **Coverage (Recall):** proporción del contexto gold que ha sido recuperado.
- **Precision:** proporción del contexto recuperado que pertenece al gold.
- **F1:** media armónica de Coverage y Precision.

### Resultados del piloto BM25

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.2500 | 0.4000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   1.0000 |    0.1250 | 0.2222 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   1.0000 |    0.0714 | 0.1333 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

### Observación

BM25 recupera `astropy/modeling/separable.py` desde las primeras
posiciones del ranking, por lo que el Coverage a nivel de fichero es
1.0 para todos los valores de K evaluados.

Sin embargo, los chunks recuperados de dicho fichero dentro del Top-20
(`separability_matrix`, líneas 66-102, e `is_separable`, líneas 27-63)
no se solapan con las regiones del gold context (líneas 200-248,
242-248 y 290-317).

Por ello, las métricas line-level son 0 para K = 5, 10 y 20.

Al aumentar K, la precisión a nivel de fichero disminuye porque se
recuperan más ficheros que no pertenecen al gold context, sin aumentar
la cobertura para esta tarea piloto.

Este resultado corresponde únicamente a una tarea piloto y no permite
extraer conclusiones generales sobre el rendimiento de BM25.

Captura asociada:

`docs/screenshots/07-bm25-file-line.png`

### Validación de la implementación

La implementación de las métricas se verificó mediante tests unitarios.

Se comprobaron casos de:

- coincidencia completa entre predicción y gold;
- fichero correcto sin solapamiento de líneas;
- solapamiento parcial de líneas;
- coincidencia de símbolos durante la exploración de la granularidad
  symbol-level.

Los cuatro tests finalizaron correctamente.

Comando de validación:

`python -m unittest tests.test_retrieval_metrics -v`

## Recuperación semántica

### Modelo de embeddings

Para la recuperación semántica se utiliza `microsoft/unixcoder-base` (UniXcoder),
un modelo orientado a la representación y búsqueda de código.

El modelo se ejecuta localmente sobre CPU. Los embeddings generados tienen
una dimensión de 768.

### Benchmark inicial

Antes de generar los embeddings del repositorio completo se realizó una prueba
de rendimiento sobre 100 chunks de Astropy, utilizando los mismos chunks
empleados en la recuperación BM25.

Resultados:

- Chunks totales del repositorio: 15.765
- Chunks procesados en el benchmark: 100
- Dimensión del embedding: 768
- Tiempo total: 45,98 s
- Tiempo medio por chunk: 0,460 s
- Tiempo estimado para los 15.765 chunks: 120,8 min

La generación completa de embeddings es computacionalmente más costosa que
la recuperación léxica. Sin embargo, los embeddings pueden almacenarse y
reutilizarse, evitando su recálculo para consultas posteriores sobre el mismo
estado del repositorio.

Se mantiene la ejecución local como opción principal. El uso de GPU se
considerará únicamente si, al escalar el experimento a la muestra final,
el tiempo total de generación de embeddings resulta poco práctico.

### Configuración definitiva

La recuperación semántica utiliza `microsoft/unixcoder-base` (UniXcoder).

La representación del corpus mantiene los mismos chunks utilizados por BM25,
de forma que la estrategia de recuperación sea la principal variable que
cambia entre ambos métodos.

Para cada chunk se construye una representación textual formada por:

- ruta del fichero,
- símbolo,
- código del chunk.

La codificación utiliza el modo `encoder-only` de UniXcoder, con una longitud
máxima de 512 tokens. Las representaciones de los tokens válidos se agregan
mediante mean pooling y el vector resultante se normaliza mediante norma L2.

Para el repositorio Astropy en el commit
`d16bfe05a744909de4b27f5875fe0d4ed41ce607` se generaron:

- 15.765 embeddings,
- 768 dimensiones por embedding.

Los embeddings del corpus se almacenan en caché y pueden reutilizarse para
distintas consultas mientras se mantengan constantes el repositorio, commit,
modelo y procedimiento de codificación.

### Resultados del piloto semántico

La recuperación semántica se evaluó sobre la tarea piloto
`astropy__astropy-12907` utilizando los mismos chunks y las mismas métricas
empleadas para BM25.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.2500 | 0.4000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   1.0000 |    0.1667 | 0.2857 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   1.0000 |    0.0714 | 0.1333 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

En este caso piloto, la recuperación semántica localiza el fichero que
contiene el contexto gold, pero los chunks recuperados en los primeros
20 resultados no solapan con las líneas gold de ContextBench.

A nivel de fichero, BM25 y la recuperación semántica presentan resultados
similares, aunque la recuperación semántica obtiene mayor precisión y F1
en K=10 para esta tarea concreta.

Este resultado corresponde únicamente a una tarea piloto y no permite
extraer conclusiones generales sobre el rendimiento relativo de ambas
estrategias.

Captura: `docs/screenshots/08-semantic-file-line.png`

### Resultados del piloto híbrido

La estrategia híbrida combina los rankings obtenidos mediante BM25 y
recuperación semántica utilizando Reciprocal Rank Fusion (RRF).

Para la fusión se utilizan los primeros 100 resultados de cada estrategia
y una constante RRF de 60. La evaluación final se mantiene en K=5, K=10
y K=20.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.2500 | 0.4000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   1.0000 |    0.1111 | 0.2000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   1.0000 |    0.0667 | 0.1250 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

En esta tarea piloto, la estrategia híbrida recupera el fichero que contiene
el contexto gold, pero ninguno de los chunks recuperados en los primeros
20 resultados solapa con las líneas gold de ContextBench.

La combinación mediante RRF no mejora los resultados respecto a las
estrategias individuales en esta tarea concreta. Este resultado no permite
extraer conclusiones generales, ya que corresponde únicamente a una tarea
piloto.

Captura: `docs/screenshots/09-hybrid-file-line.png`

### Validación del pipeline BM25 generalizado

Se generalizó la preparación del repositorio para obtener dinámicamente desde
ContextBench el repositorio, su URL y el `base_commit` correspondiente a cada
tarea.

Como comprobación de regresión, se volvió a ejecutar la tarea piloto
`astropy__astropy-12907`.

El pipeline generalizado produjo 15.765 chunks y reprodujo exactamente los
resultados BM25 obtenidos previamente para K=5, K=10 y K=20.

Esto confirma que la generalización de la infraestructura no modificó el
comportamiento experimental del recuperador BM25 en la tarea piloto.

**Evidencia:** `docs/screenshots/10-bm25-generalized-pipeline.png`

### Distribución de tareas Python en ContextBench

Se analizó la distribución de tareas disponibles en ContextBench antes de
seleccionar las incidencias del mini-piloto.

El benchmark contiene 1.136 tareas, de las cuales 512 corresponden a Python,
distribuidas entre 20 repositorios.

La distribución no es uniforme. Algunos repositorios concentran una proporción
considerable de las tareas, destacando `django/django` con 129 tareas,
`huggingface/transformers` con 67 y `sympy/sympy` y `ansible/ansible` con 52
cada uno.

Debido a esta concentración, se decidió no realizar una selección aleatoria
directa sobre todas las tareas Python para el mini-piloto.

Para validar la generalización del pipeline se utilizarán aproximadamente cinco
tareas pertenecientes a cinco repositorios diferentes, mediante un
procedimiento reproducible con semilla fija.

### Selección reproducible del mini-piloto

Para validar el funcionamiento del pipeline sobre múltiples repositorios se
seleccionaron cinco tareas Python de ContextBench pertenecientes a cinco
repositorios diferentes.

La selección se realizó mediante un procedimiento pseudoaleatorio reproducible
con semilla fija `42`. Primero se seleccionaron cinco repositorios diferentes
entre los 20 repositorios con tareas Python y posteriormente una tarea de cada
repositorio seleccionado.

Las tareas seleccionadas fueron:

1. `django__django-12663` — `django/django`
2. `Significant-Gravitas__AutoGPT-4652` — `Significant-Gravitas/AutoGPT`
3. `matplotlib__matplotlib-25479` — `matplotlib/matplotlib`
4. `langchain-ai__langchain-6765` — `langchain-ai/langchain`
5. `scikit-learn__scikit-learn-25931` — `scikit-learn/scikit-learn`

El objetivo de este mini-piloto no es obtener conclusiones comparativas
definitivas, sino comprobar que el pipeline experimental funciona correctamente
sobre tareas y repositorios diferentes antes de escalar el experimento.

**Evidencia:** `docs/screenshots/11-mini-pilot-selection.png`

### Validación de BM25 sobre un segundo repositorio

Como primera comprobación del pipeline generalizado fuera de la tarea piloto
de Astropy, se ejecutó BM25 sobre la tarea `django__django-12663`, perteneciente
al repositorio `django/django`.

El pipeline obtuvo automáticamente desde ContextBench el repositorio y el
`base_commit`, clonó el repositorio, realizó el checkout del estado requerido,
generó 24.541 chunks y ejecutó posteriormente la recuperación y evaluación.

La ejecución finalizó correctamente sin necesidad de modificar manualmente el
código para adaptarlo al nuevo repositorio.

A diferencia de la tarea piloto de Astropy, en esta tarea se obtuvo solapamiento
con el gold también a nivel de líneas. Para K=20 se alcanzó una cobertura de
fichero de 1,0000 y una cobertura de líneas de 0,0685.

Estos resultados no se utilizan todavía para extraer conclusiones comparativas
sobre BM25. La finalidad de esta ejecución es validar la generalización técnica
del pipeline antes de ejecutar el mini-piloto completo.

**Evidencia:** `docs/screenshots/12-bm25-django-generalization.png`

### Validación de la generalización de la recuperación semántica

Se validó la versión generalizada del pipeline de recuperación semántica
utilizando nuevamente la tarea `astropy__astropy-12907`.

El pipeline obtuvo dinámicamente el repositorio y `base_commit` desde
ContextBench, generó los mismos 15.765 chunks y reutilizó correctamente
la caché de embeddings correspondiente al repositorio y commit.

Los resultados de evaluación coincidieron exactamente con los obtenidos
antes de la generalización:

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.2500 | 0.4000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   1.0000 |    0.1667 | 0.2857 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   1.0000 |    0.0714 | 0.1333 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

Esto confirma que la generalización de la infraestructura no modificó
el comportamiento del recuperador semántico.

### Validación de la generalización de la recuperación híbrida

Se validó la versión generalizada del pipeline híbrido BM25 + recuperación
semántica mediante RRF utilizando nuevamente la tarea
`astropy__astropy-12907`.

El pipeline obtuvo dinámicamente la tarea, repositorio y `base_commit`,
generó los mismos 15.765 chunks y reutilizó correctamente la caché de
embeddings semánticos. Para la fusión se utilizaron los 100 primeros
resultados de BM25 y los 100 primeros resultados semánticos.

Los resultados coincidieron exactamente con los obtenidos antes de la
generalización:

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.2500 | 0.4000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   1.0000 |    0.1111 | 0.2000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   1.0000 |    0.0667 | 0.1250 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

La prueba confirma que la generalización de la infraestructura no alteró
el comportamiento de la estrategia híbrida.

### Recuperación semántica sobre Django

Se ejecutó la recuperación semántica generalizada sobre la tarea
`django__django-12663`, perteneciente al repositorio `django/django`
en el `base_commit` especificado por ContextBench.

Se generaron 24.541 chunks y sus correspondientes embeddings mediante
UniXcoder. El índice semántico fue almacenado en caché para su
reutilización posterior.

Los resultados obtenidos fueron:

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   0.0000 |    0.0000 | 0.0000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   0.0000 |    0.0000 | 0.0000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   0.0000 |    0.0000 | 0.0000 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

En esta tarea concreta, la estrategia semántica no recuperó ningún
fichero perteneciente al contexto gold dentro de los primeros 20
resultados. Este resultado contrasta con BM25, que alcanzó una cobertura
de fichero de 1.0000 en K=20.

El resultado corresponde únicamente a esta tarea y no permite todavía
extraer conclusiones generales sobre la superioridad de una estrategia.

**Evidencia:** `docs/screenshots/13-semantic-django-generalization.png`

### Recuperación híbrida sobre Django

Se ejecutó la estrategia híbrida BM25 + recuperación semántica mediante
RRF sobre la tarea `django__django-12663`.

El pipeline reutilizó correctamente los 24.541 embeddings previamente
almacenados para el repositorio y commit, calculando únicamente el
embedding correspondiente al issue. Para RRF se utilizaron los primeros
100 resultados de cada estrategia.

Los resultados obtenidos fueron:

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   0.1667 |    0.3333 | 0.2222 |
| 5   | line  |   0.0479 |    0.0809 | 0.0602 |
| 10  | file  |   0.1667 |    0.1250 | 0.1429 |
| 10  | line  |   0.0479 |    0.0449 | 0.0464 |
| 20  | file  |   0.1667 |    0.0714 | 0.1000 |
| 20  | line  |   0.0479 |    0.0218 | 0.0299 |

En esta tarea, la combinación mediante RRF no mejoró sistemáticamente
a BM25. El híbrido obtuvo un F1 de fichero ligeramente superior en K=5,
pero en K=20 BM25 alcanzó una cobertura de fichero de 1.0000 frente a
0.1667 del híbrido.

Estos resultados corresponden a una única tarea y no permiten todavía
extraer conclusiones generales sobre las estrategias.

**Evidencia:** `docs/screenshots/14-hybrid-django-generalization.png`

### BM25 sobre AutoGPT

Se ejecutó BM25 sobre la tarea
`Significant-Gravitas__AutoGPT-4652`, utilizando el `base_commit`
`9150f32f8b8602395534795ddd2d930a1684e419`.

El corpus resultante contiene 741 chunks.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   0.0000 |    0.0000 | 0.0000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   0.0000 |    0.0000 | 0.0000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   0.0000 |    0.0000 | 0.0000 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

BM25 no recuperó contexto gold dentro de los primeros 20 resultados
para esta tarea. El resultado se conserva como parte del mini-piloto
sin extraer todavía conclusiones generales.

### Recuperación semántica sobre AutoGPT

Se ejecutó la recuperación semántica sobre la tarea
`Significant-Gravitas__AutoGPT-4652`.

El corpus contiene 741 chunks, cuyos embeddings fueron generados mediante
UniXcoder y almacenados en caché para su reutilización posterior.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   0.0000 |    0.0000 | 0.0000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   0.0000 |    0.0000 | 0.0000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   0.0000 |    0.0000 | 0.0000 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

La estrategia semántica no recuperó contexto gold dentro de los primeros
20 resultados para esta tarea. Al igual que en BM25, el resultado se
conserva como parte del mini-piloto sin extraer todavía conclusiones
generales.

### Comprobación de cobertura del gold en AutoGPT

Debido a que BM25 y la recuperación semántica obtuvieron métricas nulas
hasta K=20 en la tarea `Significant-Gravitas__AutoGPT-4652`, se comprobó
si el contexto gold estaba representado en el corpus generado por el
chunking.

El contexto gold contiene 89 líneas distintas en
`autogpt/memory/message_history.py`. De ellas, 82 están cubiertas por al
menos un chunk del corpus, lo que supone una cobertura máxima posible de
0,9213.

Las líneas 14-20 no están representadas por ningún chunk, mientras que
las regiones comprendidas entre las líneas 123-204 sí están completamente
cubiertas.

Por tanto, las métricas nulas obtenidas por BM25 y recuperación semántica
en K=5, K=10 y K=20 no pueden atribuirse únicamente a la ausencia del
contexto relevante en el corpus. La mayor parte del gold era recuperable,
pero no apareció entre los primeros 20 resultados de estas estrategias.

La ausencia de las líneas 14-20 es coherente con las limitaciones conocidas
del chunking estructural utilizado, que no genera chunks independientes
para imports o código a nivel de módulo.

**Evidencia:** `docs/screenshots/16-autogpt-gold-coverage.png`

### Recuperación BM25 sobre LangChain

Se ejecutó la estrategia BM25 sobre la tarea
`langchain-ai__langchain-6765`, correspondiente al repositorio
`langchain-ai/langchain` en el commit
`ba622764cb7ccf4667878289f959857348ef8c19`.

El corpus generado mediante el chunking estructural contiene 5.751 chunks.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   1.0000 |    0.3333 | 0.5000 |
| 5   | line  |   1.0000 |    0.0976 | 0.1778 |
| 10  | file  |   1.0000 |    0.1429 | 0.2500 |
| 10  | line  |   1.0000 |    0.0476 | 0.0909 |
| 20  | file  |   1.0000 |    0.0909 | 0.1667 |
| 20  | line  |   1.0000 |    0.0249 | 0.0486 |

BM25 recuperó todo el contexto gold ya en K=5, tanto a nivel de fichero
como de línea. Al aumentar K, la cobertura se mantuvo en 1.0000, mientras
que la precisión y el F1 disminuyeron debido a la incorporación de
resultados adicionales no pertenecientes al contexto gold.

Este resultado ilustra la utilidad de evaluar distintos valores de K:
aumentar el número de chunks recuperados no implica necesariamente una
selección más precisa del contexto relevante.

### Recuperación BM25 sobre scikit-learn

Se ejecutó la estrategia BM25 sobre la tarea
`scikit-learn__scikit-learn-25931`, correspondiente al repositorio
`scikit-learn/scikit-learn` en el commit
`e3d1f9ac39e4bf0f31430e779acc50fb05fe1b64`.

El corpus generado mediante el chunking estructural contiene 9.685 chunks.

| K   | Nivel | Coverage | Precision |     F1 |
| --- | ----- | -------: | --------: | -----: |
| 5   | file  |   0.0000 |    0.0000 | 0.0000 |
| 5   | line  |   0.0000 |    0.0000 | 0.0000 |
| 10  | file  |   0.0000 |    0.0000 | 0.0000 |
| 10  | line  |   0.0000 |    0.0000 | 0.0000 |
| 20  | file  |   0.0000 |    0.0000 | 0.0000 |
| 20  | line  |   0.0000 |    0.0000 | 0.0000 |

BM25 no recuperó contexto gold dentro de los primeros 20 resultados para
esta tarea. El resultado se conserva como parte del mini-piloto y no se
utiliza de forma aislada para extraer conclusiones generales sobre el
rendimiento de la estrategia.
