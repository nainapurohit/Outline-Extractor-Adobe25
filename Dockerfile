#lightweight Python image as a base
FROM python:3.11-slim

#working directory
WORKDIR /app

#requirements file
COPY requirements.txt .

#Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

#Python script
COPY main.py .

#command to run when the container starts
CMD ["python", "main.py"]