FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LOG_TO_FILE=false

WORKDIR /app

# Run as non-root for defense-in-depth
RUN useradd --create-home --home-dir /home/app --shell /usr/sbin/nologin --uid 10001 app

COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

# Minimal healthcheck without extra packages (curl/wget)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
