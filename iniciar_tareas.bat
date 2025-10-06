@echo off
echo Iniciando Procesador de Tareas de PQRS...
cd /d D:\PROYECTOS\proyecto_pqrs
call venv\Scripts\activate
python manage.py process_tasks