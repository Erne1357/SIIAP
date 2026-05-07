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

---

## Style Standard (CSS Design System)

**Source of truth:** `app/static/css/_tokens.css` (60+ design tokens) — load order in `base.html` puts tokens after Bootstrap to override its defaults.

### Token files
| File | Purpose |
|------|---------|
| `app/static/css/_tokens.css` | Custom properties: colors, type, spacing, radii, shadows, z-index, motion, layout, breakpoints. Bootstrap overrides too. |
| `app/static/css/base.css` | Layout foundation: `.nav-link`, `.sidebar-section-label`, utilities `w-px-N`, `avatar-md`, `cursor-pointer`, `modal-body-scroll`. |
| `app/static/css/components/` | Reusable BEM components (one file each). |

### Reusable BEM components (from `components/`)
- `.status-badge` + `--{accepted,rejected,deferred,enrolled,deliberation,interview-completed,in-progress,pending,approved}` + `--sm/--lg`
- `.empty-state` + `__icon`, `__title`, `__description`, `__actions` (+ `--compact`)
- `.siiap-table-wrapper` (sticky cols + scroll hint)
- `.stepper` + `__step`, `__number`, `__label` + `--active`, `--completed`
- `.role-banner` + `__avatar`, `__content`, `__greeting`, `__role`, `__next-action`, `__progress`, `__progress-bar`, `__progress-label`
- `.skeleton`, `.skeleton-text`, `.skeleton-avatar`, `.skeleton-card`, `.skeleton-button`, `.skeleton-table`, `.skeleton-row`, `.skeleton-cell` + `--{xs,sm,md,lg,full}`

### Token categories (always reference, never hardcode)
- **Colors:** `--color-brand-{primary,primary-50,primary-100,primary-600,primary-700,accent,accent-600,secondary}`, `--color-{success,warning,danger,info}` + `*-100`, `--color-neutral-{0..900}`. Roles: `--bg-{page,surface,surface-raised,surface-sunken}`, `--border-{default,strong}`, `--text-{primary,secondary,muted,inverse}`. Status: `--status-{in-progress,interview-completed,deliberation,accepted,rejected,deferred,enrolled}`.
- **Type:** `--font-{sans,display,mono}`, `--fs-{xs,sm,base,md,lg,xl,2xl,3xl,display}`, `--fw-{regular,medium,semibold,bold}`, `--lh-{tight,normal,relaxed}`, `--tracking-{tight,normal,wide,display}`.
- **Spacing (8px scale):** `--space-{0,1,2,3,4,5,6,8,10,12,16,20}`.
- **Radii:** `--radius-{xs,sm,md,lg,xl,pill}`.
- **Shadows:** `--shadow-{0,1,2,3,4,5}`, `--shadow-focus`.
- **Z-index:** `--z-{base,dropdown,sticky,fixed,fab,backdrop,offcanvas,modal,popover,tooltip,toast,max}`.
- **Motion:** `--duration-{instant,fast,normal,slow,pulse}`, `--ease-{out,in-out,spring}`.
- **Layout:** `--header-h{,-md,-sm}`, `--sidebar-w`, `--footer-h`, `--content-max-w`, `--content-padding`.
- **Bootstrap utility extensions:** `.bg-{success,warning,danger,info,primary}-soft`, `.text-{warning,success,danger,info,brand-primary,brand-accent}-strong`.

### Hard rules (never break)
1. **No hardcoded colors** in HTML/CSS — use `var(--color-*)`, `var(--text-*)`, `var(--bg-*)`, `var(--border-*)`.
2. **No hardcoded dimensions** in HTML — use `.w-px-N` utility or token-based CSS.
3. **Spacing only via** `var(--space-N)` — no random `padding: 14px`.
4. **Radii only via** `var(--radius-*)`.
5. **Type only via** `--fs-*` / `--fw-*` / `--font-*`.
6. **No `<style>` blocks in templates** — write `app/static/css/<feature>/<page>.css` and link.
7. **No CSS inline** — only `window.*` `<script>` for Jinja2 → JS variables.
8. **BEM for new components:** `.block`, `.block__element`, `.block--modifier` (dashes, not underscores in block name).
9. **Icons:** Bootstrap Icons `<i class="bi bi-*"></i>` — no inline SVG.
10. **Status/badges:** use `.status-badge--*` modifiers — never recolor with ad-hoc utility classes.
11. **Empty states:** `.empty-state` with full subcomponents — no improvising.
12. **Tables:** wrap in `.siiap-table-wrapper`.
13. **Mobile-first:** max-width media queries in component files (576/768/992/1200 px).
14. **WCAG 2.1 AA:** never rely on color alone, min touch target 44px, `:focus-visible` outlines.

### Anti-pattern reminders
- ❌ `<div style="background:#f0f0f0; padding:12px">`  → ✅ `<div class="bg-surface-sunken p-3">` or token-based class.
- ❌ `<span class="badge bg-warning">Pendiente</span>` → ✅ `<span class="status-badge status-badge--pending">Pendiente</span>`.
- ❌ `<style>.my-card { background: #fff; }</style>` in template → ✅ external CSS file using `var(--bg-surface)`.
- ❌ `width: 120px` → ✅ `class="w-px-120"`.

---

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
