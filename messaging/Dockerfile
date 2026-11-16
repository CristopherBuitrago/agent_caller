# Se construye desde la raíz del repositorio: necesita el núcleo (backend/) instalado primero.
FROM python:3.12-slim

WORKDIR /app/backend
COPY backend/pyproject.toml .
COPY backend/src ./src
RUN pip install --no-cache-dir -e .

WORKDIR /app/messaging
COPY messaging/pyproject.toml .
COPY messaging/src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY messaging/tests ./tests

CMD ["pytest", "-q"]
