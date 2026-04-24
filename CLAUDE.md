# SIIAP — Project Instructions for Claude

## Stack
- **Backend**: Flask 3.x + SQLAlchemy + Flask-Migrate + Flask-Login + Flask-SocketIO
- **Database**: PostgreSQL 15 (Docker service: `db`, host `db`)
- **Task queue**: Celery + Redis
- **Frontend**: Bootstrap 5 + Bootstrap Icons + Vanilla JS (no framework)
- **Container**: Docker Compose

## Language Rules
| Where | Language |
|-------|----------|
| Code: variables, functions, classes, docstrings, comments | **English** |
| UI: labels, headings, flash messages, HTML text, placeholders | **Spanish** |

This matches the existing codebase. Never write UI text in English.

## Running Commands
Always run Flask/DB commands inside the Docker container:
```bash
docker exec siiap-web-1 flask db migrate -m "add_<description>"
docker exec siiap-web-1 flask db upgrade
docker exec siiap-web-1 flask shell
```
The container name may vary — use `docker ps` to confirm.

---

## Project Structure
```
app/
  models/        # SQLAlchemy models — one file per model
  services/      # Business logic — one file per domain
  routes/
    api/         # REST endpoints (url_prefix='/api/v1/<resource>')
    pages/       # HTML page routes
  templates/     # Jinja2 — Bootstrap 5
  static/
    js/          # Vanilla JS, organized by feature
    css/
  utils/         # Shared helpers (permissions, files, datetime, etc.)
  sockets/       # Flask-SocketIO event handlers
database/
  DML/
    permissions/ # 01_permissions.sql — seed for all permission codenames
migrations/
  versions/      # Flask-Migrate generated files
```

---

## API Endpoint Patterns

### Blueprint definition
```python
# app/routes/api/<resource>_api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.permissions import permission_required, any_permission_required
import app.services.<domain>_service as svc

api_<resource> = Blueprint('api_<resource>', __name__, url_prefix='/api/v1/<resource>')
```

### Standard response format — follow exactly
```python
# Success
return jsonify({"data": result, "error": None, "meta": {}}), 200

# Success with count
return jsonify({"data": items, "error": None, "meta": {"count": len(items)}}), 200

# Business error (caught domain exception → 400 or 404)
return jsonify({
    "data": None,
    "flash": [{"level": "warning", "message": str(e)}],
    "error": {"code": "BUSINESS_ERROR", "message": str(e)},
    "meta": {}
}), 400

# Not found
return jsonify({
    "data": None,
    "error": {"code": "NOT_FOUND", "message": str(e)},
    "meta": {}
}), 404

# Server error (unexpected exception → 500)
return jsonify({
    "data": None,
    "error": {"code": "SERVER_ERROR", "message": str(e)},
    "meta": {}
}), 500
```

### Permission decorators
```python
@login_required
@permission_required('resource.api.action')                              # no program scope
@permission_required('resource.api.action', program_id_kwarg='program_id')  # program-scoped
@any_permission_required('perm.one', 'perm.two')                         # at least one
```
- Source: `app/utils/permissions.py`
- Old `@roles_required(...)` is **deprecated** — never use it

### Registering a new Blueprint
Edit `app/routes/api/__init__.py`, add inside `register_api_blueprints()`:
```python
from app.routes.api.<resource>_api import api_<resource>
# then add api_<resource> to the blueprints list
```

### CSRF on mutations
Frontend must send header `X-CSRFToken` on POST/PUT/PATCH/DELETE requests.

---

## Service Patterns

### File skeleton
```python
# app/services/<domain>_service.py
"""
One-paragraph description of the domain and its flow.
"""

from app import db
from app.models import ...
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class <Domain>Error(Exception):
    """Base error for <domain> operations."""

class <Thing>NotFound(<Domain>Error):
    pass

class InvalidStateTransition(<Domain>Error):
    pass
```

### db.session pattern
```python
try:
    db.session.add(obj)
    db.session.commit()
except Exception:
    db.session.rollback()
    raise
```

### History + Notifications — required after every state mutation
```python
UserHistoryService.log_action(
    user_id=target_user.id,
    admin_id=acting_user_id,       # current_user.id passed from route
    action='descriptive_action_name',
    details={'key': 'value'}
)

NotificationService.create_notification(
    user_id=target_user.id,
    notification_type='type_name',
    title='Título en español',
    message='Mensaje en español',
    priority='normal'               # 'low' | 'normal' | 'high'
)
```

### Services must be framework-agnostic
- No `request`, `g`, `current_user` inside services
- Pass user IDs and data as explicit function arguments
- Routes are responsible for extracting context and passing it in

---

## Permission Naming Convention
Format: `{resource}.{type}.{action}`
- **resource**: functional module (`programs`, `acceptance`, `deliberation`, etc.)
- **type**: `api` for REST endpoints · `page` for HTML page routes
- **action**: short verb/description

Examples:
```
acceptance.api.upload_doc
acceptance.api.list_applicants
programs.page.view
admin_users.api.delete
permissions.api.delegate
```

**After defining new permissions**: add the INSERT rows to `database/DML/permissions/01_permissions.sql`.

---

## File Storage
```python
from app.utils.files import save_user_doc

path = save_user_doc(file_obj, user_id, phase)
# Served at: /files/doc/<user_id>/<phase>/<filename>
```
Valid phases: `admission` · `permanence` · `conclusion` · `acceptance`

---

## Migration Workflow
1. Make model changes
2. `docker exec siiap-web-1 flask db migrate -m "add_<what>"`
3. **Review** the generated file in `migrations/versions/` before applying
4. `docker exec siiap-web-1 flask db upgrade`

## Deploy Order (permission system)
After any schema migration that adds tables or after a fresh DB setup:
```bash
docker exec siiap-web-1 flask db upgrade          # 1. apply schema migrations
docker exec siiap-web-1 flask seed-permissions    # 2. populate permission catalog + role mappings
```
Both commands are **idempotent** — safe to re-run on existing data.
When adding a new permission codename: add it to `database/DML/permissions/01_permissions.sql` and re-run `flask seed-permissions`.

---

## Key Models Quick Reference
| Model | Location | Purpose |
|-------|----------|---------|
| `UserProgram` | `models/user_program.py` | Central: user↔program link, `admission_status` |
| `User` | `models/user.py` | Accounts + roles |
| `AcademicPeriod` | `models/academic_period.py` | Enrollment periods |
| `Submission` | `models/submission.py` | Generic document submissions |
| `AcceptanceDocument` | `models/acceptance_document.py` | Acceptance phase docs |
| `SemesterEnrollment` | `models/semester_enrollment.py` | Permanence tracking |
| `Permission` / `RolePermission` / `UserPermission` | `models/permission.py` etc. | Permission system |

### `admission_status` valid values
`in_progress` · `interview_completed` · `deliberation` · `accepted` · `rejected` · `deferred` · `enrolled`

### Roles
`applicant` · `program_admin` · `postgraduate_admin` · `social_service` · `student`

> **Nota:** "coordinator" no es un rol. Es un `program_admin` cuyo id está en `Program.coordinator_id`. Los permisos `coordinator.*` están mapeados al rol `program_admin`.

---

## Anti-patterns — Never Do These
- Business logic in routes — routes call services, that's it
- `Model.query` or `db.session` directly in routes
- `from app.utils.auth import ...` — file deleted, use `app.utils.permissions`
- `@roles_required(...)` — deprecated, use `@permission_required(...)`
- Hardcoded `datetime.now()` — use `now_local()` from `app.utils.datetime_utils`
- Missing `UserHistoryService.log_action()` on any state change
- UI labels or messages in English
- Adding new permissions without updating `01_permissions.sql`
