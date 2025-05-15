# SIIAPEC – Sistema Integral de Información - Admisión, PErmanencias y Conclusión

> Gestión unificada de **admisión → permanencia → conclusión**, 100 % web y container‑ready.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.x-lightgrey)
![PostgreSQL](https://img.shields.io/badge/postgresql-14-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)

---

## Tabla de Contenidos
1. [¿Qué es SIIAPEC?](#qué-es-siiapec)
2. [Características clave](#características-clave)
3. [Arquitectura](#arquitectura)
4. [Tecnologías](#tecnologías)
5. [Modelo de datos](#modelo-de-datos)
6. [Estructura del proyecto](#estructura-del-proyecto)
7. [Primeros pasos](#primeros-pasos)
8. [Flujo de desarrollo](#flujo-de-desarrollo)
9. [Pruebas](#pruebas)
10. [Roadmap](#roadmap)
11. [Licencia](#licencia)

---

## ¿Qué es SIIAPEC?
Plataforma web para la **División de Posgrados** del TecNM‑ITCJ que digitaliza el ciclo completo de un alumno:

* **Admisión** – carga y validación de requisitos.  
* **Permanencia** – seguimiento semestral y gestión de entregables.  
* **Conclusión** – entrega de tesis y trámites de titulación.  
* Auditoría, bitácora, notificaciones in‑app y paneles de administración.

---

## Características clave
| Módulo | Descripción rápida |
|--------|-------------------|
| **M1 – Información de Programas** | Listado público y detalle con pasos de admisión. |
| **M2 – Perfil de Usuario** | Edición de datos, cambio de contraseña, estado de inscripción. |
| **M3 – Inscripción** | Flujo guiado de requisitos + subida de documentos. |
| **M4 – Revisión de Documentos** | Panel para revisores con aprobar / rechazar y bitácora. |
| **M5 – Reportes & Admin** | Dashboard, gestión de programas/usuarios, exportación PDF/Excel. |
| **M6 – Notificaciones** | Bandeja in‑app, eventos automáticos, sin e‑mail externo. |

Roles incorporados (`role`): `postgraduate_admin`, `program_admin`, `document_reviewer`, `applicant`.

---

## Arquitectura
\`\`\`
Nginx (caché estática)  ←→  Flask app (Gunicorn)  ←→  PostgreSQL
└──────── docker-compose orchestration ────────┘
\`\`\`

* **Monolito modular** en Flask (Blueprints por dominio).  
* Contenedores separados para infra, pero **una sola base de código**.  
* Frontend SSR (Jinja + Bootstrap) con **Swup** para transiciones SPA‑like y **AOS** para animaciones.  
* Hot‑reload y tareas async preparados para Celery/RQ.

---

## Tecnologías
| Capa | Stack |
|------|-------|
| Backend | Python 3.9, Flask 2.x, SQLAlchemy, Flask‑Login, WTForms |
| Frontend | Jinja2, Bootstrap 5, Swup 4, AOS, Vanilla JS |
| Persistencia | PostgreSQL 14, Alembic/Flask‑Migrate |
| Contenedores | Docker + docker‑compose |
| Otros | Gunicorn, Nginx, pytest, ruff |

---

## Modelo de datos (resumen)
Tabla | Propósito
------|----------
\`user\` | Datos de cuenta y preferencias
\`program\` | Posgrados ofertados, con coordinador asignado
\`phase\` | Agrupa pasos por **admission**, **permanence**, **conclusion**
\`step\` | Requisito individual dentro de una fase
\`program_step\` | Puente M:N + \`sequence\` de cada paso en un programa
\`archive\` | Plantillas/documentos base descargables o cargables
\`submission\` | Entregas del usuario, estado y fechas de revisión
\`user_program\` | Matrícula viva del estudiante (semestre, status)
\`log\` | Bitácora de acciones administrativas

*(ver `/docs` para diagrama completo).*

---

## Estructura del proyecto
\`\`\`
.
├─ app/
│  ├─ models/           # ORM
│  ├─ routes/           # Blueprints
│  ├─ templates/        # Jinja (auth, programs, user…)
│  ├─ static/           # css/, js/, assets/
│  └─ config.py
├─ database/DDL|DML/
├─ docker/
├─ tests/
└─ README.md
\`\`\`

---

## Primeros pasos
### Requisitos
* Docker 20.10+ y docker‑compose v2  
* (Opcional dev) Python 3.9, Poetry o venv

### Clonar & levantar
\`\`\`bash
git clone https://github.com/<tu-org>/siiapec.git
cd siiapec
cp .env.example .env
docker compose up --build
\`\`\`

La app estará en **http://localhost**.

### Migraciones + datos seed
\`\`\`bash
docker compose exec web flask db upgrade
docker compose exec web flask seed
\`\`\`

---

## Flujo de desarrollo
| Acción | Comando |
|--------|---------|
| Hot reload | \`docker compose -f docker-compose.debug.yml up\` |
| Linters | \`ruff check app/\` |
| Migraciones | \`flask db migrate -m "msg"\` |
| Pruebas | \`pytest -q\` |

---

## Pruebas
* **Unitarias**: dominio + servicios con repos stub.  
* **Integración**: Blueprints vs test‑client y BD SQLite in‑mem.

---

## Roadmap
- [ ] UI de notificaciones (M6)
- [ ] Worker Celery para PDFs masivos
- [ ] CI/CD GitHub Actions → GHCR
- [ ] WCAG 2.1 + i18n
- [ ] Helm chart para K8s

---

## Licencia
© TecNM ITCJ – Proyecto académico.
