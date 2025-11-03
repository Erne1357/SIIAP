# docker/Dockerfile 
FROM python:3.11-slim
WORKDIR /app

# Configura la zona horaria de Ciudad Juárez
ENV TZ=America/Ciudad_Juarez
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instala netcat para el script de espera de la BD
RUN apt-get update && apt-get install -y netcat-traditional tzdata && rm -rf /var/lib/apt/lists/*

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