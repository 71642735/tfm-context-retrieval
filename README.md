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
