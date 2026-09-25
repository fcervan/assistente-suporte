FROM python:3.12-slim
# libs de sistema p/ opencv (docling/tableformer) — sem elas: libxcb.so.1 ImportError
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libxcb1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8002
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
