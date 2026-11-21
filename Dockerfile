FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY app ./app
COPY migrations ./migrations

USER 10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
