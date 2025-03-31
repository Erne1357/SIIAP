# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file from the project root into the container
COPY requirements.txt .
# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code into the container
COPY app/ app/
# Copy the main entry point file
COPY app.py .

# Expose port 5000 for the Flask app
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the application
CMD ["flask", "run"]
