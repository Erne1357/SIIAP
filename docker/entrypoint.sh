#!/bin/sh

set -e

DB_HOST="db"
DB_PORT="5432"
REDIS_HOST="redis"
REDIS_PORT="6379"

# ─── Esperar PostgreSQL ───────────────────────────────────────────────────────
echo "Esperando a que PostgreSQL se inicie en $DB_HOST:$DB_PORT..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "PostgreSQL listo."

# ─── Esperar Redis ────────────────────────────────────────────────────────────
echo "Esperando a que Redis se inicie en $REDIS_HOST:$REDIS_PORT..."
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 0.1
done
echo "Redis listo."

# ─── Resolver IP de Redis (evita DNS lookup en eventlet) ─────────────────────
# eventlet parchea el socket y el DNS vía tpool ignora socket_connect_timeout,
# causando bloqueos de ~20s. Resolvemos aquí y guardamos la IP en REDIS_URL.
REDIS_IP=$(getent hosts $REDIS_HOST | awk '{ print $1 }' | head -1)
if [ -n "$REDIS_IP" ]; then
  echo "Redis IP resuelta: $REDIS_IP"
  export REDIS_URL="redis://${REDIS_IP}:${REDIS_PORT}/0"
  export CELERY_BROKER_URL="redis://${REDIS_IP}:${REDIS_PORT}/1"
  export CELERY_RESULT_BACKEND="redis://${REDIS_IP}:${REDIS_PORT}/2"
else
  echo "Advertencia: no se pudo resolver la IP de Redis, usando hostname."
fi

# ─── Migraciones de base de datos ─────────────────────────────────────────────
echo "Ejecutando migraciones..."
flask db upgrade
echo "Migraciones completadas."

# ─── Ejecutar el comando principal (CMD del Dockerfile) ───────────────────────
exec "$@"
