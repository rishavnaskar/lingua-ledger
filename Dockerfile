FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-spa tesseract-ocr-ita \
    tesseract-ocr-por tesseract-ocr-jpn tesseract-ocr-chi-sim tesseract-ocr-ind tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY lingua_ledger ./lingua_ledger
COPY api ./api
COPY samples ./samples
COPY artifacts/calibrator.json artifacts/summary.json artifacts/*.png ./artifacts/
RUN uv sync --frozen --no-dev

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
