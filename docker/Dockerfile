# docker/Dockerfile 
FROM python:3.11-slim
WORKDIR /app

# Configura la zona horaria de Ciudad Juárez
ENV TZ=America/Ciudad_Juarez
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instala netcat para el script de espera de la BD
# Instala dependencias del sistema para weasyprint (renderizado HTML→PDF)
RUN apt-get update && apt-get install -y \
    netcat-traditional tzdata curl \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-info \
    fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

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