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
