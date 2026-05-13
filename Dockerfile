FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bridge/ ./bridge/

EXPOSE 8080

CMD ["uvicorn", "bridge.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
