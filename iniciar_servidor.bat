@echo off
echo Iniciando Servidor Web de PQRS...
cd /d D:\PROYECTOS\proyecto_pqrs
call venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000