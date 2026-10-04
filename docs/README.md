# Preguntas del TFM

## ¿Cuál es el problema que intenta resolver tu TFM?

Un agente necesita seleccionar contexto relevante de un repositorio grande. Quieres estudiar qué estrategia de recuperación le proporciona mejor contexto y si eso ayuda después al LLM a resolver el issue.

## ¿Qué es ContextBench y por qué lo utilizas?

Es el benchmark que usamos para disponer de issues reales y de un contexto gold con el que comparar lo recuperado.

## ¿Qué significa “gold context”?

Es el contexto de referencia que el benchmark considera relevante para la tarea. Lo utilizamos para evaluar lo que recupera nuestro sistema.

## ¿Por qué haces chunking?

Porque no queremos entregar el repositorio completo al recuperador. Lo dividimos en unidades manejables de código que puedan ser buscadas y ordenadas.

## ¿Qué es un chunk en tu experimento?

Principalmente una función o método de Python, con fichero, símbolo, líneas y código.

## ¿Por qué usaste AST para crear los chunks?

Porque permite dividir el código según su estructura sintáctica, en lugar de cortar arbitrariamente cada N caracteres o líneas.

## ¿Qué es BM25?

Un método de recuperación léxica: puntúa los chunks según la coincidencia y relevancia de términos respecto al texto del issue. No “entiende” semánticamente el código como un embedding.

## ¿Qué le das como consulta a BM25?

El problem_statement del issue.

## ¿Qué texto indexas de cada chunk?

En nuestro baseline: file_path + symbol + code.

## ¿Qué significa Top-K?

Los K chunks con mayor puntuación devueltos por el recuperador. Estamos evaluando K=5, 10 y 20.

## ¿Cómo sabes si BM25 lo ha hecho bien?

Comparamos el contexto recuperado con el contexto gold mediante métricas a diferentes granularidades.

## ¿Qué significa coverage?

Qué proporción del contexto gold hemos conseguido recuperar.

## ¿Qué significa precision?

Qué proporción de lo que hemos recuperado corresponde al gold.

## ¿Por qué al aumentar K puede subir coverage pero bajar precision?

Porque recuperamos más contexto y tenemos más posibilidades de cubrir el gold, pero también podemos introducir más contexto irrelevante.

## ¿Qué significa file coverage = 1 y line coverage = 0?

Hemos encontrado el fichero correcto, pero no la región correcta dentro de ese fichero. Esto ya nos ocurrió en el piloto.

## ¿Qué es la evaluación por símbolos?

Comprueba si recuperamos unidades de código relevantes, como funciones o clases, no solo el fichero o las líneas exactas. Para Python, ContextBench considera funciones, clases y funciones async como definiciones. Texto pegado

## ¿Por qué no utilizas solo la métrica por líneas?

Porque las distintas granularidades cuentan cosas diferentes. Por ejemplo, un span gold puede incluir líneas en blanco o código entre definiciones; fichero, símbolo y línea ofrecen perspectivas complementarias.

## ¿Por qué empiezas por BM25?

Porque proporciona un baseline léxico sencillo y reproducible que después podremos comparar con recuperación semántica e híbrida.

## ¿Por qué mantienes el mismo chunking para BM25, semántico e híbrido?

Para aislar la variable que queremos estudiar: la estrategia de recuperación. Si cambiásemos también el chunking, no sabríamos qué cambio produjo la diferencia.

## ¿Un mejor retrieval implica necesariamente que el LLM resolverá mejor el issue?

No necesariamente. Precisamente una de las ideas importantes del TFM es comprobar la relación entre calidad del contexto recuperado y capacidad posterior del LLM para resolver el problema.

## Explíqueme con un ejemplo un resultado obtenido en su experimento.

En el primer issue, BM25 recuperó correctamente astropy/modeling/separable.py, por lo que obtuvo cobertura perfecta a nivel de fichero. Sin embargo, los primeros chunks recuperados pertenecían a otras zonas del fichero y no solapaban las líneas gold. Por eso la cobertura a nivel de líneas fue cero. Esto muestra que encontrar el fichero correcto no implica necesariamente recuperar el contexto concreto necesario para resolver el problema.
