FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Ensure PaddleOCR can write models to a writable cache
ENV HOME=/tmp
ENV PPOCR_HOME=/tmp/.paddleocr
RUN mkdir -p /tmp/.paddleocr && chmod -R 777 /tmp/.paddleocr

# No GPU dependencies required for PaddleOCR CPU inference

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py /app/app.py

# Expose port
ENV PORT=7860
EXPOSE 7860

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
