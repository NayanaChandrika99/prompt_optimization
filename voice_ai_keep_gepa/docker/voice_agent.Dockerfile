FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voice_ai_keep_gepa/voice_agent /app/voice_ai_keep_gepa/voice_agent

EXPOSE 5100

CMD ["python", "voice_ai_keep_gepa/voice_agent/app.py"]
