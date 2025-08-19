FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face cache in writable location
ENV HF_HOME=/tmp/hf
ENV HUGGINGFACE_HUB_CACHE=/tmp/hf
RUN mkdir -p /tmp/hf && chmod -R 777 /tmp/hf

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


