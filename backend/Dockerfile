# Se construye desde la raíz del repositorio (ver docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app/backend

COPY backend/pyproject.toml .
COPY backend/src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY backend/tests ./tests

CMD ["pytest", "-q"]
