# docker/Dockerfile 
FROM python:3.11-slim
WORKDIR /app

# Instala netcat para el script de espera de la BD
RUN apt-get update && apt-get install -y netcat-traditional && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
# instala gunicorn
RUN pip install gunicorn
COPY . .

# Copia y da permisos de ejecución al script de entrada
COPY docker/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 5000

# Define el entrypoint
ENTRYPOINT ["entrypoint.sh"]

# El comando por defecto, que será pasado al entrypoint
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]