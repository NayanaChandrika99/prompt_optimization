FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voice_ai_keep_gepa/dashboard /app/voice_ai_keep_gepa/dashboard

EXPOSE 5000

CMD ["python", "voice_ai_keep_gepa/dashboard/app.py"]
