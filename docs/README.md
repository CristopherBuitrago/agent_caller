# Documentos

```
docs/
├── para_el_jefe/     lo que espera respuesta de la empresa
├── propuesta/        lo entregado al cliente
└── scripts/          cómo se generan los PDF y los Word
```

## `para_el_jefe/`

| Archivo | Qué es |
| --- | --- |
| `pendientes_externos.md` y `.pdf` | Lo que falta y no depende del desarrollo: lo urgente, las dudas para el jefe, los proveedores y lo legal |
| `preguntas_proveedores.md` y `.pdf` | Lo que necesitamos de la empresa y las preguntas para Vaspian, el procesador de pagos, Lariat y los proveedores de IA |
| `criterios_exito_piloto.md` y `.pdf` | Qué tiene que lograr el piloto para pasar a producción: cumplimiento, funcionamiento técnico y resultados de cobro, más cómo se hace el piloto |
| `dudas_para_el_jefe.md` | Cada duda con la observación de la que salió y las respuestas del jefe, con fecha. No tiene PDF |

## `propuesta/`

| Archivo | Qué es |
| --- | --- |
| `propuesta_es.pdf` y `.docx` | Propuesta en español |
| `proposal_en.pdf` y `.docx` | Propuesta en inglés |

El contenido de la propuesta vive en `scripts/generar_propuesta.py`, no en un `.md`. Para cambiar el texto se edita ese script y se vuelven a generar el PDF y el Word.

## Cómo regenerar

El `.md` es la única fuente: se edita el `.md` y se vuelve a generar el PDF. Todo se corre desde `docs/`, en un contenedor con reportlab. En este computador ese contenedor es `pdfgen`, con `docs/` montado en `/docs`.

| Para qué | Comando |
| --- | --- |
| PDF de un `.md` (queda al lado, con el mismo nombre) | `python scripts/generar_pdf.py para_el_jefe/pendientes_externos.md` |
| PDF de varios `.md` a la vez | `python scripts/generar_pdf.py para_el_jefe/pendientes_externos.md para_el_jefe/preguntas_proveedores.md` |
| Propuesta en PDF | `python scripts/generar_propuesta.py es` (o `en`) |
| Propuesta en Word (necesita además pypdfium2, pillow y python-docx) | `python scripts/generar_propuesta_word.py es` (o `en`) |

Ejemplo con Podman: `podman exec -w /docs pdfgen python scripts/generar_pdf.py para_el_jefe/preguntas_proveedores.md`

`scripts/pdf_desde_md.py` tiene las funciones compartidas. Entiende títulos (`#` y `##`), párrafos, viñetas (`- `) y tablas. En una columna "Estado", la primera palabra (Aplicada, Decidida, Por confirmar, En pausa, Pendiente) sale en color. El título del PDF es el primer `#` del `.md`.
