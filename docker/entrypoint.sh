#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

# Variable para el host de la base de datos, tomada de docker-compose
DB_HOST="db"
DB_PORT="5432"

echo "Esperando a que PostgreSQL se inicie..."

# Bucle que espera a que el puerto de la base de datos esté abierto
# Usamos el comando 'nc' (netcat) que es una herramienta ligera para redes
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done

echo "PostgreSQL iniciado correctamente."

# Ejecutar las migraciones de la base de datos
echo "Ejecutando migraciones de la base de datos..."
flask db upgrade

echo "Migraciones completadas."

# Ejecutar el comando principal pasado al script (CMD de Dockerfile)
exec "$@"