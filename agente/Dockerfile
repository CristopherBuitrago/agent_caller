# Se construye desde la raíz del repositorio: necesita el núcleo (backend/) instalado primero.
FROM python:3.12-slim

WORKDIR /app/backend
COPY backend/pyproject.toml .
COPY backend/src ./src
RUN pip install --no-cache-dir -e .

WORKDIR /app/agente
COPY agente/pyproject.toml .
COPY agente/src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY agente/tests ./tests

CMD ["pytest", "-q"]
