# Preguntas del TFM

## Preguntas de defensa — Recuperación de contexto y BM25

### ¿Cuál es el problema que intenta resolver tu TFM?

Un agente necesita seleccionar contexto relevante de un repositorio grande. Quieres estudiar qué estrategia de recuperación le proporciona mejor contexto y si eso ayuda después al LLM a resolver el issue.

### ¿Qué es ContextBench y por qué lo utilizas?

Es el benchmark que usamos para disponer de issues reales y de un contexto gold con el que comparar lo recuperado.

### ¿Qué significa “gold context”?

Es el contexto de referencia que el benchmark considera relevante para la tarea. Lo utilizamos para evaluar lo que recupera nuestro sistema.

### ¿Por qué haces chunking?

Porque no queremos entregar el repositorio completo al recuperador. Lo dividimos en unidades manejables de código que puedan ser buscadas y ordenadas.

### ¿Qué es un chunk en tu experimento?

Principalmente una función o método de Python, con fichero, símbolo, líneas y código.

### ¿Por qué usaste AST para crear los chunks?

Porque permite dividir el código según su estructura sintáctica, en lugar de cortar arbitrariamente cada N caracteres o líneas.

### ¿Qué es BM25?

Un método de recuperación léxica: puntúa los chunks según la coincidencia y relevancia de términos respecto al texto del issue. No “entiende” semánticamente el código como un embedding.

### ¿Qué le das como consulta a BM25?

El problem_statement del issue.

### ¿Qué texto indexas de cada chunk?

En nuestro baseline: file_path + symbol + code.

### ¿Qué significa Top-K?

Los K chunks con mayor puntuación devueltos por el recuperador. Estamos evaluando K=5, 10 y 20.

### ¿Cómo sabes si BM25 lo ha hecho bien?

Comparamos el contexto recuperado con el contexto gold mediante métricas a diferentes granularidades.

### ¿Qué significa coverage?

Qué proporción del contexto gold hemos conseguido recuperar.

### ¿Qué significa precision?

Qué proporción de lo que hemos recuperado corresponde al gold.

### ¿Por qué al aumentar K puede subir coverage pero bajar precision?

Porque recuperamos más contexto y tenemos más posibilidades de cubrir el gold, pero también podemos introducir más contexto irrelevante.

### ¿Qué significa file coverage = 1 y line coverage = 0?

Hemos encontrado el fichero correcto, pero no la región correcta dentro de ese fichero. Esto ya nos ocurrió en el piloto.

### ¿Qué es la evaluación por símbolos?

Comprueba si recuperamos unidades de código relevantes, como funciones o clases, no solo el fichero o las líneas exactas. Para Python, ContextBench considera funciones, clases y funciones async como definiciones. Texto pegado

### ¿Por qué no utilizas solo la métrica por líneas?

Porque las distintas granularidades cuentan cosas diferentes. Por ejemplo, un span gold puede incluir líneas en blanco o código entre definiciones; fichero, símbolo y línea ofrecen perspectivas complementarias.

### ¿Por qué empiezas por BM25?

Porque proporciona un baseline léxico sencillo y reproducible que después podremos comparar con recuperación semántica e híbrida.

### ¿Por qué mantienes el mismo chunking para BM25, semántico e híbrido?

Para aislar la variable que queremos estudiar: la estrategia de recuperación. Si cambiásemos también el chunking, no sabríamos qué cambio produjo la diferencia.

### ¿Un mejor retrieval implica necesariamente que el LLM resolverá mejor el issue?

No necesariamente. Precisamente una de las ideas importantes del TFM es comprobar la relación entre calidad del contexto recuperado y capacidad posterior del LLM para resolver el problema.

### Explíqueme con un ejemplo un resultado obtenido en su experimento.

En el primer issue, BM25 recuperó correctamente astropy/modeling/separable.py, por lo que obtuvo cobertura perfecta a nivel de fichero. Sin embargo, los primeros chunks recuperados pertenecían a otras zonas del fichero y no solapaban las líneas gold. Por eso la cobertura a nivel de líneas fue cero. Esto muestra que encontrar el fichero correcto no implica necesariamente recuperar el contexto concreto necesario para resolver el problema.

### ¿Qué es un chunk en nuestro experimento y por qué no recuperamos el repositorio entero de golpe?

Un **chunk** es una unidad manejable de código en la que dividimos el repositorio para poder indexarlo, buscarlo y ordenarlo por relevancia.

En nuestro experimento, el chunking está basado principalmente en funciones y métodos de Python. Cada chunk conserva información como:

- repositorio
- fichero
- símbolo
- línea inicial
- línea final
- código fuente

No tratamos el repositorio completo como una única unidad porque necesitamos que el recuperador pueda identificar qué partes concretas del código son más relevantes para resolver una issue.

De esta forma, ante una issue, el recuperador puede ordenar los chunks del repositorio por relevancia y seleccionar los mejores.

### En el piloto BM25 obtuvo `file coverage = 1`, `symbol coverage = 0` y `line coverage = 0`. ¿Qué significa?

Significa que BM25 consiguió recuperar el **fichero correcto**, pero no recuperó los **símbolos ni las líneas concretas** consideradas relevantes por el contexto gold de ContextBench.

En nuestro caso, BM25 posicionó muy bien `astropy/modeling/separable.py`, por lo que obtuvo una cobertura de fichero de 1.

Sin embargo, dentro de ese fichero recuperó funciones como `separability_matrix` e `is_separable`, mientras que el contexto gold correspondía a otras funciones y zonas del fichero.

Por eso:

- `file coverage = 1`: encontramos el fichero correcto.
- `symbol coverage = 0`: no encontramos las funciones/clases gold.
- `line coverage = 0`: los chunks recuperados no solapan con las líneas gold.

Este resultado demuestra que **encontrar el fichero correcto no implica necesariamente recuperar el contexto concreto necesario para resolver el problema**.

### ¿Por qué evaluamos K=5, K=10 y K=20 en vez de utilizar solamente Top-5?

K indica cuántos de los chunks mejor posicionados por el recuperador consideramos en la evaluación.

Por ejemplo:

- K=5 → evaluamos los 5 chunks mejor posicionados.
- K=10 → evaluamos los 10 mejores.
- K=20 → evaluamos los 20 mejores.

Utilizamos distintos valores de K para estudiar cómo cambia la calidad de la recuperación cuando permitimos recuperar más contexto.

Aumentar K puede incrementar la posibilidad de encontrar contexto relevante, pero también puede introducir más contexto irrelevante y reducir la precisión.

Por tanto, evaluar varios valores de K permite analizar ese equilibrio entre **cobertura y precisión** en lugar de asumir de antemano un único valor como el mejor.

### BM25 ha obtenido 0 en cobertura de símbolos y líneas. ¿Podemos concluir que BM25 es un mal método para este problema?

No.

Este resultado procede únicamente de una **tarea piloto**, por lo que no podemos extraer conclusiones generales sobre el rendimiento de BM25.

Lo que podemos afirmar es que, para esta tarea concreta, BM25 consiguió localizar el fichero correcto pero no recuperó los símbolos ni las líneas del contexto gold dentro de los valores de K evaluados.

Para comparar correctamente BM25 con la recuperación semántica y la recuperación híbrida necesitamos repetir el experimento sobre una muestra mayor de tareas y mantener constantes el resto de variables experimentales.

El objetivo del experimento no es demostrar de antemano que un método es mejor que otro, sino **medir y comparar su comportamiento bajo las mismas condiciones**.

### ¿Cuál es la diferencia fundamental entre BM25 y la recuperación semántica?

BM25 es una estrategia de recuperación léxica que prioriza los chunks según la coincidencia y relevancia de los términos de la consulta. La recuperación semántica, en cambio, utiliza representaciones vectoriales para recuperar código relacionado por su significado, aunque no utilice exactamente los mismos términos que aparecen en la consulta.

### ¿Qué es un embedding?

Un embedding es una representación numérica o vectorial de un contenido, como un texto o un fragmento de código. En este trabajo se generan embeddings tanto para la consulta como para los chunks de código. La similitud entre estos vectores permite estimar qué chunks están semánticamente más relacionados con el problema planteado.

### ¿Por qué no es necesario generar de nuevo los embeddings de todos los chunks para cada consulta?

Los embeddings de los chunks pueden calcularse una vez y almacenarse. Para una nueva consulta sobre el mismo estado del repositorio únicamente es necesario generar el embedding de la consulta y compararlo con los embeddings previamente calculados. Esto permite reutilizar el trabajo computacional realizado.

### ¿Por qué se utiliza el mismo chunking para BM25 y para la recuperación semántica?

Se utiliza el mismo chunking para controlar las variables del experimento. Si cada estrategia utilizara una división diferente del código, sería difícil determinar si las diferencias observadas se deben al método de recuperación o al propio chunking. Mantener las mismas unidades de recuperación permite realizar una comparación más controlada entre las estrategias.

### Si la recuperación semántica obtiene mejores métricas de recuperación que BM25, ¿podemos concluir que es mejor para resolver issues con un LLM?

No necesariamente. Una mayor calidad de recuperación no implica automáticamente una mayor capacidad del LLM para resolver correctamente el issue. Por este motivo, el trabajo evalúa de forma separada la calidad del contexto recuperado y el resultado posterior del LLM al intentar resolver el problema. Uno de los objetivos es precisamente analizar la relación entre ambas etapas.

### ¿Qué hace UniXcoder con los chunks del repositorio?

UniXcoder transforma cada chunk de código en una representación vectorial o embedding. En nuestro experimento, cada embedding tiene 768 dimensiones.

Estos embeddings permiten representar numéricamente los chunks para posteriormente compararlos con el embedding generado a partir del issue.

### ¿Cómo se realiza una consulta en la recuperación semántica?

El texto del issue no se compara directamente con los embeddings de los chunks. Primero, el issue se procesa con el mismo modelo de embeddings, UniXcoder, para obtener su propia representación vectorial.

Después se calcula la similitud entre el embedding del issue y los embeddings de los chunks del repositorio. Los chunks se ordenan según esta similitud y se seleccionan los primeros resultados del ranking, utilizando en el experimento Top-5, Top-10 y Top-20.

### ¿Por qué pueden reutilizarse los embeddings de los chunks?

Los embeddings de los chunks no dependen del issue concreto que se esté consultando. Por ello, pueden generarse una vez, almacenarse y reutilizarse para diferentes consultas sobre el mismo estado del repositorio.

Para cada nuevo issue únicamente es necesario generar el embedding de la consulta y compararlo con los embeddings previamente almacenados.

### ¿Cuándo sería necesario regenerar los embeddings del corpus?

Los embeddings deben regenerarse cuando cambie alguna de las condiciones que determinan su representación, por ejemplo:

- el estado del código o `base_commit` evaluado;
- el chunking o la representación textual de los chunks;
- el modelo utilizado para generar los embeddings;
- el procedimiento de codificación utilizado para generar los vectores.

Mientras estas condiciones permanezcan constantes, los embeddings del corpus pueden reutilizarse.

### ¿Es necesario regenerar los embeddings si se cambia el LLM que intenta resolver el issue?

No. Es importante distinguir entre el modelo utilizado para generar embeddings y el LLM utilizado posteriormente para intentar resolver el issue.

UniXcoder se utiliza durante la etapa de recuperación para representar el issue y los chunks mediante embeddings. El LLM interviene posteriormente, cuando recibe el issue y el contexto recuperado e intenta generar una solución.

Por tanto, cambiar el LLM encargado de resolver el issue no obliga a regenerar los embeddings del corpus.

### ¿Por qué hay que utilizar el mismo modelo de embeddings para el issue y para los chunks?

Los embeddings del issue y de los chunks deben pertenecer al mismo espacio vectorial para que su similitud pueda compararse de forma coherente.

Por ello, si los embeddings de los chunks se generan con UniXcoder, el embedding del issue también debe generarse con UniXcoder y con el mismo procedimiento de codificación.

Si se sustituyera UniXcoder por otro modelo de embeddings, sería necesario regenerar tanto las representaciones del corpus como las de las consultas.

### ¿Por qué se utiliza el mismo chunking para BM25 y para la recuperación semántica?

Se utiliza el mismo chunking para controlar las variables del experimento.

Si BM25 y la recuperación semántica utilizaran divisiones diferentes del repositorio, no podríamos determinar con claridad si las diferencias observadas se deben a la estrategia de recuperación o al propio chunking.

Mantener las mismas unidades de recuperación permite atribuir las diferencias principalmente al método de recuperación utilizado.

### ¿Recuperar el fichero correcto significa que se ha recuperado correctamente el contexto?

No necesariamente. Una estrategia puede recuperar un chunk perteneciente al fichero correcto pero que no contenga las líneas relevantes para resolver el issue.

Por este motivo se evalúa la recuperación a dos niveles:

- fichero, como granularidad más gruesa;
- líneas, como granularidad más fina.

Esto permite distinguir entre localizar correctamente la zona general del repositorio y recuperar realmente el contexto relevante indicado por el gold de ContextBench.

### Si UniXcoder es más sofisticado que BM25, ¿por qué no asumir directamente que la recuperación semántica será mejor?

Una mayor sofisticación del método no garantiza un mejor resultado para la tarea evaluada. Precisamente uno de los objetivos del experimento es medir empíricamente el comportamiento de las distintas estrategias de recuperación.

Por ello se comparan BM25, recuperación semántica y recuperación híbrida utilizando las mismas tareas, los mismos chunks y las mismas métricas.

### Si una estrategia obtiene mejores métricas de recuperación, ¿significa que el LLM resolverá mejor los issues?

No necesariamente. Una mejor recuperación del contexto no implica automáticamente que el LLM sea capaz de generar una solución correcta.

Por este motivo el trabajo separa dos etapas de evaluación:

1. la calidad del contexto recuperado;
2. la capacidad posterior del LLM para resolver el issue utilizando dicho contexto.

Esto permite estudiar no solo qué estrategia recupera mejor el contexto gold, sino también la relación entre la calidad de recuperación y el resultado final del LLM.

## Preguntas de repaso — Recuperación híbrida con RRF

### ¿Por qué utilizamos RRF en lugar de sumar directamente los scores de BM25 y UniXcoder?

Los scores de BM25 y de la recuperación semántica representan cosas diferentes
y se encuentran en escalas distintas, por lo que no tiene sentido sumarlos
directamente.

RRF (Reciprocal Rank Fusion) evita este problema utilizando la posición que
ocupa cada chunk en los rankings generados por cada método, en lugar de utilizar
sus scores originales.

### ¿Qué ocurre si un chunk aparece en posiciones altas tanto en BM25 como en la recuperación semántica?

El chunk recibe contribución de ambos rankings y, por tanto, normalmente obtiene
una puntuación RRF mayor.

Esto permite que RRF favorezca chunks sobre los que existe cierto consenso entre
la recuperación léxica y la recuperación semántica.

### ¿Qué diferencia existe entre `FUSION_DEPTH = 100` y los valores `K = 5, 10, 20`?

`FUSION_DEPTH = 100` indica cuántos resultados de cada ranking individual
utilizamos como entrada para construir el ranking híbrido mediante RRF.

En nuestro caso:

- los primeros 100 resultados de BM25;
- los primeros 100 resultados de UniXcoder.

En cambio, `K = 5, 10, 20` indica cuántos resultados del ranking resultante
evaluamos contra el contexto gold de ContextBench.

Por tanto:

- `FUSION_DEPTH` pertenece al proceso de fusión;
- `K` pertenece a los puntos de corte utilizados para evaluar la recuperación.

En una fase posterior, los chunks recuperados podrán utilizarse también como
contexto proporcionado al LLM, pero actualmente estamos evaluando primero la
calidad de la recuperación de forma independiente.

### El híbrido ha obtenido peores métricas que el método semántico en K=10 para el issue piloto. ¿Deberíamos modificar RRF hasta conseguir que mejore?

No.

El objetivo del experimento es comparar las estrategias de recuperación y
observar empíricamente su comportamiento, no modificar los métodos hasta
conseguir que una estrategia determinada sea la mejor.

Modificar los parámetros después de observar el resultado de una única tarea
podría introducir un ajuste específico al piloto y reducir la validez de la
comparación.

Por ello mantenemos fija la configuración y evaluaremos las estrategias sobre
una muestra mayor de tareas antes de extraer conclusiones.

### ¿Qué significa obtener `file coverage = 1` pero `line coverage = 0`?

Significa que la estrategia de recuperación ha localizado el fichero que
contiene el contexto relevante, pero los chunks recuperados no solapan con las
líneas identificadas como gold por ContextBench.

Por tanto, encontrar el fichero correcto no implica necesariamente haber
recuperado el fragmento de código correcto.

### ¿Qué estrategias de recuperación estamos comparando?

El experimento compara tres estrategias principales:

1. **BM25**: recuperación léxica basada en coincidencia de términos.
2. **UniXcoder**: recuperación semántica mediante embeddings de código.
3. **BM25 + UniXcoder mediante RRF**: estrategia híbrida que combina los
   rankings léxico y semántico.

Las tres estrategias utilizan el mismo corpus y el mismo chunking para controlar
variables y aislar, en la medida de lo posible, el efecto de la estrategia de
recuperación.

### ¿Cómo funciona conceptualmente la estrategia híbrida?

El flujo puede resumirse de la siguiente forma:

    Issue
      │
      ├── BM25 ────────────┐
      │                    │
      └── UniXcoder ───────┤
                           │
                           ▼
                          RRF
                           │
                           ▼
                    Ranking híbrido
                           │
                           ▼
                     Top-5/10/20
                           │
                           ▼
                 Evaluación file/line

RRF combina las posiciones obtenidas por los chunks en los dos rankings sin
necesidad de comparar directamente los scores de BM25 y UniXcoder.

### ¿Una mejor recuperación implica necesariamente que el LLM resolverá mejor el issue?

No necesariamente.

El experimento distingue dos etapas:

1. **Calidad de recuperación**: evaluamos si las estrategias recuperan el
   contexto relevante utilizando el gold de ContextBench.
2. **Resolución del issue**: posteriormente evaluaremos si el contexto
   recuperado permite al LLM generar una solución correcta.

Una de las cuestiones que queremos analizar es precisamente si una mejor
recuperación de contexto se traduce en una mayor capacidad del LLM para resolver
los issues.

## Mini-piloto y metodología experimental

### 1. ¿Por qué realizar un mini-piloto con unas 5 incidencias de varios repositorios antes de ejecutar las 30–50 tareas finales?

Queremos comprobar que el pipeline validado inicialmente con Astropy se generaliza correctamente a incidencias de distintos repositorios antes de ejecutar el experimento completo.

El objetivo principal de este mini-piloto no es determinar todavía qué estrategia es mejor, sino detectar posibles problemas de generalización relacionados con el clonado de repositorios, el `base_commit`, el chunking, la recuperación o la evaluación.

### 2. Si BM25 obtiene mejores resultados que la estrategia híbrida en algunas incidencias, ¿deberíamos modificar RRF para conseguir que el híbrido gane?

No. El objetivo del experimento no es demostrar que una estrategia concreta sea superior, sino estudiar bajo qué condiciones funciona mejor cada estrategia.

Modificar los parámetros después de observar los resultados para favorecer al híbrido introduciría un sesgo en la comparación.

### 3. ¿Por qué utilizamos exactamente el mismo chunking para BM25, UniXcoder y la estrategia híbrida?

Porque si modificáramos también el chunking introduciríamos otra variable en el experimento y sería más difícil determinar a qué se deben las diferencias observadas.

Por eso mantenemos constantes el chunking y el resto de condiciones experimentales y variamos únicamente la estrategia de recuperación. De esta forma podemos aislar mejor su influencia.

### 4. Si UniXcoder obtiene mejores métricas de recuperación que BM25, pero BM25 permite al LLM resolver más incidencias, ¿sería una contradicción?

No. Una mejor calidad de recuperación según las métricas no implica necesariamente una mayor tasa de resolución por parte del LLM.

El LLM puede aprovechar de forma diferente el contexto recuperado y también puede verse afectado por información irrelevante o ruido.

Precisamente por este motivo evaluamos por separado dos etapas: la calidad del contexto recuperado y la capacidad posterior del LLM para resolver la incidencia.

### 5. ¿Qué información de ContextBench utilizamos para realizar la recuperación y qué información reservamos para la evaluación?

Para realizar la recuperación utilizamos principalmente la descripción de la incidencia (`problem_statement`) sobre el repositorio correspondiente en el estado indicado por `base_commit`.

El `base_commit` determina el estado exacto del repositorio sobre el que debe realizarse el experimento.

El `gold_context` se reserva exclusivamente para la evaluación posterior, comparándolo con el contexto recuperado para determinar su relevancia.

El `gold_context` nunca debe utilizarse para decidir qué recuperar, ya que esto produciría una fuga de información (data leakage) y dejaría de ser una evaluación válida.

## Evaluación downstream con LLM y SWE-bench

### ¿Para qué utilizamos el harness de SWE-bench?

Utilizamos el harness de SWE-bench para evaluar de forma reproducible si los patches generados por el LLM resuelven realmente cada issue.

El harness prepara el entorno de evaluación correspondiente a la tarea, aplica el patch generado, ejecuta los tests definidos para la instancia y determina finalmente si la incidencia puede considerarse resuelta.

Esto evita tener que definir manualmente un procedimiento de testing diferente para cada repositorio.

### ¿Qué significa que una tarea termine con `resolved=True`?

Significa que el grader de SWE-bench ha clasificado la instancia como resuelta después de evaluar el patch generado.

Por tanto, no nos limitamos a comprobar que el patch tenga una sintaxis válida o pueda aplicarse al repositorio, sino que utilizamos el resultado del benchmark para determinar si realmente resuelve la tarea.

### ¿Cuál es la diferencia entre `FAIL_TO_PASS` y `PASS_TO_PASS`?

Los tests `FAIL_TO_PASS` son tests que fallaban antes de aplicar la solución y que deben pasar después de aplicar el patch. Sirven para comprobar que se ha corregido el problema.

Los tests `PASS_TO_PASS` son tests que ya pasaban antes de aplicar la solución y deben continuar pasando después. Sirven para comprobar que el cambio no introduce regresiones en comportamiento que ya funcionaba.

Una forma sencilla de recordarlo es:

- `FAIL_TO_PASS` → ¿hemos arreglado lo que estaba roto?
- `PASS_TO_PASS` → ¿hemos evitado romper lo que ya funcionaba?

### ¿Por qué un error de Podman, un error 503 de Gemini o un fallo de infraestructura no debe contarse automáticamente como un fallo del LLM?

Porque ese tipo de error no demuestra que el LLM haya sido incapaz de resolver el issue.

El fallo puede producirse antes de la generación, durante la comunicación con el proveedor del modelo o durante la infraestructura utilizada para ejecutar y evaluar el patch.

Por ello, debemos distinguir los fallos experimentales de resolución de los fallos de infraestructura. Un error de infraestructura debe registrarse y, cuando corresponda, reintentarse de forma controlada, pero no debe mezclarse directamente con los resultados PASS/FAIL del LLM.

### ¿Por qué haber conseguido un `resolved=True` con BM25 y K=10 no demuestra que BM25 o K=10 sean la mejor configuración?

Porque se trata únicamente de una instancia utilizada para validar técnicamente el pipeline downstream.

El resultado demuestra que la cadena completa puede funcionar:

`issue → retrieval → contexto recuperado → LLM → patch → SWE-bench → resultado`

Pero una única tarea no permite comparar las estrategias de recuperación ni seleccionar una configuración óptima.

Para estudiar si BM25, UniXcoder o RRF influyen de forma diferente en la capacidad del LLM para resolver issues, debemos mantener constantes el modelo, el prompt y el resto del protocolo y comparar los resultados sobre la muestra experimental.

### ¿Por qué el primer `resolved=False` que obtuvimos no era un FAIL válido del LLM?

Porque los tests no habían llegado a ejecutarse correctamente debido a un problema de infraestructura.

El script `eval.sh` generado desde Windows contenía finales de línea CRLF que provocaban errores al ejecutarse dentro del contenedor Linux. Por tanto, aquel `resolved=False` no demostraba que el patch generado por el LLM fuera incorrecto.

Para considerar válido un resultado downstream debemos asegurarnos de que la infraestructura de evaluación ha funcionado correctamente y que SWE-bench ha podido evaluar realmente el patch.

### ¿Qué debemos mantener constante cuando comparemos BM25, UniXcoder y RRF en la evaluación downstream?

Debemos mantener constante todo aquello que no sea la estrategia de recuperación.

En particular:

- el mismo LLM;
- el mismo prompt;
- el mismo valor de K;
- los mismos parámetros de generación;
- el mismo procedimiento de aplicación del patch;
- el mismo procedimiento de evaluación mediante SWE-bench;
- las mismas tareas de la muestra experimental.

De esta forma, la principal variable que cambia entre las condiciones experimentales es la estrategia utilizada para seleccionar el contexto: BM25, UniXcoder o RRF.

Esto permite estudiar si las diferencias en el contexto recuperado se traducen en diferencias en la capacidad del LLM para resolver los mismos issues.

## Ideas clave — Evaluación downstream con LLM

### 1. ¿Qué estamos midiendo realmente en downstream?

La calidad de la recuperación de contexto y la capacidad del LLM para resolver un issue son dos etapas relacionadas, pero diferentes.

Primero evaluamos la calidad del contexto recuperado mediante métricas de retrieval. Posteriormente evaluamos si ese contexto permite al LLM generar un patch que resuelva realmente el issue.

Por tanto:

> Una mejor recuperación de contexto no implica necesariamente una mayor capacidad del LLM para resolver el issue.

Esta relación entre calidad de retrieval y resolución de issues es precisamente uno de los aspectos que queremos estudiar.

### 2. El LLM no puede explorar libremente el repositorio

El LLM recibe únicamente:

- el `problem_statement`;
- el contexto seleccionado por la estrategia de recuperación.

No puede explorar libremente otros ficheros del repositorio.

Además, no recibe:

- `gold_context`;
- el patch de referencia;
- `test_patch`.

Esto permite evitar fuga de información (_data leakage_) y hace que el contexto disponible para el LLM dependa realmente de la estrategia de recuperación.

Si permitiéramos al modelo explorar libremente el repositorio, sería más difícil determinar si la resolución del issue se debe al contexto proporcionado por el retriever o a la exploración realizada posteriormente por el propio LLM.

### 3. ¿Qué función cumple SWE-bench?

El LLM genera un patch, pero necesitamos un procedimiento objetivo y reproducible para determinar si ese patch resuelve realmente el issue.

Para ello utilizamos el _harness_ de SWE-bench.

De forma simplificada:

`issue → retrieval → contexto → LLM → patch → SWE-bench → PASS/FAIL`

El harness permite aplicar el patch, ejecutar la evaluación correspondiente a la instancia y determinar si puede considerarse resuelta.

### 4. Diferencia entre `FAIL_TO_PASS` y `PASS_TO_PASS`

Los tests `FAIL_TO_PASS` son tests que fallaban antes de aplicar la solución y deben pasar después del patch.

Los tests `PASS_TO_PASS` son tests que ya funcionaban antes y deben continuar funcionando después del cambio.

Una forma sencilla de recordarlo es:

> `FAIL_TO_PASS` → ¿hemos arreglado lo que estaba roto?

> `PASS_TO_PASS` → ¿hemos evitado romper lo que ya funcionaba?

Ambos tipos son importantes: no basta con solucionar el problema si para hacerlo introducimos regresiones en comportamiento que ya funcionaba.

### 5. Debemos separar los fallos del LLM de los fallos de infraestructura

No todos los errores producidos durante una ejecución significan que el LLM haya sido incapaz de resolver el issue.

Por ejemplo:

- un error 503 del proveedor del LLM;
- una pérdida de conexión con Podman;
- un error durante la preparación del contenedor;
- un problema que impida ejecutar correctamente los tests.

son problemas de infraestructura.

Si la evaluación no ha podido completarse correctamente, no tenemos evidencia suficiente para clasificar el resultado como un fallo de resolución del LLM.

Por tanto, los errores de infraestructura deben registrarse y tratarse separadamente de los resultados experimentales PASS/FAIL.

### 6. ¿Qué significa nuestro primer `resolved=True`?

El primer `resolved=True` demuestra que hemos validado técnicamente el pipeline downstream completo:

`issue → BM25 Top-10 → contexto recuperado → LLM → patch → SWE-bench → resolved=True`

Esto demuestra que las distintas piezas del pipeline pueden conectarse y producir una evaluación válida de extremo a extremo.

Sin embargo, este resultado corresponde a una única instancia piloto.

Por tanto, NO demuestra:

- que BM25 sea mejor que UniXcoder o RRF;
- que K=10 sea el mejor valor de K;
- que la configuración utilizada en el piloto sea necesariamente la configuración definitiva;
- que podamos extraer conclusiones generales sobre la resolución de issues.

El piloto sirve para validar técnicamente el procedimiento, no para seleccionar la estrategia ganadora.

### 7. Principio fundamental del experimento downstream: controlar las variables

Cuando comparemos BM25, UniXcoder y RRF debemos intentar mantener constante todo aquello que no sea la estrategia de recuperación.

Debemos mantener constantes:

- el mismo LLM;
- el mismo prompt;
- el mismo valor de K;
- los mismos parámetros de generación;
- las mismas tareas;
- el mismo procedimiento de aplicación del patch;
- el mismo procedimiento de evaluación mediante SWE-bench.

La principal variable que cambia será:

**la estrategia utilizada para seleccionar el contexto: BM25, UniXcoder o RRF.**

De esta forma podemos estudiar si cambiar la estrategia de recuperación, y por tanto el contexto proporcionado al LLM, produce diferencias en su capacidad para resolver los mismos issues.

## Idea global para la defensa

El objetivo no es únicamente determinar qué estrategia obtiene mejores métricas de retrieval.

Queremos estudiar si las diferencias en la calidad y selección del contexto recuperado se traducen posteriormente en diferencias en la capacidad de un LLM para resolver incidencias software a nivel de repositorio.

Por ello evaluamos las dos etapas por separado:

1. **Retrieval:** ¿qué contexto recupera cada estrategia?
2. **Downstream:** ¿puede el LLM resolver el issue utilizando ese contexto?

Esta separación permite analizar si una mejor recuperación de contexto se traduce realmente en una mayor capacidad de resolución.

## Preguntas sobre la evaluación downstream y Pass@1

### 1. ¿Por qué un resultado `invalid_patch` se considera un resultado del modelo y no un fallo de infraestructura?

Porque la petición al LLM se ha realizado correctamente y el modelo ha generado una respuesta. El problema es que el diff producido no puede aplicarse correctamente sobre el repositorio en el commit correspondiente.

Por tanto, no ha fallado la infraestructura, el proveedor del LLM ni el sistema de evaluación. La generación se ha completado, pero el resultado generado no es aplicable según el protocolo original (`git apply --check`). Por este motivo se registra como `invalid_patch`, distinto de `infrastructure_error`, y no se regenera automáticamente para respetar Pass@1.

Ahora bien, `invalid_patch` es un resultado de no aplicabilidad y no permite atribuir automáticamente la causa al LLM. El diagnóstico posterior identificó problemas de formato en la salida (el prompt solo pedía un unified diff), parches sin prefijos `a/` y `b/` interpretados con `-p1`, y posibles efectos de los finales de línea (parches guardados con CRLF y comprobación en Windows con `autocrlf=true`). Véase `docs/downstream-patch-diagnostics.md`.

---

### 2. Si SWE-bench falla después de que el LLM ya haya generado un patch, ¿por qué reutilizamos exactamente el mismo patch al reintentar?

Para preservar el protocolo Pass@1.

Una vez que el LLM ha producido un patch, esa generación constituye su única oportunidad para esa condición experimental. Si posteriormente ocurre un fallo de infraestructura, se puede repetir la evaluación, pero no la generación.

Generar un nuevo patch concedería al modelo una segunda oportunidad y podría sesgar los resultados. Además, al tratarse de un modelo no determinista, una nueva llamada podría producir una solución diferente.

Por tanto:

`generación completada → mismo patch → reintento únicamente de la evaluación`

---

### 3. Si en una tarea BM25 obtiene `resolved` mientras Semantic y Hybrid obtienen `invalid_patch`, ¿por qué no podemos afirmar todavía que BM25 sea mejor downstream?

Porque una única tarea no proporciona evidencia suficiente para establecer una conclusión general sobre las estrategias.

El resultado solo demuestra que, para esa tarea concreta y bajo las condiciones experimentales establecidas, el contexto recuperado mediante BM25 permitió al LLM generar una solución válida que resolvió el issue, mientras que las otras estrategias no lo hicieron.

La comparación debe realizarse sobre el conjunto completo de tareas y mediante resultados agregados antes de concluir qué estrategia presenta mejor comportamiento downstream.

---

### 4. ¿Qué intentamos aislar manteniendo fijos el LLM, K=10, el prompt, la configuración de generación y el procedimiento de evaluación?

Intentamos aislar la influencia de la estrategia de recuperación de contexto.

La variable que modificamos entre condiciones es fundamentalmente el método utilizado para recuperar información del repositorio:

- BM25 para recuperación léxica.
- UniXcoder para recuperación semántica.
- RRF para recuperación híbrida.

El resto del protocolo se mantiene fijo para reducir variables de confusión. De esta forma podemos estudiar si cambiar la estrategia que construye el contexto proporcionado al LLM influye en su capacidad para resolver el mismo issue.

---

### 5. ¿Por qué se separan los artefactos y resultados del piloto de los resultados del experimento final?

Porque el piloto se utilizó para desarrollar, depurar y validar el pipeline experimental.

Durante esa fase todavía se estaban realizando modificaciones sobre la generación, evaluación, tratamiento de errores y automatización. Por tanto, esos resultados no deben mezclarse con los obtenidos una vez congelado y validado el procedimiento experimental.

La separación permite mantener una frontera clara entre:

`desarrollo y validación del pipeline ≠ ejecución experimental final`

Así se garantiza que los resultados finales se obtienen bajo un protocolo común y previamente definido.

### ¿Por qué un `invalid_patch` se considera un resultado definitivo en el experimento downstream?

Porque el modelo ya ha realizado su único intento bajo el protocolo Pass@1. Gemini ha generado una respuesta, pero esta no contiene un patch aplicable al commit base de la tarea.

Por tanto, `invalid_patch` se considera un resultado definitivo dentro del experimento: no se realiza una nueva generación, ya que eso supondría conceder al modelo un segundo intento. Registra que el parche no pudo aplicarse según el protocolo original, pero no permite atribuir automáticamente la causa al LLM. El diagnóstico posterior identificó problemas de formato, de prefijos de ruta y posibles efectos de los finales de línea que contribuyen a este resultado (véase `docs/downstream-patch-diagnostics.md`).

### ¿Por qué un `infrastructure_error` no se considera un resultado experimental definitivo?

Porque representa un fallo de la infraestructura utilizada para ejecutar o evaluar el experimento, no necesariamente un fallo del modelo.

Incluso si Gemini ya ha generado un patch válido, un problema posterior en Docker/Podman, en el evaluador o en otro componente de infraestructura puede impedir determinar si dicho patch resuelve la tarea.

Por ello, un `infrastructure_error` puede volver a evaluarse una vez solucionado el problema de infraestructura, pero reutilizando exactamente la misma generación.

### ¿Por qué se reutiliza el mismo patch después de solucionar un `infrastructure_error`?

Porque el experimento utiliza un protocolo Pass@1: cada condición dispone de una única generación del modelo.

Si después de un fallo de infraestructura se volviera a llamar a Gemini, se estaría obteniendo un segundo intento y se alteraría el protocolo experimental.

Por tanto, se corrige únicamente el problema de infraestructura y se vuelve a evaluar exactamente el mismo patch generado originalmente.

### ¿Cuál es la idea fundamental detrás de estas decisiones?

Los fallos del modelo son resultados experimentales; los fallos de nuestra infraestructura no. Reparar la infraestructura nunca debe proporcionar al modelo un nuevo intento.

## Preguntas sobre el cruce retrieval ↔ downstream

### 1. ¿Por qué se utiliza K=10 para relacionar la calidad del retrieval con los resultados downstream?

Aunque la evaluación de recuperación se realizó con K=5, K=10 y K=20, en el experimento downstream se fijó K=10, es decir, se proporcionaron al LLM los 10 chunks mejor posicionados por cada estrategia.

Por tanto, el cruce se realiza con K=10 porque permite analizar exactamente la calidad del contexto que recibió el LLM durante la generación de los patches.

---

### 2. ¿Cuál es la diferencia entre `invalid_patch` y `not_resolved`?

`invalid_patch` significa que el patch generado por el LLM no pudo aplicarse correctamente al estado exacto del repositorio.

`not_resolved` significa que el patch sí pudo aplicarse, pero la evaluación posterior mediante los tests correspondientes determinó que no resolvía la incidencia.

El proceso puede resumirse como:

1. El LLM genera un patch.
2. Se comprueba si el patch puede aplicarse.
3. Si puede aplicarse, se ejecuta la evaluación correspondiente.
4. Si no puede aplicarse → `invalid_patch`.
5. Si se aplica pero no resuelve la incidencia → `not_resolved`.
6. Si se aplica y resuelve la incidencia → `resolved`.

---

### 3. ¿Qué significa que la mediana de `line_f1` sea 0 en los `invalid_patch` y 0.1882 en los patches aplicables?

En las 141 condiciones clasificadas como `invalid_patch`, la mediana de `line_f1` fue 0. Esto significa que al menos la mitad de esas condiciones obtuvo un F1 de recuperación a nivel de líneas igual a cero.

En cambio, entre las 9 condiciones que produjeron un patch aplicable, la mediana de `line_f1` fue 0.1882.

Esto muestra descriptivamente que la recuperación de contexto relevante a nivel de líneas fue mejor entre las condiciones que consiguieron generar patches aplicables.

Sin embargo, no permite afirmar que una peor recuperación sea la causa de los `invalid_patch`. Se observa una asociación descriptiva, no una relación causal demostrada.

---

### 4. ¿Por qué no se puede concluir que BM25 es superior downstream si los dos únicos casos `resolved` utilizaron BM25?

Porque únicamente se obtuvieron 2 casos `resolved` entre las 150 condiciones evaluadas. Ambos correspondieron a BM25, pero el número de éxitos es demasiado reducido para establecer una superioridad downstream estadísticamente sustentada.

Además, la resolución de una incidencia no depende únicamente de la calidad del retrieval. También interviene la capacidad del LLM para interpretar el contexto recuperado y generar un patch correcto y aplicable.

Por tanto, el resultado es compatible con el mejor rendimiento agregado de BM25 observado en la evaluación de retrieval, pero no demuestra que BM25 sea necesariamente superior para la resolución downstream.

---

### 5. ¿Una mejor recuperación de contexto implica necesariamente una mayor capacidad para resolver incidencias?

No.

Una mejor recuperación aumenta la probabilidad de proporcionar al LLM información relevante, pero posteriormente el modelo debe interpretar correctamente ese contexto y generar una modificación válida del código.

En este experimento se observó una señal descriptiva favorable: los patches aplicables presentaron mejores métricas de recuperación, especialmente a nivel de líneas. Sin embargo, la elevada proporción de `invalid_patch` (141 de 150 condiciones) limitó la capacidad para demostrar que las mejoras en retrieval se traducen sistemáticamente en una mayor resolución de incidencias.

Por tanto, una de las conclusiones del experimento es que la calidad del retrieval es importante, pero no constituye por sí sola una garantía de resolución.

### ¿Por qué disminuye el F1 cuando aumenta K?

Al aumentar K se recupera un mayor número de chunks. Esto aumenta la
probabilidad de recuperar contexto relevante y, por tanto, tiende a aumentar
la cobertura.

Sin embargo, también se incorporan más chunks que no son relevantes para la
incidencia, lo que reduce la precisión.

En los resultados obtenidos, la pérdida de precisión al aumentar K fue mayor
que la mejora obtenida en cobertura desde el punto de vista del equilibrio
medido por F1. Por este motivo, el F1 disminuyó al pasar de K=5 a K=10 y K=20.

Por tanto, recuperar más contexto no implica necesariamente recuperar mejor
contexto: existe un compromiso entre cobertura y precisión.

## Preguntas sobre la interpretación de los resultados finales

### 1. ¿Por qué que aumente la cobertura al incrementar K no significa que el retrieval sea necesariamente mejor?

Al aumentar K se recupera un mayor número de chunks. Esto puede aumentar la cobertura, ya que existe una mayor probabilidad de recuperar información relevante, pero también puede introducir más contexto irrelevante o ruido.

En nuestros resultados, al aumentar K la cobertura aumentó, pero la precisión disminuyó. Esta pérdida de precisión fue suficiente para que el F1 disminuyera.

Por tanto, recuperar más contexto no implica necesariamente recuperar mejor contexto. Existe un compromiso entre cobertura y precisión.

---

### 2. ¿Cuál es el principal resultado de la evaluación downstream?

Los dos casos `resolved` y los 141 casos `invalid_patch` aportan información, pero el resultado dominante es que 141 de las 150 condiciones experimentales (94 %) produjeron un patch que no pudo aplicarse correctamente.

Los dos casos `resolved` demuestran que el pipeline completo fue capaz de generar un patch, aplicarlo al repositorio y superar la evaluación correspondiente.

Sin embargo, la elevada proporción de `invalid_patch` indica que la aplicabilidad de los patches generados constituyó un importante cuello de botella en la evaluación downstream.

---

### 3. ¿Podemos afirmar que una mejor recuperación de contexto provoca una mayor capacidad del LLM para resolver las incidencias?

No.

Los patches aplicables presentaron descriptivamente mejores métricas de recuperación a nivel de líneas que los patches no aplicables. Por ejemplo, el grupo aplicable obtuvo mayores valores medios de cobertura y F1 a nivel de líneas.

Sin embargo, únicamente hubo 9 condiciones con patches aplicables frente a 141 no aplicables. Por tanto, los resultados permiten observar una asociación descriptiva, pero no demostrar una relación causal entre una mejor recuperación y la resolución de la incidencia.

En consecuencia, no podemos afirmar que una mejor recuperación provoque necesariamente una mayor tasa de resolución.

---

### 4. ¿Por qué se muestran `n=141` y `n=9` en la figura que compara la calidad del retrieval según la aplicabilidad del patch?

Porque los dos grupos tienen tamaños muy diferentes.

El grupo de patches no aplicables contiene 141 condiciones, mientras que el grupo de patches aplicables contiene únicamente 9.

Mostrar explícitamente el tamaño de cada grupo evita interpretar la comparación como si ambos grupos tuvieran una cantidad similar de observaciones y permite entender que los resultados del grupo aplicable se basan en una muestra pequeña.

Por este motivo, la comparación debe interpretarse principalmente de forma descriptiva y no como evidencia estadística suficiente para establecer una relación causal.

---

### 5. ¿Por qué las tablas y figuras finales se generan mediante código a partir de los resultados experimentales?

Principalmente para garantizar la reproducibilidad y reducir el riesgo de errores manuales.

Las tablas y figuras se generan directamente a partir de los resultados experimentales congelados, evitando copiar o transcribir manualmente los valores.

De esta forma, si se vuelve a ejecutar el mismo código sobre los mismos resultados, deberían obtenerse las mismas métricas, tablas y figuras. Esto facilita además la trazabilidad entre los resultados originales del experimento y los elementos presentados en el TFM.

---

### 6. ¿Cuáles son dos ideas fundamentales que resumen los resultados experimentales?

La primera es que recuperar más contexto no implica necesariamente recuperar mejor contexto. Al aumentar K puede aumentar la cobertura, pero también puede introducirse más ruido y disminuir la precisión.

La segunda es que se observaron indicios descriptivos de una asociación entre una mejor recuperación a nivel de líneas y la aplicabilidad de los patches. Sin embargo, debido al reducido número de patches aplicables y de incidencias resueltas, los resultados no permiten demostrar causalidad ni establecer una superioridad downstream concluyente de BM25.

## Preguntas sobre metodología de recuperación

### 1. ¿Por qué se utilizaron los mismos chunks para BM25 y UniXcoder?

Se utilizaron los mismos chunks para mantener constante la unidad de recuperación en todas las estrategias. De esta forma, las diferencias observadas entre BM25 y UniXcoder se deben principalmente al método utilizado para calcular la relevancia y ordenar los fragmentos, y no a que cada estrategia trabaje con unidades de código diferentes.

### 2. ¿Cuál es la diferencia principal entre recuperación léxica y recuperación semántica?

La recuperación léxica, como BM25, se basa principalmente en la coincidencia de términos entre la consulta y los documentos. En cambio, la recuperación semántica representa la consulta y los fragmentos mediante vectores y los compara según su similitud semántica. Esto permite encontrar fragmentos relacionados aunque no utilicen exactamente las mismas palabras que aparecen en la incidencia.

### 3. ¿Por qué se utilizó UniXcoder en lugar del modelo SFR considerado inicialmente?

Inicialmente se valoró utilizar Salesforce/SFR-Embedding-Code-400M_R, pero durante su integración aparecieron problemas de compatibilidad con el entorno experimental. Dado que el objetivo del TFM es comparar estrategias de recuperación y no diferentes modelos de embeddings, se decidió utilizar UniXcoder en lugar de modificar significativamente el entorno únicamente para poder utilizar SFR.

### 4. ¿Para qué se utilizan mean pooling y la normalización L2 en la recuperación semántica?

UniXcoder genera representaciones para los diferentes tokens de una entrada. Mediante mean pooling se obtiene un único vector que representa globalmente la consulta o el chunk. Posteriormente, este vector se normaliza mediante la norma L2 para facilitar una comparación consistente entre las representaciones. Una vez normalizados los vectores, se pueden comparar mediante el producto escalar, que en este caso equivale a la similitud coseno.

### 5. ¿Qué diferencia existe entre la validación inicial, el piloto y el experimento definitivo?

La validación inicial se realizó sobre una única incidencia y sirvió para comprobar técnicamente que el flujo completo funcionaba correctamente. Posteriormente se realizó un piloto reducido de cinco tareas para detectar posibles problemas antes de escalar el procedimiento. Finalmente, una vez validado y fijado el procedimiento experimental, se ejecutó el experimento definitivo sobre las 50 tareas seleccionadas de ContextBench.

## Preguntas de defensa — Resultados del capítulo 5

### 1. ¿Qué significa F1 en nuestro experimento y por qué nos resulta útil para comparar las tres estrategias?

F1 combina la precisión y la cobertura en una única medida. Nos permite comparar el equilibrio entre cuánto contexto relevante conseguimos recuperar y cuánto de lo que recuperamos es realmente relevante respecto al gold context.

---

### 2. ¿Qué ocurre con la cobertura, la precisión y F1 cuando aumentamos K? ¿Cómo explicarías ese comportamiento?

K representa el número de chunks del ranking que se tienen en cuenta en la evaluación. En nuestros resultados, al aumentar K aumenta la cobertura, porque al considerar más chunks tenemos más posibilidades de incluir contexto relevante. Sin embargo, disminuye la precisión, ya que también se incorpora más contexto que no pertenece al gold context. Como consecuencia de este equilibrio, en nuestros resultados también disminuye F1.

---

### 3. ¿Qué conclusión podemos sacar de que BM25 obtenga el mayor F1 agregado en las seis configuraciones evaluadas? ¿Y qué conclusión no podemos sacar?

Podemos afirmar que, bajo las condiciones de nuestro experimento, BM25 obtiene el mejor equilibrio agregado entre cobertura y precisión para los valores de K y los niveles de evaluación analizados.

No podemos concluir que BM25 sea el mejor método de recuperación en general, ya que los resultados corresponden a una muestra, un benchmark, un procedimiento de chunking y unas configuraciones concretas.

---

### 4. En la evaluación con el LLM obtenemos 141 parches no aplicables, 7 aplicables pero no resueltos y 2 resueltos. ¿Por qué estos resultados limitan las conclusiones sobre las estrategias de recuperación?

Porque 141 de las 150 condiciones experimentales no llegan a la evaluación funcional. Solo nueve parches pueden aplicarse y únicamente dos consiguen resolver la incidencia.

Por tanto, disponemos de muy pocos casos para estudiar si las diferencias observadas entre las estrategias de recuperación se traducen realmente en una mayor capacidad de resolución mediante el LLM.

---

### 5. Los dos casos resueltos presentan valores relativamente altos de cobertura y F1. ¿Podemos afirmar que una mejor recuperación provoca una mayor tasa de resolución?

No. Podemos observar que los casos resueltos presentan mejores valores en varias métricas de recuperación, pero únicamente existen dos casos resueltos.

Esto permite describir una asociación dentro de nuestra muestra, pero no establecer una relación causal entre una mejor recuperación de contexto y una mayor capacidad de resolución.

Idea clave: asociación no implica causalidad.

---

### 6. ¿Qué significa exactamente que BM25 tenga un F1 mayor que UniXcoder y RRF en nuestros resultados?

Significa que, bajo las condiciones evaluadas en nuestro experimento, BM25 obtiene un mejor equilibrio agregado entre cobertura y precisión.

No significa que BM25 gane necesariamente en todas las tareas individuales ni que sea superior en cualquier escenario de recuperación de código.

---

### 7. ¿Por qué no podemos afirmar simplemente que “BM25 es el mejor” en general?

Porque nuestros resultados corresponden a una muestra concreta de 50 tareas de ContextBench y a unas condiciones experimentales determinadas: mismo chunking, valores de K de 5, 10 y 20, y evaluación a nivel de fichero y línea.

Podemos afirmar que BM25 obtiene el mayor F1 agregado bajo estas condiciones, pero no generalizar el resultado a cualquier repositorio, benchmark o configuración de recuperación.

---

### 8. ¿Qué efecto observamos al aumentar K de 5 a 10 y a 20?

En las tres estrategias observamos el mismo patrón general: al aumentar K aumenta la cobertura, mientras que disminuyen la precisión y F1.

Esto muestra que recuperar una mayor cantidad de contexto no implica necesariamente obtener un mejor equilibrio entre el contexto relevante recuperado y la información adicional incorporada.

---

### 9. ¿Por qué los 141 parches no aplicables limitan específicamente las conclusiones de la evaluación downstream?

Porque esos 141 casos no llegan a la evaluación funcional del parche. De las 150 condiciones experimentales, solo nueve generan un parche aplicable y únicamente dos terminan resolviendo la incidencia.

Esto deja muy pocos casos para estudiar si las diferencias en la calidad de la recuperación se traducen realmente en diferencias en la resolución de las incidencias.

---

## Tres ideas clave para la defensa

1. **Recuperación:** BM25 obtiene el mayor F1 agregado en las condiciones evaluadas.

2. **Downstream:** solo se obtienen 9 parches aplicables y 2 incidencias resueltas, por lo que no se puede concluir que BM25 sea superior de forma general en la resolución de incidencias.

3. **Relación recuperación-resolución:** se observa una asociación descriptiva entre mejores métricas de recuperación y algunos resultados favorables, pero los datos no permiten demostrar una relación causal.
