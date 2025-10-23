FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voice_ai_keep_gepa/gepa_optimizer /app/voice_ai_keep_gepa/gepa_optimizer

EXPOSE 8000

CMD ["python", "voice_ai_keep_gepa/gepa_optimizer/service.py"]
