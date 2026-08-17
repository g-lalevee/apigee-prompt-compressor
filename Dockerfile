FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY compressor_image/ ./compressor_image/

# Expose port
EXPOSE 8000

# Run application
CMD uvicorn compressor_image.main:app --host 0.0.0.0 --port ${PORT:-8000}
