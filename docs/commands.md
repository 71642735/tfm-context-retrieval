$env:PYTHONPATH = "$PWD\external\ContextBench;$PWD"
python run_semantic_retrieval.py astropy\_\_astropy-12907

Para volver al entorno original del TFM, copia y ejecuta estas tres líneas en PowerShell:
deactivate
cd C:\Users\juan.a.gutierrez\Proyectos\tfm-context-retrieval
.\.venv\Scripts\Activate.ps1

Y para volver al entorno de reproducibilidad:
deactivate
cd C:\Users\juan.a.gutierrez\Proyectos\tfm-reproducibilidad
.\.venv\Scripts\Activate.ps1
