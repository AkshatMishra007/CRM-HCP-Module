FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies if any are needed (e.g. gcc, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Set environment variable to make sure python outputs are unbuffered (great for docker logging)
ENV PYTHONUNBUFFERED=1

# Command to run the application (running on 0.0.0.0 is critical inside Docker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
