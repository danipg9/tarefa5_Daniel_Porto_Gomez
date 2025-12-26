#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Crear tablas en la base de datos remota (Postgres)
# Ejecutamos el script que creamos antes para inicializar la BD
python init_db.py