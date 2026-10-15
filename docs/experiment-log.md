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

## Automatización del mini-piloto de recuperación

Se automatizó la ejecución conjunta de las tres estrategias de recuperación
evaluadas en el trabajo: BM25, recuperación semántica mediante UniXcoder y
recuperación híbrida mediante Reciprocal Rank Fusion (RRF).

El runner experimental reutiliza para cada tarea el mismo repositorio en el
`base_commit` indicado por ContextBench y el mismo corpus de chunks para las
tres estrategias. Los rankings obtenidos se evalúan para K=5, K=10 y K=20
a nivel de fichero y línea.

La ejecución automatizada se realizó sobre las cinco tareas seleccionadas
previamente para el mini-piloto:

- `django__django-12663`
- `Significant-Gravitas__AutoGPT-4652`
- `matplotlib__matplotlib-25479`
- `langchain-ai__langchain-6765`
- `scikit-learn__scikit-learn-25931`

La ejecución finalizó correctamente para las cinco tareas y generó 90 filas
de resultados:

5 tareas × 3 estrategias × 3 valores de K × 2 niveles de evaluación = 90.

Los resultados se almacenaron de forma estructurada en:

`results/retrieval_results.csv`

El fichero contiene, para cada combinación experimental, el identificador de
la tarea, la estrategia de recuperación, K, el nivel de evaluación y las
métricas de coverage, precision y F1.

La automatización no modifica las estrategias de recuperación ni las métricas
utilizadas previamente, sino que permite ejecutar de forma reproducible el
mismo procedimiento sobre múltiples tareas y reducir errores derivados de la
recopilación manual de resultados.

**Evidencia:** `docs/screenshots/17-mini-pilot-automated.png`

## Validación del pipeline de recuperación semántica

Durante el análisis del mini-piloto se observó que la recuperación semántica
mediante UniXcoder no recuperaba contexto gold dentro de Top-5, Top-10 ni
Top-20 para las cinco tareas seleccionadas. Antes de interpretar este
resultado como comportamiento del método, se realizaron comprobaciones
adicionales para descartar un fallo básico de implementación.

En la tarea `django__django-12663` se inspeccionó el ranking semántico completo.
Los seis ficheros gold estaban presentes en el ranking, aunque su primera
aparición se producía en posiciones alejadas del Top-20. La mejor posición
observada fue 654 y la más baja 4492.

Posteriormente se realizó una prueba de autorrecuperación utilizando como
consulta la misma representación textual de un chunk existente en el corpus.
El chunk seleccionado se encontraba aproximadamente en la mitad del corpus,
evitando seleccionar manualmente un caso favorable.

El chunk utilizado fue:

- Fichero: `tests/distinct_on_fields/tests.py`
- Símbolo: `DistinctOnTests.test_transform`
- Líneas: 101-109

El sistema recuperó el mismo chunk en la posición 1 con una similitud coseno
de 1.000000.

Estas comprobaciones indican que los embeddings almacenados mantienen una
correspondencia coherente con los chunks y que el pipeline semántico es capaz
de recuperar correctamente una consulta idéntica a una unidad indexada.
Por tanto, no se encontraron indicios de que los resultados nulos observados
en Top-5, Top-10 y Top-20 se deban a un fallo básico de generación,
almacenamiento o asociación de los embeddings.

Este diagnóstico no implica que UniXcoder sea incapaz de recuperar contexto
relevante en general, sino que, para las consultas y tareas analizadas en el
mini-piloto, los chunks pertenecientes a los ficheros gold no fueron
posicionados dentro de los valores de K evaluados.

**Evidencias:**

- `docs/screenshots/19-semantic-gold-rank-django.png`
- `docs/screenshots/20-semantic-self-retrieval.png`

## Resultados agregados del mini-piloto

Tras completar la ejecución automatizada de las cinco tareas del mini-piloto,
se calcularon macro-promedios de las métricas de recuperación. Cada tarea
contribuye con el mismo peso al promedio, independientemente del tamaño del
repositorio o de la cantidad de contexto gold.

Los resultados agregados fueron:

| Método        |   K | Nivel   | Coverage | Precision |     F1 |
| ------------- | --: | ------- | -------: | --------: | -----: |
| BM25          |   5 | fichero |   0.2333 |    0.1167 | 0.1400 |
| BM25          |   5 | línea   |   0.2096 |    0.0406 | 0.0487 |
| BM25          |  10 | fichero |   0.3333 |    0.0971 | 0.1379 |
| BM25          |  10 | línea   |   0.2407 |    0.0517 | 0.0595 |
| BM25          |  20 | fichero |   0.5000 |    0.1268 | 0.1921 |
| BM25          |  20 | línea   |   0.2844 |    0.0617 | 0.0775 |
| UniXcoder     |   5 | fichero |   0.0000 |    0.0000 | 0.0000 |
| UniXcoder     |   5 | línea   |   0.0000 |    0.0000 | 0.0000 |
| UniXcoder     |  10 | fichero |   0.0000 |    0.0000 | 0.0000 |
| UniXcoder     |  10 | línea   |   0.0000 |    0.0000 | 0.0000 |
| UniXcoder     |  20 | fichero |   0.0000 |    0.0000 | 0.0000 |
| UniXcoder     |  20 | línea   |   0.0000 |    0.0000 | 0.0000 |
| Híbrido (RRF) |   5 | fichero |   0.0333 |    0.0667 | 0.0444 |
| Híbrido (RRF) |   5 | línea   |   0.0096 |    0.0162 | 0.0120 |
| Híbrido (RRF) |  10 | fichero |   0.2333 |    0.0450 | 0.0649 |
| Híbrido (RRF) |  10 | línea   |   0.2096 |    0.0141 | 0.0194 |
| Híbrido (RRF) |  20 | fichero |   0.2333 |    0.0254 | 0.0411 |
| Híbrido (RRF) |  20 | línea   |   0.2096 |    0.0071 | 0.0114 |

En este mini-piloto, BM25 obtuvo los mayores macro-promedios de F1 tanto a
nivel de fichero como de línea. Su mejor resultado se obtuvo con K=20, con
un F1 de 0.1921 a nivel de fichero y 0.0775 a nivel de línea.

La estrategia semántica mediante UniXcoder no recuperó contexto gold dentro
de Top-5, Top-10 ni Top-20 en las cinco tareas seleccionadas. Las
comprobaciones adicionales realizadas sobre el pipeline semántico no
mostraron indicios de un fallo básico en la generación, almacenamiento o
asociación de los embeddings.

La estrategia híbrida mediante RRF produjo resultados distintos de cero,
pero no mejoró los macro-promedios obtenidos por BM25. Este comportamiento
muestra que la combinación de recuperación léxica y semántica no garantiza
por sí misma una mejora del ranking.

Estos resultados se consideran preliminares debido al reducido tamaño del
mini-piloto. Su finalidad es validar la infraestructura experimental,
detectar posibles problemas y comprobar el comportamiento de las estrategias
antes de ejecutar la muestra final. No se utilizan para concluir que BM25
sea superior de forma general.

A partir de estos resultados se congela la configuración principal de
recuperación para la siguiente fase experimental:

- Estrategias: BM25, UniXcoder y combinación híbrida mediante RRF.
- Mismo chunking para las tres estrategias.
- Consulta: `problem_statement` de ContextBench.
- K: 5, 10 y 20.
- Evaluación: nivel de fichero y nivel de línea.
- Métricas: coverage, precision y F1.
- Parámetro RRF: k=60.
- Profundidad de rankings utilizados para la fusión: 100.

La configuración no se modificará en función de qué estrategia obtenga
mejores o peores resultados. Solo se realizarán cambios si se identifica un
error de implementación que comprometa la validez del experimento.

**Evidencia:** `docs/screenshots/18-mini-pilot-macro-results.png`

**Resultados reproducibles:**

- `results/retrieval_results.csv`
- `results/retrieval_summary.csv`

## Definición de la muestra experimental final

Una vez validado el pipeline mediante el mini-piloto, se fija la muestra
objetivo para la evaluación final de las estrategias de recuperación.

La muestra estará formada por 50 tareas de ContextBench que cumplan los
siguientes criterios:

- Lenguaje: Python.
- Tamaño objetivo: 50 tareas.
- Selección reproducible mediante semilla fija `seed=42`.
- Máximo de 5 tareas por repositorio.
- Ningún repositorio podrá representar, por tanto, más del 10 % de la muestra.
- La selección se realizará antes de ejecutar y analizar los resultados
  finales de recuperación.
- Las tareas no se seleccionarán ni descartarán en función del rendimiento
  obtenido por BM25, UniXcoder o RRF.

El límite por repositorio se introduce para reducir la concentración de la
muestra en los proyectos con mayor representación dentro de ContextBench y
aumentar la diversidad de repositorios evaluados.

El tamaño de 50 tareas se establece como un compromiso entre diversidad de
la muestra, coste computacional y viabilidad temporal del experimento. No se
asume que este tamaño garantice representatividad estadística del conjunto
completo de ContextBench.

La selección obtenida mediante estas reglas quedará fijada antes de comenzar
la ejecución experimental final.

### Resultado de la selección de la muestra final

Se ejecutó el procedimiento de selección reproducible definido previamente
para obtener la muestra experimental final.

El resultado fue:

- Tareas Python disponibles en ContextBench: 512.
- Repositorios Python disponibles: 20.
- Tareas seleccionadas: 50.
- Repositorios representados: 20.
- Máximo observado de tareas por repositorio: 3.
- Máximo peso de un único repositorio en la muestra: 6 %.
- Semilla utilizada: `42`.
- Límite previamente establecido: máximo 5 tareas por repositorio.

La selección resultante presenta representación de los 20 repositorios Python
disponibles en ContextBench. Aunque el límite máximo establecido era de cinco
tareas por repositorio, el procedimiento de selección por rondas produjo una
distribución más equilibrada, con entre una y tres tareas por repositorio.

La lista exacta de tareas seleccionadas se almacena en
`results/final_tasks.csv`. Este fichero fija la muestra que se utilizará en
la evaluación final y evita realizar modificaciones posteriores en función
de los resultados obtenidos por las estrategias de recuperación.

**Evidencia:** `docs/screenshots/21-final-sample-selection.png`

### Estimación del coste computacional de la recuperación semántica

Antes de ejecutar la evaluación final se realizó una medición del coste de generación de embeddings con _UniXcoder_ sobre uno de los estados de repositorio incluidos en la muestra final.

La prueba se realizó sobre `scikit-learn/scikit-learn`, en el commit `586f4318ffcdfbd9a1093f35ad43e81983740b66`, utilizando la misma configuración semántica definida para el experimento final (`batch_size=8`).

Se procesaron 10.049 chunks en 4.231,79 segundos (1,18 horas), obteniendo una velocidad aproximada de 2,37 chunks por segundo, equivalentes a 142,48 chunks por minuto.

A partir de los 567.285 chunks pendientes inicialmente en la muestra final, esta velocidad supone una estimación lineal aproximada de 66,36 horas de cálculo. Tras generar durante el benchmark los embeddings correspondientes a este estado, quedan aproximadamente 557.236 chunks, con una proyección de 65,18 horas adicionales.

Esta estimación se utiliza únicamente para planificar la ejecución computacional. El tiempo real puede variar entre repositorios debido a diferencias en la longitud y contenido de los chunks.

**Evidencia:** `docs/screenshots/22-semantic-performance-benchmark.png`

### Finalización de la evaluación de recuperación

Se completó la evaluación final de las tres estrategias de recuperación sobre la muestra experimental de 50 tareas de ContextBench.

Para cada tarea se evaluaron BM25, recuperación semántica mediante _UniXcoder_ y recuperación híbrida mediante _Reciprocal Rank Fusion_ (RRF), utilizando K=5, K=10 y K=20 y métricas a nivel de fichero y línea.

La ejecución produjo 900 filas de resultados:

- 50 tareas.
- 3 estrategias de recuperación.
- 3 valores de K.
- 2 niveles de evaluación.

La validación posterior confirmó 50 identificadores de tarea únicos y 18 combinaciones de resultados para cada tarea. No se registraron fallos durante la ejecución final.

Por tanto, el conjunto de resultados de recuperación se considera completo y válido para iniciar el análisis agregado.

**Resultados:** `results/final_retrieval_results.csv`

**Evidencia:** `docs/screenshots/23-final-retrieval-complete.png`

### Resultados agregados de la evaluación final de recuperación

Tras completar la evaluación sobre las 50 tareas seleccionadas, se agregaron los
resultados mediante macro-promedio por tarea. De esta forma, cada tarea tiene el
mismo peso en el resultado agregado, independientemente de sus características.

Se evaluaron las tres estrategias de recuperación (BM25, UniXcoder y RRF) para
K=5, K=10 y K=20, tanto a nivel de fichero como de línea.

| Método    |   K | Nivel | Coverage | Precision |     F1 |
| --------- | --: | ----- | -------: | --------: | -----: |
| BM25      |   5 | file  |   0.4033 |    0.2337 | 0.2578 |
| BM25      |   5 | line  |   0.1740 |    0.1352 | 0.1332 |
| BM25      |  10 | file  |   0.4757 |    0.1911 | 0.2438 |
| BM25      |  10 | line  |   0.2381 |    0.0991 | 0.1228 |
| BM25      |  20 | file  |   0.5652 |    0.1307 | 0.1939 |
| BM25      |  20 | line  |   0.2733 |    0.0627 | 0.0912 |
| UniXcoder |   5 | file  |   0.2617 |    0.1480 | 0.1673 |
| UniXcoder |   5 | line  |   0.1065 |    0.0901 | 0.0880 |
| UniXcoder |  10 | file  |   0.3289 |    0.1216 | 0.1604 |
| UniXcoder |  10 | line  |   0.1547 |    0.0631 | 0.0784 |
| UniXcoder |  20 | file  |   0.4369 |    0.1024 | 0.1521 |
| UniXcoder |  20 | line  |   0.1868 |    0.0404 | 0.0598 |
| RRF       |   5 | file  |   0.3556 |    0.2337 | 0.2505 |
| RRF       |   5 | line  |   0.1483 |    0.1229 | 0.1190 |
| RRF       |  10 | file  |   0.4273 |    0.1741 | 0.2222 |
| RRF       |  10 | line  |   0.2015 |    0.0855 | 0.1084 |
| RRF       |  20 | file  |   0.5629 |    0.1225 | 0.1862 |
| RRF       |  20 | line  |   0.2546 |    0.0555 | 0.0841 |

La validación del fichero agregado confirmó que las 18 combinaciones
correspondientes a 3 métodos, 3 valores de K y 2 niveles de evaluación contienen
exactamente 50 tareas cada una.

Los resultados muestran que, en la muestra evaluada, BM25 obtiene los mayores
valores de F1 en todas las configuraciones analizadas. La recuperación semántica
mediante UniXcoder presenta resultados inferiores a BM25 en las métricas agregadas de la muestra evaluada, mientras que la estrategia híbrida RRF se aproxima a BM25 pero no lo supera en F1.

También se observa un patrón consistente al aumentar K: aumenta la cobertura del
contexto gold, mientras disminuyen la precisión y el F1. Este comportamiento
refleja el compromiso entre recuperar una mayor proporción del contexto relevante
y añadir una mayor cantidad de contexto no relevante.

Estos resultados describen exclusivamente la calidad de la etapa de recuperación.
La evaluación downstream permitirá analizar posteriormente si las diferencias
observadas en retrieval se traducen o no en diferencias en la capacidad del LLM
para resolver los issues.

**Resultados:** `results/final_retrieval_summary.csv`

**Evidencia:** `docs/screenshots/24-final-retrieval-summary.png`

#### Análisis de resultados por tarea

Como complemento a las métricas agregadas, se comparó el F1 de las tres
estrategias individualmente para cada tarea, manteniendo fijos K y el nivel de
evaluación. Las tareas en las que los tres métodos obtuvieron F1=0 se
contabilizaron por separado y los empates con F1>0 no se asignaron
arbitrariamente a ningún método.

|   K | Nivel | BM25 | UniXcoder | RRF | Empates | Todos F1=0 |
| --: | ----- | ---: | --------: | --: | ------: | ---------: |
|   5 | file  |   12 |         7 |  12 |      10 |          9 |
|   5 | line  |   13 |         5 |   9 |       0 |         23 |
|  10 | file  |   17 |        12 |   8 |       5 |          8 |
|  10 | line  |   14 |         8 |  12 |       0 |         16 |
|  20 | file  |   17 |        12 |  10 |       5 |          6 |
|  20 | line  |   19 |         8 |   9 |       0 |         14 |

BM25 es el método con mayor número de victorias individuales en cinco de las
seis configuraciones y empata con RRF en K=5 a nivel de fichero. Esto es
coherente con su mejor rendimiento agregado en F1.

No obstante, UniXcoder y RRF obtienen el mejor F1 en determinados subconjuntos
de tareas. Por tanto, los resultados no indican que una estrategia domine
necesariamente en todos los issues, sino que existen diferencias de
comportamiento entre tareas.

También se observa que el número de tareas en las que los tres métodos obtienen
F1=0 disminuye al aumentar K. A nivel de línea pasa de 23 tareas con K=5 a 14
con K=20, lo que es consistente con el aumento de cobertura observado en los
resultados agregados.

#### Cierre de la fase de recuperación

El análisis por tarea confirma que el mejor rendimiento agregado de BM25 no
implica que esta estrategia sea superior en todos los issues. Existen tareas
concretas en las que UniXcoder o RRF obtienen un F1 superior.

Como ejemplos ilustrativos para K=10 a nivel de línea:

- `keras-team__keras-18871`: BM25 obtiene el mayor F1 (0.6880), frente a
  UniXcoder (0.5090) y RRF (0.5710).
- `sympy__sympy-16886`: UniXcoder obtiene el mayor F1 (0.4363), frente a
  BM25 (0.2181) y RRF (0.2847).
- `sphinx-doc__sphinx-9461`: RRF obtiene F1=0.1880, mientras que BM25 y
  UniXcoder obtienen F1=0.

Estos casos se utilizan únicamente como ejemplos ilustrativos de la variabilidad
observada entre tareas y no como evidencia adicional seleccionada para modificar
las conclusiones agregadas.

En consecuencia, en la muestra evaluada de 50 tareas, BM25 presenta el mejor
rendimiento agregado en F1, pero ninguna de las estrategias puede considerarse
dominante para todos los issues.

Con este análisis se considera cerrada la fase experimental de recuperación.
La siguiente fase evaluará si las diferencias observadas en la calidad del
contexto recuperado se traducen en diferencias en la capacidad de un LLM para
resolver los issues.

#### Inspección cualitativa de rankings

Como análisis complementario, se inspeccionaron los rankings de tres tareas
ilustrativas para K=10 a nivel de línea, sin modificar la configuración
experimental ni las estrategias de recuperación.

En `keras-team__keras-18871`, BM25 obtuvo el mayor F1 a nivel de línea
(0.6880). En su Top-10 aparecieron tres chunks con solapamiento con el contexto
gold, frente a dos en UniXcoder. RRF también recuperó tres chunks con
solapamiento, aunque obtuvo un F1 inferior a BM25.

En `sympy__sympy-16886`, UniXcoder obtuvo el mayor F1 (0.4363), aunque los tres
métodos recuperaron dos chunks con solapamiento con el gold dentro del Top-10.
Esto muestra que el número de chunks con solapamiento no explica por sí solo el
resultado: los métodos recuperan conjuntos de chunks con diferentes rangos de
líneas, lo que afecta a la precisión y al F1 a nivel de línea.

El caso `sphinx-doc__sphinx-9461` ilustra el comportamiento de la fusión RRF.
El chunk `Documenter.filter_members`, situado en las líneas 669-818 de
`sphinx/ext/autodoc/__init__.py`, ocupaba la posición 78 en BM25 y la posición
39 en UniXcoder, por lo que no aparecía en el Top-10 de ninguno de los dos
métodos. Al combinar ambos rankings mediante RRF, el chunk ascendió hasta la
posición 6 y pasó a formar parte del contexto recuperado para K=10. Esto explica
que RRF obtuviera F1=0.1880 en esta tarea mientras BM25 y UniXcoder obtuvieron
F1=0.

Esta inspección se utiliza únicamente como análisis cualitativo ilustrativo de
los resultados ya obtenidos y no se empleó para modificar parámetros,
seleccionar nuevas configuraciones ni alterar las conclusiones agregadas.

**Evidencia:**

- `docs/screenshots/25-rrf-ranking-inspection-sphinx.png`
- `docs/screenshots/26-rrf-gold-ranks-sphinx.png`

#### Auditoría de las métricas de recuperación

Antes de iniciar la evaluación downstream se realizó una revisión adicional de
la implementación de las métricas de recuperación.

Se ampliaron los tests unitarios para comprobar ocho casos, incluyendo
coincidencia completa, ausencia y solapamiento parcial de líneas, múltiples
ficheros, fichero incorrecto e intervalos solapados tanto en la predicción como
en el contexto gold. Los ocho tests finalizaron correctamente.

También se verificaron las 50 tareas de la muestra experimental para comprobar
la validez del contexto gold. Ninguna tarea presentó un `gold_context` vacío ni
intervalos con límites de línea inválidos.

Estas comprobaciones no modificaron la implementación de las métricas ni los
resultados experimentales, sino que se realizaron como validación adicional de
su corrección antes de iniciar la fase downstream.

**Evidencia:** `docs/screenshots/27-retrieval-metrics-audit.png`

#### Auditoría del pipeline de recuperación

Antes de iniciar la evaluación downstream se revisó adicionalmente el pipeline
de recuperación para comprobar la comparabilidad entre estrategias y descartar
posibles filtraciones de información del contexto gold.

La inspección del pipeline confirmó que BM25 y UniXcoder utilizan exclusivamente
el `problem_statement` como consulta y reciben el mismo corpus de chunks,
construido a partir del repositorio en el `base_commit` correspondiente.
El `gold_context` se utiliza únicamente después de generar los rankings para
calcular las métricas, mientras que `patch` y `test_patch` no intervienen en la
recuperación.

También se revisó la implementación de RRF. La fusión utiliza únicamente las
posiciones de los resultados de BM25 y UniXcoder, con `rrf_k=60` y una
profundidad de fusión de 100 resultados por método.

Como comprobación adicional de la caché semántica, se verificó el determinismo
del chunking sobre `sphinx-doc__sphinx`: dos ejecuciones independientes
produjeron 6071 chunks en exactamente el mismo orden, sin diferencias entre
posiciones.

Finalmente, se validaron las cachés semánticas correspondientes a las 50 tareas
de la muestra final. Las 50 cachés utilizadas presentaron metadatos coherentes
para repositorio, commit, modelo, modo de encoding y longitud máxima, y el
número declarado de chunks coincidió con el número de embeddings almacenados.
No se detectaron errores en esta comprobación.

La caché semántica no almacena actualmente una huella de la identidad y el orden
de los chunks, por lo que esta validación podría reforzarse en futuras versiones.
No obstante, las comprobaciones de determinismo, metadatos y autorrecuperación
realizadas no proporcionaron indicios de una desalineación entre chunks y
embeddings en los experimentos ejecutados.

**Evidencia:** `docs/screenshots/28-semantic-cache-audit.png`

#### Auditoría de la muestra final y de la agregación

Antes de iniciar la evaluación downstream se realizó una comprobación adicional
de la integridad de la muestra experimental y de los resultados finales de
recuperación.

La muestra final contiene 50 tareas únicas pertenecientes a 20 repositorios,
sin identificadores duplicados. El máximo observado fue de tres tareas por
repositorio, equivalente al 6 % de la muestra.

Los resultados finales contienen exactamente las mismas 50 tareas seleccionadas,
sin tareas ausentes ni adicionales. Cada tarea presenta las 18 combinaciones
experimentales previstas (3 métodos × 3 valores de K × 2 niveles), sin
combinaciones duplicadas, para un total de 900 filas.

También se recalcularon independientemente los macro-promedios de coverage,
precision y F1 directamente a partir de las 900 filas originales. Las 18
combinaciones recalculadas coincidieron numéricamente con
`results/final_retrieval_summary.csv`, salvo diferencias del orden de 10^-17
atribuibles a la representación en coma flotante.

El recálculo confirmó además que BM25 obtiene el mayor F1 agregado en las seis
configuraciones formadas por K={5,10,20} y los niveles de fichero y línea.

Estas comprobaciones no modificaron los resultados experimentales y se
realizaron para validar de forma independiente la integridad de la muestra y
el procedimiento de agregación.

**Evidencias:**

- `docs/screenshots/29-final-sample-results-audit.png`
- `docs/screenshots/30-final-aggregation-audit.png`

### Preparación de la evaluación downstream con LLM

Se inició la preparación de la fase downstream, cuyo objetivo es evaluar si las diferencias observadas entre las estrategias de recuperación se traducen en diferencias en la capacidad de un LLM para resolver los issues.

Como requisito de diseño, el LLM recibirá únicamente el `problem_statement` y el contexto proporcionado por la estrategia de recuperación correspondiente. El `gold_context`, el patch de referencia y el `test_patch` no se utilizarán como entrada del modelo, evitando así fuga de información (_data leakage_).

Se configuró el SDK `google-genai` (versión 2.30.0) y se validó correctamente el acceso a Gemini Developer API desde el entorno experimental.

Como candidato inicial se está evaluando `gemini-3.5-flash-lite`. Se comprobó mediante una llamada mínima que el modelo puede generar respuestas correctamente. Para el proyecto `tfm-context-retrieval`, Google AI Studio mostró un límite gratuito para generación de texto de 15 RPM, 250K TPM y 500 RPD, suficiente en número de peticiones para un diseño potencial de 50 tareas × 3 estrategias de recuperación (150 generaciones).

La selección del modelo todavía no se considera congelada. Antes se realizará un piloto con un issue real de ContextBench para comprobar su capacidad para generar un patch utilizable.

**Estado:** configuración técnica validada; modelo downstream todavía provisional.

**Evidencia:**

- docs/screenshots/32-gemini-free-tier-limits.png

### Evaluación de los patches generados

Para evaluar si los _patches_ generados por el LLM resuelven realmente cada _issue_, se utilizará el _harness_ de SWE-bench.

> Utilizamos el _harness_ de SWE-bench para evaluar de forma reproducible si los _patches_ generados por el LLM resuelven cada instancia, evitando definir manualmente un procedimiento de _testing_ diferente para cada repositorio.

### Primer piloto downstream validado

Se validó el pipeline downstream sobre la instancia `pytest-dev__pytest-5809`, primera tarea de la muestra final, utilizando recuperación BM25 con Top-K=10 y `gemini-3.5-flash-lite` como modelo candidato durante el piloto técnico.

El flujo evaluado fue:

`issue → recuperación BM25 Top-10 → prompt con contexto recuperado → generación de patch → aplicación del patch → evaluación mediante SWE-bench`.

El patch generado fue aplicado correctamente por el harness (`patch_successfully_applied=True`) y el grader oficial de SWE-bench clasificó la instancia como resuelta (`resolved=True`, `infra_failure=False`).

El test `FAIL_TO_PASS` fue resuelto correctamente:

- `testing/test_pastebin.py::TestPaste::test_create_new_paste`

Además, los tres tests `PASS_TO_PASS` continuaron pasando, sin introducir regresiones en los tests controlados por la instancia.

Este resultado valida técnicamente el pipeline completo para una instancia piloto. No se utiliza para modificar la configuración experimental ni permite extraer conclusiones comparativas entre las estrategias de recuperación.

Debido a incompatibilidades de infraestructura entre SWE-bench 5.0.2, Windows y Podman, la ejecución de los tests y la generación del informe final tuvieron que separarse: los tests se ejecutaron mediante el harness y el informe se regeneró posteriormente mediante `rewrite_reports=True` a partir del `test_output.txt` producido por la misma ejecución.

**Evidencia:** `docs/screenshots/33-first-downstream-pass.png`

### Validación del registro de consumo de tokens

Se comprobó que la API de Gemini proporciona metadatos de uso para cada generación, permitiendo registrar el consumo real de tokens durante la evaluación downstream.

En una ejecución piloto de `pytest-dev__pytest-5809` utilizando BM25 con K=10 y `gemini-3.5-flash-lite`, la API reportó:

- tokens de entrada: 3163;
- tokens de salida: 330;
- tokens de razonamiento reportados: ninguno;
- tokens totales: 3493.

Esta información se utilizará como dato auxiliar durante la evaluación downstream para controlar el consumo de la API y analizar el volumen de contexto procesado por cada estrategia. No se utilizará como métrica principal para determinar la calidad de las estrategias de recuperación.

**Evidencia:** `docs/screenshots/34-downstream-token-usage.png`

### Congelación del protocolo de evaluación downstream

Tras validar técnicamente el pipeline de generación y el registro de artefactos, se congela la configuración que se utilizará en la evaluación downstream.

La configuración fijada es:

- estrategias de recuperación: BM25, UniXcoder y RRF;
- muestra: las 50 tareas previamente seleccionadas y congeladas;
- K: 10 chunks recuperados por condición;
- LLM: `gemini-3.5-flash-lite`;
- máximo de tokens de salida: 4096;
- nivel de razonamiento: `minimal`;
- una única generación por condición (Pass@1);
- misma plantilla de prompt para las tres estrategias;
- mismo procedimiento de aplicación y evaluación mediante SWE-bench.

No se fijan explícitamente `temperature`, `top_p` ni `top_k` de generación, utilizándose el comportamiento por defecto del modelo.

El valor K=10 se selecciona como punto intermedio entre K=5, K=10 y K=20, buscando un compromiso entre cantidad de contexto y ruido. No se selecciona retrospectivamente en función de la estrategia que obtuvo mejores resultados de retrieval.

`gemini-3.5-flash-lite` se selecciona por su disponibilidad y viabilidad para ejecutar el volumen previsto de generaciones, y no por el resultado obtenido en la primera tarea piloto.

Para cada generación se conservarán como artefactos experimentales:

- el prompt exacto enviado al modelo;
- el patch generado;
- la configuración utilizada;
- los tokens de entrada;
- los tokens de salida;
- los tokens de razonamiento reportados;
- los tokens totales;
- posteriormente, el resultado de evaluación mediante SWE-bench.

Los prompts contienen únicamente el `problem_statement` y los chunks proporcionados por la estrategia de recuperación. No se proporciona al LLM `gold_context`, el patch de referencia ni `test_patch`.

Los errores de infraestructura o del proveedor se distinguirán de los fallos de resolución. Un patch generado con formato inválido o no aplicable se considerará un resultado de la generación y no se regenerará automáticamente, manteniendo una única generación por condición.

Esta configuración se congela antes de ejecutar la evaluación downstream comparativa para evitar modificar el protocolo en función de los resultados posteriores.

## Validación de la capa reutilizable de generación downstream

Se ha refactorizado el pipeline downstream para separar la recuperación de contexto y la generación mediante LLM en componentes reutilizables.

La capa de recuperación fue validada para las tres estrategias experimentales:

- BM25;
- UniXcoder;
- RRF.

En los tres casos se utiliza `K=10` como contexto proporcionado al LLM. Para RRF se mantiene una profundidad de fusión de 100 resultados, coherente con el experimento de recuperación previo. La recuperación semántica reutiliza las cachés de embeddings generadas durante dicho experimento.

La configuración de generación queda fijada en:

- modelo: `gemini-3.5-flash-lite`;
- `K=10`;
- `max_output_tokens=4096`;
- `thinking_level="minimal"`;
- una única generación válida por condición (Pass@1).

Se implementó además una política de reintentos controlados para errores temporales del proveedor. Los errores HTTP 429 y 503 pueden reintentarse hasta un máximo de tres intentos, mientras que los errores no considerados temporales se propagan sin reintento. Esta política fue validada mediante pruebas simuladas sin consumo de API.

Posteriormente se realizó una generación real de validación para la tarea `pytest-dev__pytest-5809` utilizando BM25 Top-10.

El consumo registrado fue:

- tokens de entrada: 3163;
- tokens de salida: 330;
- tokens de razonamiento: 0;
- tokens totales: 3493.

El patch generado se almacenó junto con el prompt y los metadatos de la generación. La comprobación mediante `git apply --check` sobre el `base_commit` correspondiente finalizó correctamente, por lo que el patch es aplicable. Este resultado no implica todavía que la incidencia esté resuelta; la resolución deberá determinarse posteriormente mediante la evaluación con SWE-bench.

**Evidencia:** `docs/screenshots/35-downstream-refactored-generation.png`

## Validación de la evaluación downstream reutilizable

Se implementó una capa reutilizable de evaluación downstream para evaluar un patch generado para una tarea concreta mediante el harness oficial de SWE-bench.

La evaluación distingue cuatro estados:

- `resolved`: SWE-bench determina que el patch resuelve la instancia.
- `not_resolved`: la evaluación termina correctamente, pero el patch no resuelve la instancia.
- `invalid_patch`: el patch generado no puede aplicarse sobre el `base_commit`.
- `infrastructure_error`: no puede obtenerse un resultado experimental válido debido a un fallo de infraestructura.

Antes de ejecutar SWE-bench se comprueba la aplicabilidad del patch mediante `git apply --check`. Un patch no aplicable se considera un resultado del modelo y no provoca una nueva generación bajo el protocolo Pass@1.

Durante la validación en Windows + Podman se reprodujo la desconexión ya observada entre Docker SDK y la API compatible de Podman después de finalizar los tests. Para evitar clasificar este caso como fallo experimental, la capa de evaluación comprueba si SWE-bench ha producido un `test_output.txt` completo mediante el marcador `>>>>> Test Exit Code:`. Si la salida es completa, se ejecuta únicamente el grader oficial de SWE-bench mediante `rewrite_reports=True`. Una salida inexistente o incompleta continúa clasificándose como `infrastructure_error`.

La validación se realizó sobre `pytest-dev__pytest-5809` con el contexto recuperado mediante BM25 en K=10. La ejecución automática recuperó correctamente el informe oficial de SWE-bench y obtuvo:

- `status = resolved`
- `resolved = True`
- `infrastructure_failure = False`

Este resultado valida el mecanismo de evaluación individual y su recuperación controlada ante la desconexión posterior a la ejecución de tests. No constituye todavía un resultado comparativo entre estrategias de recuperación.

**Evidencia:** `docs/screenshots/37-downstream-automatic-evaluation-recovery.png`
