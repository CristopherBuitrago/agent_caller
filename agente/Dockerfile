# Se construye desde la raíz del repositorio.
FROM python:3.12-slim

# Solo para las pruebas de punta a punta (levantan la API del backend en memoria). El código del
# agente no importa el núcleo: test_architecture.py lo vigila.
WORKDIR /app/backend
COPY backend/pyproject.toml .
COPY backend/src ./src
RUN pip install --no-cache-dir -e ".[dev]"

WORKDIR /app/agente
COPY agente/pyproject.toml .
COPY agente/src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY agente/tests ./tests

CMD ["pytest", "-q"]
