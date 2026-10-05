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
