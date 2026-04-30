FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OCR and PDF conversion
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 10000

# Ensure data directories exist
RUN mkdir -p uploads temp_images outputs

# Command to run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--timeout", "120", "app:app"]
