FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

COPY app.py llm_generator.py download_fonts.py ./
COPY static/ ./static/
RUN python download_fonts.py

# One worker limits simultaneous Chromium processes on the free instance.
CMD ["sh", "-c", "exec gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 1 --timeout 180 --access-logfile - --error-logfile -"]
