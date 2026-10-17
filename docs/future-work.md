# Trabajo futuro

Este documento recoge posibles líneas de trabajo futuro identificadas durante el desarrollo experimental del TFM.

Estas ideas no forman parte del alcance experimental actual. Su inclusión aquí tiene como objetivo conservar propuestas que puedan ser discutidas posteriormente en la memoria y aplicadas al desarrollo de un agente de programación más avanzado.

## 1. Recuperación iterativa y adaptativa

El experimento actual realiza una única recuperación de contexto antes de invocar al LLM, utilizando un número fijo de fragmentos recuperados.

Como posible extensión, se podría estudiar un mecanismo iterativo en el que el modelo analice inicialmente un conjunto reducido de contexto y pueda solicitar nuevas recuperaciones cuando determine que necesita información adicional.

El objetivo sería evolucionar desde una recuperación estática previa a la generación hacia una recuperación iterativa, en la que el agente determine dinámicamente qué información adicional necesita para resolver la incidencia, sin necesidad de incorporar el repositorio completo a la ventana de contexto.

## 2. Recuperación basada en estructura del código

Las estrategias actuales podrían complementarse con información estructural extraída del código fuente.

Entre otras posibilidades:

- símbolos;
- AST (Abstract Syntax Tree);
- llamadas entre funciones y métodos;
- dependencias entre módulos;
- relaciones entre clases;
- imports;
- referencias entre archivos.

Esta información permitiría expandir el contexto a partir de las relaciones del código y no únicamente mediante similitud léxica o semántica.

## 3. Recuperación específica de tests

Una posible extensión consistiría en localizar automáticamente tests relacionados con los fragmentos de código recuperados.

Los tests pueden aportar información sobre el comportamiento esperado del sistema y ayudar al modelo a comprender tanto el problema como las condiciones que debe satisfacer una posible solución.

## 4. Selección dinámica de la cantidad de contexto

El experimento actual utiliza valores fijos de K para garantizar una comparación controlada entre estrategias.

En un agente real podría estudiarse una selección dinámica de la cantidad de contexto, comenzando con un conjunto reducido de fragmentos y ampliándolo únicamente cuando resulte necesario.

Esto permitiría investigar el equilibrio entre información disponible, ruido introducido en el contexto, consumo de tokens y capacidad de resolución.

## 5. Uso del feedback de ejecución

El sistema experimental actual evalúa el patch generado sin proporcionar al modelo nuevas oportunidades de corrección.

Un agente de programación podría utilizar un proceso iterativo:

1. generar una modificación;
2. aplicar el patch;
3. ejecutar los tests;
4. analizar los errores obtenidos;
5. recuperar contexto adicional si fuera necesario;
6. generar una corrección;
7. repetir hasta alcanzar un criterio de finalización.

De esta forma, los resultados de ejecución pasarían a formar parte del contexto utilizado por el agente para tomar decisiones posteriores.

## 6. Evaluación con modelos de mayor capacidad

Se podría estudiar el efecto de utilizar modelos de lenguaje de mayor capacidad manteniendo constantes las estrategias de recuperación.

Esto permitiría analizar hasta qué punto los fallos de resolución dependen de la calidad del contexto recuperado y hasta qué punto están relacionados con la capacidad del modelo para comprender el problema y producir una modificación correcta.

## 7. Separación del efecto de retrieval y generación

Los resultados downstream dependen de una cadena de etapas: recuperación del contexto, interpretación del problema, generación del patch, aplicación del patch y superación de los tests.

Como trabajo futuro podría diseñarse una evaluación específica que permita distinguir con mayor precisión los fallos provocados por contexto insuficiente de aquellos producidos durante la generación de la solución.

## 8. Aplicación a un agente de programación completo

Las estrategias estudiadas en este TFM podrían utilizarse como base para desarrollar un agente de programación orientado a la resolución automática de incidencias.

En lugar de proporcionar el repositorio completo al modelo, el agente podría combinar recuperación léxica, semántica y estructural con ciclos iterativos de razonamiento, recuperación, modificación y ejecución de tests.

El objetivo sería proporcionar al modelo únicamente la información necesaria para tomar cada decisión, ampliando progresivamente el contexto cuando fuera necesario.
