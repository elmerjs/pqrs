@echo off
echo ================================================
echo INICIANDO REVISION AUTOMATICA DE CORREOS PQRS
echo ================================================

REM Cambia al directorio de tu proyecto
cd /d D:\PROYECTOS\proyecto_pqrs\

REM Activa el entorno virtual
call venv\Scripts\activate

REM Ejecuta el comando de Django para procesar correos
echo --- Ejecutando el script de Django...
python manage.py procesar_correos

echo.
echo --- Proceso finalizado. ---

REM Desactiva el entorno virtual (opcional)
call venv\Scripts\deactivate

REM Esta linea es util para pruebas. La ventana se quedara abierta.
pause