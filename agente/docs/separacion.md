# Separar el agente a su propio repositorio

El agente es el servicio más fácil de separar: su código no importa el núcleo y le pide todo a la API del backend por HTTP.

## Qué lo ata hoy a este repositorio

| Atadura | Por qué existe | Cómo se resuelve al separarlo |
| --- | --- | --- |
| **Las pruebas de punta a punta** (`tests/integration/`) levantan en memoria la API del backend y usan su base. Por eso el `Dockerfile` instala el núcleo para las pruebas | Probar llamadas completas con las reglas reales | Correrlas contra una API del backend ya levantada (su imagen publicada, con una base de prueba), en lugar de importarla |
| **`test_backend_contract.py`** importa `cobranza.domain.call` | Revisar que la copia de `CallDirection` y `CallOutcome` no se separe del backend | Revisar contra la respuesta de `GET /api/agent/tools` o contra el esquema OpenAPI publicado del backend, con versión |
| **El `docker-compose.yml` de la raíz** levanta la base y la API para el chat y la página web | Desarrollo local | Su propio compose, con la imagen publicada del backend y una base de prueba |
| **Los casos de prueba de la página web** usan los datos simulados del backend (TEST-001...) | Demo | Documentar que dependen del seed del backend, o pedirlos a la API |

## Pasos

1. Mover `agente/` (con `tests/` y su `Dockerfile`) a un repositorio nuevo, conservando su historial (`git filter-repo --subdirectory-filter agente`).
2. Quitar del `Dockerfile` la instalación del núcleo y cambiar las pruebas de integración y de contrato como dice la tabla.
3. Fijar la versión de la API del backend que usa (por ejemplo, `/api/v1/...`).
4. Agregar las pruebas automáticas y publicar la imagen con versión.
