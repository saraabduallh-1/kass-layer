# خصص: demo page + term detector API in one small CPU-only container (no model at query time).
#   docker build -t kass:latest .          (needs demo_local/ built by scripts/demo/build_*.py)
#   docker run -p 8000:8000 kass:latest    → http://localhost:8000  (API docs: /docs)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    KASS_DATA_DIR=/app/data KASS_SERVE_PAGE=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/kass_layer src/kass_layer
COPY demo_local data
RUN useradd --system --uid 10001 kass
USER kass
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "kass_layer.detector.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
