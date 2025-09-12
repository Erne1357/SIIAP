# docker/Dockerfile (antes docker/dockerfile)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
# instala gunicorn
RUN pip install gunicorn
COPY . .
EXPOSE 5000
# usa gunicorn en lugar de 'python app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
