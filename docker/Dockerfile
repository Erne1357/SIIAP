# Usa una imagen oficial de Python optimizada
FROM python:3.9-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de dependencias
COPY requirements.txt .

# Instala dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia todo el contenido del proyecto al contenedor
COPY . .

# Expone el puerto en el que corre Flask
EXPOSE 5000

# Comando para correr la app directamente
CMD ["python", "app.py"]
