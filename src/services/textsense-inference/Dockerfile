FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime

WORKDIR /app

# Create cache directory with proper permissions
RUN mkdir -p /tmp/hf && chmod 777 /tmp/hf

# Set environment variables for model caching
ENV HF_HOME=/tmp/hf
ENV TRANSFORMERS_CACHE=/tmp/hf
ENV HUGGINGFACE_HUB_CACHE=/tmp/hf

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
