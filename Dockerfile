FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Buat workdir
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . /app

# Use exec form for proper signal handling
CMD ["python", "-u", "main.py"]