# 📚 Plan de Implementación: Permanencia Semestral (Fase 6 — Extensión Completa)

> **Fecha de creación:** 24 de Marzo de 2026
> **Sistema:** SIIAP - Sistema Integral de Información Académica de Posgrado
> **Versión:** 1.0
> **Rama:** `feature/academic-periods-system`

---

## 📋 Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Estado Base — Lo que ya existe](#2-estado-base)
3. [Cambios en Archives (Limpieza Previa)](#3-cambios-en-archives)
4. [Módulo A — Referencia Bancaria (Scaffolding)](#4-módulo-a--referencia-bancaria)
5. [Módulo B — Seguimiento Documental Semestral](#5-módulo-b--seguimiento-documental-semestral)
6. [Módulo C — Becarios CONACyT](#6-módulo-c--becarios-conacyt)
7. [Módulo D — Movilidad / Baja Temporal](#7-módulo-d--movilidad--baja-temporal)
8. [Orden de Implementación Recomendado](#8-orden-de-implementación)
9. [Migraciones Necesarias](#9-migraciones-necesarias)
10. [Diagrama de Flujo General](#10-diagrama-de-flujo-general)

---

## 1. Resumen Ejecutivo

Este plan extiende la Fase 6 (Permanencia Semestral) ya implementada para cubrir el ciclo completo de permanencia:

| Módulo | Qué hace | Estado |
|--------|----------|--------|
| A | Referencia bancaria descargable por el estudiante | Scaffolding (listo para integrar algoritmo) |
| B | Documentos de seguimiento semestral con fechas configurables | A implementar |
| C | Seguimiento mensual de becarios CONACyT | A implementar |
| D | Movilidad: Solicitud de Baja Temporal | A implementar |

**Nuevos modelos:** `DocumentDeadline`
**Nuevos campos:** `Archive.is_active`, `UserProgram.has_conacyt_scholarship`, `DocumentTemplate` tipo `payment_reference`
**Extensiones:** `PermanenceService`, `permanence_api.py`, `student_dashboard.html`, `coordinator/permanence.html`

---

## 2. Estado Base

### Lo que ya existe (no tocar salvo extensión)

| Componente | Ubicación | Estado |
|------------|-----------|--------|
| `SemesterEnrollment` model | `app/models/semester_enrollment.py` | ✅ Completo |
| `confirm_semester_enrollment()` | `app/services/permanence_service.py` | ✅ Completo |
| `update_enrollment_status()` | `app/services/permanence_service.py` | ✅ Completo |
| `get_student_permanence()` | `app/services/permanence_service.py` | ✅ Completo |
| `permanence_api.py` (4 endpoints) | `app/routes/api/permanence_api.py` | ✅ Completo |
| `coordinator/permanence.html` | `app/templates/coordinator/permanence.html` | ✅ Completo |
| `student_dashboard.html` (estado inscripción) | `app/templates/user/dashboard/student_dashboard.html` | ✅ Completo |
| `DocumentTemplate` model | `app/models/document_template.py` | ✅ Completo (se extiende para Módulo A) |
| `Submission` model (con `semester`, `academic_period_id`, `deadline_at`) | `app/models/submission.py` | ✅ Reutilizable |

### Pasos y archives relevantes (permanencia)

```
Step 9  — Permanencia          (phase_id=2)
Step 10 — Movilidad            (phase_id=2)
Step 11 — Seguimiento Semestral (phase_id=2)  [no usado actualmente]
Step 12 — Becarios CONACyT     (phase_id=2)
```

---

## 3. Cambios en Archives

### 3.1 Problema

Los archives de Step 9 incluyen 4 documentos que ya NO se quieren solicitar a los estudiantes:
- Mapa Curricular
- Programación de Materias / Tira de Materias
- Boleta de Inscripción/Reinscripción
- Boleta de Calificación Firmada/Sellada

No se pueden **eliminar** de la BD porque puede haber submissions históricas referenciadas. Se deben **desactivar**.

También, el "Reporte de Retroalimentación Semestral" tiene `is_uploadable=FALSE` actualmente, lo que es incorrecto.

### 3.2 Nuevo campo en `Archive`

```python
# app/models/archive.py — agregar campo:
is_active = db.Column(db.Boolean, default=True, nullable=False)
```

Actualizar `to_dict()` para incluirlo.

### 3.3 Migración de datos

```sql
-- Desactivar los 4 archives obsoletos de Step 9
-- (identificados por nombre + step_id=9)
UPDATE archive SET is_active = FALSE
WHERE step_id = 9
  AND name IN (
    'Mapa Curricular',
    'Programación de Materias',
    'Boleta de Inscripción',
    'Boleta de Calificación Firmada/Sellada'
  );

-- Corregir Reporte de Retroalimentación
UPDATE archive SET is_uploadable = TRUE
WHERE step_id = 9 AND name = 'Reporte de Retroalimentación';
```

### 3.4 Archives activos resultantes por step

**Step 9 (Permanencia) — activos:**
| # | Nombre | Descargable | Subible | Notas |
|---|--------|------------|---------|-------|
| 5 | Reporte de Retroalimentación Semestral | No | Sí | 1 en Maestría, 2 en Doctorado |
| 6 | Solicitud de Baja Temporal | Sí (plantilla) | Sí | Módulo D |
| 7 | Carta del Director | Sí | Sí | |

**Step 10 (Movilidad) — activos:**
| # | Nombre | Descargable | Subible |
|---|--------|------------|---------|
| 8 | Carta Solicitud | Sí | Sí |
| 9 | Carta de Aceptación | Sí | Sí |
| 10 | Carta de Terminación | Sí | Sí |
| 11 | Informe Final | No | Sí |

**Step 12 (Becarios CONACyT) — activos:**
| # | Nombre | Descargable | Subible |
|---|--------|------------|---------|
| 16 | Formato de Desempeño | Sí | Sí |

---

## 4. Módulo A — Referencia Bancaria

### 4.1 Objetivo

Permitir que el estudiante descargue su referencia bancaria generada por el sistema antes de ir a pagar cada semestre. El algoritmo de generación se integrará cuando esté disponible. Este módulo deja todo el scaffolding listo.

### 4.2 Cambios en `DocumentTemplate`

Agregar el tipo `payment_reference` al diccionario `DOCUMENT_TYPES`:

```python
# app/models/document_template.py
DOCUMENT_TYPES = {
    'acceptance_letter':        'Carta de Aceptación',
    'enrollment_confirmation':  'Confirmación de Inscripción',
    'course_schedule':          'Tira de Materias',
    'payment_reference':        'Referencia Bancaria de Pago',   # NUEVO
}
```

Variables adicionales disponibles para plantillas de tipo `payment_reference`:
```
{{student_name}}, {{control_number}}, {{program_name}},
{{period_name}}, {{period_code}}, {{semester_number}},
{{payment_amount}}, {{payment_reference}}, {{due_date}}
```

### 4.3 Nuevo Servicio (Stub)

```python
# app/services/payment_reference_service.py
"""
Servicio para generar referencias bancarias de pago semestral.

PENDIENTE: Integrar el algoritmo de generación de número de referencia
del sistema existente. El stub retorna un error controlado si no hay
plantilla configurada, permitiendo al estudiante ver la UI aunque
la funcionalidad aún no esté activada.
"""

from app.models import UserProgram
from app.models.document_template import DocumentTemplate
from app.models.academic_period import AcademicPeriod
from app.models.semester_enrollment import SemesterEnrollment


class PaymentReferenceNotConfigured(Exception):
    """No hay plantilla de referencia bancaria configurada para este programa."""
    pass


def generate_payment_reference_number(user_id: int, program_id: int,
                                       period_code: str) -> str:
    """
    TODO: Integrar aquí el algoritmo de generación de número de referencia.
    Por ahora lanza NotImplementedError.

    El algoritmo existente en la otra página debe adaptarse para recibir:
    - user_id o control_number
    - program_id
    - period_code (ej: '20261')

    Y retornar un string con el número de referencia de pago único.
    """
    raise NotImplementedError(
        "El algoritmo de generación de referencia bancaria aún no ha sido integrado. "
        "Ver PLAN_PERMANENCIA.md Módulo A."
    )


def get_payment_reference_for_student(user_program_id: int) -> dict:
    """
    Retorna la información de referencia bancaria para el estudiante.

    Returns:
        {
          'configured': bool,
          'file_url': str or None,
          'template_name': str or None,
          'error': str or None
        }

    Si no hay plantilla configurada, retorna configured=False sin lanzar excepción,
    para que el frontend muestre el estado adecuado al estudiante.
    """
    from app.models.user_program import UserProgram
    from app.models.user import User

    up = UserProgram.query.get(user_program_id)
    if not up:
        return {'configured': False, 'file_url': None,
                'template_name': None, 'error': 'UserProgram no encontrado'}

    template = DocumentTemplate.get_for_program(
        program_id=up.program_id,
        document_type='payment_reference'
    )

    if not template:
        return {
            'configured': False,
            'file_url': None,
            'template_name': None,
            'error': 'No hay plantilla de referencia bancaria configurada para este programa.'
        }

    # TODO: Cuando el algoritmo esté disponible, descomentar y completar:
    # try:
    #     active_period = AcademicPeriod.get_active_period()
    #     ref_number = generate_payment_reference_number(
    #         user_id=up.user_id,
    #         program_id=up.program_id,
    #         period_code=active_period.code
    #     )
    #     file_path = _generate_pdf(template, up, ref_number, active_period)
    #     return {'configured': True, 'file_url': f'/files/doc/{file_path}', ...}
    # except NotImplementedError:
    #     pass

    return {
        'configured': True,  # plantilla existe, pero algoritmo pendiente
        'file_url': None,
        'template_name': template.name,
        'error': 'La generación automática de referencias estará disponible próximamente.'
    }
```

### 4.4 Endpoint API (Stub)

```python
# En permanence_api.py — agregar:

@api_permanence.get('/user-program/<int:user_program_id>/payment-reference')
@login_required
def api_get_payment_reference(user_program_id):
    """
    Retorna la referencia bancaria del estudiante para el periodo activo.
    Si no está configurada, retorna configured=False (no es error HTTP).
    """
    from app.services.payment_reference_service import get_payment_reference_for_student
    from app.models import UserProgram

    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({"data": None,
                        "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"},
                        "meta": {}}), 404

    # Solo el propio estudiante o coordinadores pueden ver
    if current_user.id != up.user_id:
        if not hasattr(current_user, 'role') or current_user.role.name not in (
            'coordinator', 'program_admin', 'postgraduate_admin'
        ):
            return jsonify({"data": None,
                            "error": {"code": "FORBIDDEN", "message": "Sin permiso"},
                            "meta": {}}), 403

    data = get_payment_reference_for_student(user_program_id)
    return jsonify({"data": data, "error": None, "meta": {}}), 200
```

### 4.5 Vista del Estudiante (Bloque en Dashboard)

```html
{# En student_dashboard.html — nueva tarjeta de Referencia Bancaria #}
<div class="card mb-4">
  <div class="card-header d-flex align-items-center gap-2">
    <i class="bi bi-bank text-success"></i>
    <strong>Referencia Bancaria</strong>
    <span class="badge bg-secondary ms-auto">{{ permanence_data.current_period.name if permanence_data and permanence_data.current_period else 'Sin periodo' }}</span>
  </div>
  <div class="card-body">
    <div id="payment-ref-container">
      <div class="text-center py-2 text-muted small">
        <i class="bi bi-hourglass-split"></i> Verificando referencia...
      </div>
    </div>
  </div>
</div>
```

El JS hace `GET /api/v1/permanence/user-program/{id}/payment-reference` y muestra:
- Si `configured=False`: Alerta informativa "Tu referencia bancaria no está configurada aún. Contacta al coordinador."
- Si `configured=True` y `file_url`: Botón de descarga.
- Si `configured=True` y `file_url=null` (pendiente algoritmo): Mensaje "La generación de referencias estará disponible próximamente."

---

## 5. Módulo B — Seguimiento Documental Semestral

### 5.1 Objetivo

Permitir que el coordinador **abra y cierre ventanas de entrega** de documentos de permanencia por periodo, y que los estudiantes suban sus documentos dentro de esas ventanas. El coordinador revisa y aprueba/rechaza.

### 5.2 Lógica de los Reportes de Avance (1 vs 2)

| Nivel del Programa | Entregas por Semestre | Cómo se implementa |
|---|---|---|
| Maestría | 1 | Coordinador crea 1 `DocumentDeadline` para el Reporte, con `sequence=1` |
| Doctorado | 2 | Coordinador crea 2 `DocumentDeadline` para el Reporte, con `sequence=1` y `sequence=2` |

El coordinador sabe cuántas crear según el nivel del programa (`Program.program_level`). La UI del coordinador puede sugerir el número correcto.

### 5.3 Nuevo Modelo `DocumentDeadline`

```python
# app/models/document_deadline.py
"""
Ventana de entrega de un documento de permanencia.

El coordinador crea estas ventanas por cada documento que requiere
entrega en un periodo académico. Puede haber múltiples ventanas
para el mismo archivo en el mismo periodo (ej: 2 reportes de avance
para doctorado, ventanas mensuales para CONACyT).
"""

from app import db
from app.utils.datetime_utils import now_local


class DocumentDeadline(db.Model):
    __tablename__ = 'document_deadline'

    id = db.Column(db.Integer, primary_key=True)

    # Qué documento y para qué programa
    archive_id = db.Column(db.Integer, db.ForeignKey('archive.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'), nullable=False)

    # Para distinguir 1er y 2do reporte (Doctorado) o mes de entrega (CONACyT)
    # Ejemplos: 1, 2 (reportes) | 1-12 (meses para CONACyT)
    sequence = db.Column(db.Integer, default=1, nullable=False)

    # Etiqueta descriptiva mostrada al estudiante
    # Ejemplos: "1er Reporte Semestral", "2do Reporte Semestral",
    #            "Formato CONACyT — Enero", "Formato CONACyT — Febrero"
    label = db.Column(db.String(100), nullable=False)

    # Ventana de entrega
    opens_at = db.Column(db.DateTime, nullable=True)   # NULL = ya abierta
    closes_at = db.Column(db.DateTime, nullable=True)  # NULL = sin fecha límite

    # Control manual del coordinador (puede anular las fechas)
    is_open = db.Column(db.Boolean, default=True, nullable=False)

    # Quién lo creó
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    # Relaciones
    archive = db.relationship('Archive', backref=db.backref('deadlines', lazy='dynamic'))
    program = db.relationship('Program', backref=db.backref('document_deadlines', lazy='dynamic'))
    academic_period = db.relationship('AcademicPeriod',
                                       backref=db.backref('document_deadlines', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def is_currently_open(self) -> bool:
        """
        La ventana está abierta si:
        1. is_open=True (control manual)
        2. Y si hay fechas, la fecha actual está dentro del rango.
        """
        from app.utils.datetime_utils import now_local as _now
        if not self.is_open:
            return False
        now = _now()
        if self.opens_at and now < self.opens_at:
            return False
        if self.closes_at and now > self.closes_at:
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'archive_id': self.archive_id,
            'archive_name': self.archive.name if self.archive else None,
            'program_id': self.program_id,
            'academic_period_id': self.academic_period_id,
            'sequence': self.sequence,
            'label': self.label,
            'opens_at': self.opens_at.isoformat() if self.opens_at else None,
            'closes_at': self.closes_at.isoformat() if self.closes_at else None,
            'is_open': self.is_open,
            'is_currently_open': self.is_currently_open,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
```

### 5.4 Vincular Submission a DocumentDeadline

Agregar campo a `Submission`:

```python
# app/models/submission.py — agregar campo:
document_deadline_id = db.Column(
    db.Integer, db.ForeignKey('document_deadline.id'), nullable=True
)
document_deadline = db.relationship('DocumentDeadline',
                                     backref=db.backref('submissions', lazy='dynamic'))
```

Este campo solo se llena para submissions de permanencia con ventana definida. Submissions de admisión lo dejan en NULL.

### 5.5 Extensión de `PermanenceService`

```python
# app/services/permanence_service.py — funciones nuevas a agregar:

def get_student_documents_for_period(user_program_id: int) -> list:
    """
    Obtiene las ventanas de entrega activas para el estudiante en el periodo activo,
    con el estado de su submission para cada una.

    Returns:
        [
          {
            'deadline': {...},        # DocumentDeadline.to_dict()
            'archive': {...},         # Archive.to_dict()
            'submission': {...}|None  # Submission.to_dict() o None si no ha subido
          },
          ...
        ]
    """
    from app.models.document_deadline import DocumentDeadline
    from app.models.archive import Archive
    from app.models.submission import Submission

    up = UserProgram.query.get(user_program_id)
    if not up:
        raise StudentNotFound(f"UserProgram {user_program_id} no encontrado")

    active_period = AcademicPeriod.get_active_period()
    if not active_period:
        return []

    deadlines = DocumentDeadline.query.filter_by(
        program_id=up.program_id,
        academic_period_id=active_period.id,
    ).join(Archive, DocumentDeadline.archive_id == Archive.id).filter(
        Archive.is_active == True
    ).order_by(DocumentDeadline.sequence).all()

    result = []
    for dl in deadlines:
        # Buscar submission del estudiante para esta ventana
        sub = Submission.query.filter_by(
            user_id=up.user_id,
            document_deadline_id=dl.id,
        ).order_by(Submission.upload_date.desc()).first()

        result.append({
            'deadline': dl.to_dict(),
            'archive': dl.archive.to_dict(),
            'submission': sub.to_dict() if sub else None,
        })

    return result


def submit_permanence_document(user_program_id: int, document_deadline_id: int,
                                file_storage, student_id: int) -> dict:
    """
    El estudiante sube un documento para una ventana de entrega activa.
    Usa el modelo Submission existente.
    """
    from app.models.document_deadline import DocumentDeadline
    from app.models.submission import Submission
    from app.utils.files import save_user_doc

    up = UserProgram.query.get(user_program_id)
    if not up or up.user_id != student_id:
        raise StudentNotFound("UserProgram no encontrado o no pertenece al estudiante")

    dl = DocumentDeadline.query.get(document_deadline_id)
    if not dl:
        raise StudentNotFound(f"Ventana de entrega {document_deadline_id} no encontrada")

    if not dl.is_currently_open:
        raise InvalidStateTransition(
            f"La ventana de entrega '{dl.label}' está cerrada. No se puede subir el documento."
        )

    # Verificar que la ventana pertenece al programa del estudiante
    if dl.program_id != up.program_id:
        raise InvalidStateTransition("Esta ventana de entrega no corresponde a tu programa")

    # Buscar ProgramStep para permanencia
    from app.models.program_step import ProgramStep
    program_step = ProgramStep.query.filter_by(
        program_id=up.program_id,
        step_id=dl.archive.step_id
    ).first()
    if not program_step:
        raise InvalidStateTransition("El documento no está configurado para este programa")

    file_path = save_user_doc(file_storage, up.user_id, 'permanence', dl.archive.name)

    # Verificar si ya existe una submission para esta ventana
    existing = Submission.query.filter_by(
        user_id=up.user_id,
        document_deadline_id=dl.id,
        status='review'
    ).first()
    if existing:
        raise InvalidStateTransition(
            "Ya tienes un documento en revisión para esta ventana. Espera a que sea revisado."
        )

    sub = Submission(
        file_path=file_path,
        status='review',
        user_id=up.user_id,
        archive_id=dl.archive_id,
        program_step_id=program_step.id,
        semester=up.current_semester,
        uploaded_by=student_id,
        uploaded_by_role='student',
        deadline_at=dl.closes_at,
    )
    sub.document_deadline_id = dl.id
    sub.academic_period_id = dl.academic_period_id
    db.session.add(sub)

    UserHistoryService.log_action(
        user_id=student_id,
        admin_id=student_id,
        action='permanence_document_submitted',
        details=f'Subió "{dl.archive.name}" ({dl.label}) — Semestre {up.current_semester}'
    )

    db.session.commit()
    return sub.to_dict()


def review_permanence_document(submission_id: int, coordinator_id: int,
                                status: str, notes: str = None) -> dict:
    """
    El coordinador aprueba o rechaza un documento de permanencia.
    status: 'approved' o 'rejected'
    """
    from app.models.submission import Submission
    from app.utils.datetime_utils import now_local

    if status not in ('approved', 'rejected'):
        raise ValueError("status debe ser 'approved' o 'rejected'")

    sub = Submission.query.get(submission_id)
    if not sub:
        raise StudentNotFound(f"Submission {submission_id} no encontrada")

    if sub.status != 'review':
        raise InvalidStateTransition(
            f"Solo submissions en estado 'review' pueden revisarse. Estado: '{sub.status}'"
        )

    sub.status = status
    sub.reviewer_id = coordinator_id
    sub.review_date = now_local()
    sub.reviewer_comment = notes

    up = sub.user.user_program[0]  # Simplificado; ajustar según estructura real
    dl_label = sub.document_deadline.label if sub.document_deadline else sub.archive.name

    if status == 'approved':
        NotificationService.create_notification(
            user_id=sub.user_id,
            notification_type='permanence_doc_approved',
            title=f'Documento aprobado — {dl_label}',
            message=f'Tu documento "{dl_label}" fue aprobado para el periodo actual.',
            priority='medium',
            action_url='/user/dashboard',
        )
    else:
        NotificationService.create_notification(
            user_id=sub.user_id,
            notification_type='permanence_doc_rejected',
            title=f'Documento rechazado — {dl_label}',
            message=(
                f'Tu documento "{dl_label}" fue rechazado. '
                f'Motivo: {notes or "Sin especificar"}. Vuelve a subirlo cuando la ventana esté abierta.'
            ),
            priority='high',
            action_url='/user/dashboard',
        )

    UserHistoryService.log_action(
        user_id=sub.user_id,
        admin_id=coordinator_id,
        action=f'permanence_document_{status}',
        details=f'{"Aprobó" if status == "approved" else "Rechazó"} "{dl_label}" — {notes or ""}'
    )

    db.session.commit()
    return sub.to_dict()


def create_document_deadline(program_id: int, archive_id: int,
                              academic_period_id: int, label: str,
                              sequence: int = 1, opens_at=None,
                              closes_at=None, coordinator_id: int = None) -> 'DocumentDeadline':
    """
    El coordinador crea una ventana de entrega para un documento en un periodo.
    """
    from app.models.document_deadline import DocumentDeadline
    from app.models.archive import Archive

    archive = Archive.query.get(archive_id)
    if not archive or not archive.is_active:
        raise ValueError(f"Archive {archive_id} no encontrado o inactivo")

    dl = DocumentDeadline(
        archive_id=archive_id,
        program_id=program_id,
        academic_period_id=academic_period_id,
        sequence=sequence,
        label=label,
        opens_at=opens_at,
        closes_at=closes_at,
        is_open=True,
        created_by=coordinator_id,
    )
    db.session.add(dl)
    db.session.commit()
    return dl


def toggle_document_deadline(deadline_id: int, is_open: bool,
                              coordinator_id: int) -> 'DocumentDeadline':
    """
    El coordinador abre o cierra manualmente una ventana de entrega.
    """
    from app.models.document_deadline import DocumentDeadline

    dl = DocumentDeadline.query.get(deadline_id)
    if not dl:
        raise StudentNotFound(f"Ventana {deadline_id} no encontrada")

    dl.is_open = is_open
    action = 'deadline_opened' if is_open else 'deadline_closed'
    UserHistoryService.log_action(
        user_id=coordinator_id,
        admin_id=coordinator_id,
        action=action,
        details=f'{"Abrió" if is_open else "Cerró"} ventana "{dl.label}" del periodo {dl.academic_period_id}'
    )
    db.session.commit()
    return dl
```

### 5.6 Nuevos Endpoints API

```python
# En permanence_api.py — agregar:

# ── Ventanas de entrega (Coordinador) ────────────────────────────────────────

@api_permanence.get('/program/<int:program_id>/deadlines')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_deadlines(program_id):
    """Lista todas las ventanas de entrega del periodo activo para un programa."""
    # ...

@api_permanence.post('/program/<int:program_id>/deadlines')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_create_deadline(program_id):
    """Crea una ventana de entrega. Body: {archive_id, label, sequence, opens_at, closes_at}"""
    # ...

@api_permanence.patch('/deadlines/<int:deadline_id>/toggle')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_toggle_deadline(deadline_id):
    """Abre/cierra manualmente una ventana. Body: {is_open: bool}"""
    # ...

@api_permanence.delete('/deadlines/<int:deadline_id>')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_delete_deadline(deadline_id):
    """Elimina una ventana (solo si no tiene submissions)."""
    # ...

# ── Documentos de permanencia (Estudiante) ───────────────────────────────────

@api_permanence.get('/user-program/<int:user_program_id>/documents')
@login_required
def api_get_student_documents(user_program_id):
    """Lista ventanas y estado de submission del estudiante en el periodo activo."""
    # ...

@api_permanence.post('/user-program/<int:user_program_id>/documents/<int:deadline_id>')
@login_required
def api_submit_permanence_document(user_program_id, deadline_id):
    """El estudiante sube un documento. Multipart/form-data con field 'file'."""
    # ...

# ── Revisión de documentos (Coordinador) ─────────────────────────────────────

@api_permanence.get('/program/<int:program_id>/pending-documents')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_pending_documents(program_id):
    """Lista submissions de permanencia en estado 'review' para el programa."""
    # ...

@api_permanence.post('/submissions/<int:submission_id>/review')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_review_permanence_document(submission_id):
    """Aprueba o rechaza un documento. Body: {status: 'approved'|'rejected', notes: str}"""
    # ...
```

### 5.7 Vista del Estudiante — Sección "Documentos del Semestre"

```
┌──────────────────────────────────────────────────────────────────┐
│ 📄 Documentos del Semestre               Ene-Jun 2026            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1er Reporte Semestral                    Cierra: 15/03/2026     │
│  Reporte de Retroalimentación Comité                             │
│  Estado: ⏳ Pendiente            [ Subir documento ]             │
│                                                                  │
│  ──────────────────────────────────────────────────────────────  │
│                                                                  │
│  Carta del Director                       Cierra: 30/04/2026     │
│  Carta del Director de Tesis Similitud <30%                      │
│  Estado: ✅ Aprobado             [ Ver documento ]               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Estado de cada ventana:
- Sin submission + ventana abierta → botón "Subir"
- Submission en `review` → badge "En revisión" (sin botón)
- Submission `rejected` + ventana abierta → badge "Rechazado" + botón "Volver a subir"
- Submission `approved` → badge "Aprobado" + enlace "Ver"
- Ventana cerrada + sin submission → badge "Ventana cerrada"

### 5.8 Vista del Coordinador — Pestañas implementadas

`coordinator/permanence.html` tiene **2 tabs**: "Estudiantes" y "Ventanas de Entrega".

**Tab "Ventanas de Entrega":**

```
┌──────────────────────────────────────────────────────────────────┐
│ Gestión de Ventanas de Entrega                   [+ Nueva Ventana]│
├──────────────────────────────────────────────────────────────────┤
│  📋 1er Reporte Semestral       🟢 Abierta  Cierra: 15/03  [🔒][🗑]│
│     12 entregas · 3 ✓                                            │
│     ── 3 entregas por revisar ─────────────────────────────────  │
│     Juan Pérez M26111001   25/02  [👁] [✅] [❌]                 │
│     María López M26111002  01/03  [👁] [✅] [❌]                 │
│     ...                                                          │
│                                                                  │
│  📋 Formato CONACyT — Enero     🔴 Cerrada                [🔓][🗑]│
│     8 entregas · 8 ✓                                             │
└──────────────────────────────────────────────────────────────────┘
```

> **Decisión de diseño (v1.1):** Se descartó una pestaña "Revisión de Docs" separada para no
> duplicar la infraestructura de `admin/review/`. Las submissions pendientes aparecen **inline**
> dentro de la tarjeta de su ventana. Al aprobar/rechazar se recarga solo la sección de ventanas.

**Modal "Nueva Ventana":**
- Select: Archive (activos de `phase_id=2`, pasados desde `coordinator_pages.py`)
- Input: Etiqueta descriptiva (auto-sugerida del nombre del archive)
- Input: Fecha de apertura (opcional; vacío = abierta desde ya)
- Input: Fecha de cierre (opcional)
- Input: Secuencia (1 para Maestría, 1 o 2 para Doctorado)
- Select: Periodo académico (por defecto el activo)
- Hint contextual según `Program.program_level`

---

## 6. Módulo C — Becarios CONACyT

### 6.1 Objetivo

El Formato de Desempeño (Step 12) solo aplica a estudiantes con beca CONACyT. El coordinador marca quién es becario. Las entregas mensuales se gestionan igual que el Módulo B, usando `DocumentDeadline` con secuencias mensuales.

### 6.2 Nuevo Campo en `UserProgram`

```python
# app/models/user_program.py — agregar:
has_conacyt_scholarship = db.Column(db.Boolean, default=False, nullable=False)
```

Actualizar `to_dict()` para incluirlo.

### 6.3 Endpoint para Marcar Becario

```python
# En permanence_api.py — agregar:

@api_permanence.patch('/user-program/<int:user_program_id>/conacyt-scholarship')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_toggle_conacyt_scholarship(user_program_id):
    """
    Activa o desactiva el flag de beca CONACyT para un estudiante.
    Body: { "has_scholarship": true|false }
    """
    from app.models import UserProgram
    data = request.get_json() or {}
    has_scholarship = data.get('has_scholarship')

    if has_scholarship is None:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Falta el campo has_scholarship"}],
            "error": {"code": "MISSING_FIELD", "message": "has_scholarship es requerido"},
            "meta": {}
        }), 400

    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({...}), 404

    up.has_conacyt_scholarship = bool(has_scholarship)
    from app import db
    db.session.commit()

    from app.services.user_history_service import UserHistoryService
    action = 'conacyt_scholarship_enabled' if has_scholarship else 'conacyt_scholarship_disabled'
    UserHistoryService.log_action(
        user_id=up.user_id,
        admin_id=current_user.id,
        action=action,
        details=f'{"Habilitó" if has_scholarship else "Deshabilitó"} beca CONACyT para el estudiante'
    )

    return jsonify({
        "data": {"has_conacyt_scholarship": up.has_conacyt_scholarship},
        "flash": [{"level": "success",
                   "message": f'Beca CONACyT {"habilitada" if has_scholarship else "deshabilitada"}'}],
        "error": None,
        "meta": {}
    }), 200
```

### 6.4 Ventanas Mensuales CONACyT

El coordinador crea ventanas usando el mismo `DocumentDeadline`, pero referenciando el archivo "Formato de Desempeño" (Step 12) con secuencias 1–12 (mes del año) y etiquetas como "Formato CONACyT — Enero 2026".

**Sugerencia de UI para el coordinador:** botón "Crear ventanas mensuales para CONACyT" que genere automáticamente las 6 ventanas del semestre activo con fechas sugeridas (último día de cada mes).

### 6.5 Filtrado en Dashboard del Estudiante

En `get_student_documents_for_period()`:

```python
# Dentro del query de deadlines, filtrar:
# Si el deadline es de Step 12 (CONACyT), solo incluirlo si el estudiante es becario
deadlines_to_show = []
for dl in deadlines:
    if dl.archive.step_id == 12:  # Step 12 = Becarios CONACyT
        if not up.has_conacyt_scholarship:
            continue  # Omitir si no es becario
    deadlines_to_show.append(dl)
```

### 6.6 Vista del Coordinador — Sección CONACyT

En la pestaña de estudiantes, agregar toggle de beca CONACyT por estudiante:

```
┌────────────────────────────────────────────────────────────────────┐
│  M26111001 - Juan Pérez     Sem 2     CONACyT: [🟢 Becario] [Off] │
│  M26111002 - María López    Sem 2     CONACyT: [⚪ No becario] [On]│
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. Módulo D — Movilidad / Baja Temporal

### 7.1 Objetivo

Flujo simple: el estudiante solicita baja temporal subiendo el documento del Archive "Solicitud de Baja Temporal" (Step 9). El coordinador lo revisa y aprueba o rechaza. Si aprueba, el `SemesterEnrollment` pasa a `on_leave`.

### 7.2 Flujo

```
Estudiante sube            Coordinador revisa
"Solicitud de Baja"   →   [Aprobar] → SemesterEnrollment.status = 'on_leave'
(Submission review)        [Rechazar] → Notificación al estudiante
```

La baja temporal **no** requiere un nuevo modelo. Se identifica por el `archive_id` correspondiente a "Solicitud de Baja Temporal".

### 7.3 Función en `PermanenceService`

```python
def process_leave_request(submission_id: int, coordinator_id: int,
                           approve: bool, notes: str = None) -> dict:
    """
    El coordinador aprueba o rechaza una solicitud de baja temporal.

    Si se aprueba:
    - El submission pasa a 'approved'
    - El SemesterEnrollment activo del estudiante pasa a 'on_leave'

    Si se rechaza:
    - El submission pasa a 'rejected'
    - Notificación al estudiante con el motivo
    """
    from app.models.submission import Submission

    sub = Submission.query.get(submission_id)
    if not sub:
        raise StudentNotFound(f"Submission {submission_id} no encontrada")

    # Verificar que es una solicitud de baja temporal
    if 'baja temporal' not in sub.archive.name.lower():
        raise InvalidStateTransition("Este documento no es una solicitud de baja temporal")

    if sub.status != 'review':
        raise InvalidStateTransition("Solo solicitudes en estado 'review' pueden procesarse")

    sub.status = 'approved' if approve else 'rejected'
    sub.reviewer_id = coordinator_id
    sub.review_date = now_local()
    sub.reviewer_comment = notes

    if approve:
        # Buscar SemesterEnrollment activo del estudiante
        up = UserProgram.query.filter_by(user_id=sub.user_id).first()
        if up:
            active_se = SemesterEnrollment.query.filter_by(
                user_program_id=up.id,
                status='active'
            ).first()
            if active_se:
                active_se.status = 'on_leave'

        NotificationService.create_notification(
            user_id=sub.user_id,
            notification_type='leave_request_approved',
            title='Baja temporal aprobada',
            message='Tu solicitud de baja temporal fue aprobada. Tu estado se actualizó a baja temporal.',
            priority='high',
            action_url='/user/dashboard',
        )
    else:
        NotificationService.create_notification(
            user_id=sub.user_id,
            notification_type='leave_request_rejected',
            title='Baja temporal rechazada',
            message=f'Tu solicitud de baja temporal fue rechazada. Motivo: {notes or "Sin especificar"}.',
            priority='high',
            action_url='/user/dashboard',
        )

    UserHistoryService.log_action(
        user_id=sub.user_id,
        admin_id=coordinator_id,
        action='leave_request_approved' if approve else 'leave_request_rejected',
        details=f'{"Aprobó" if approve else "Rechazó"} solicitud de baja temporal. {notes or ""}'
    )

    db.session.commit()

    return {
        'submission': sub.to_dict(),
        'new_enrollment_status': 'on_leave' if approve else None,
    }
```

### 7.4 Endpoint API

```python
# En permanence_api.py — agregar:

@api_permanence.post('/submissions/<int:submission_id>/leave-request')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_process_leave_request(submission_id):
    """
    Aprueba o rechaza una solicitud de baja temporal.
    Body: { "approve": true|false, "notes": str }
    """
    data = request.get_json() or {}
    approve = data.get('approve')
    notes = (data.get('notes') or '').strip() or None

    if approve is None:
        return jsonify({...}), 400

    try:
        result = svc.process_leave_request(
            submission_id=submission_id,
            coordinator_id=current_user.id,
            approve=bool(approve),
            notes=notes
        )
        action = "aprobada" if approve else "rechazada"
        return jsonify({
            "data": result,
            "flash": [{"level": "success", "message": f"Solicitud de baja temporal {action}"}],
            "error": None,
            "meta": {}
        }), 200
    except (svc.StudentNotFound, svc.InvalidStateTransition) as e:
        return jsonify({...}), 400
    except Exception as e:
        return jsonify({...}), 500
```

### 7.5 Vista del Coordinador — Pestaña "Solicitudes de Movilidad"

```
┌──────────────────────────────────────────────────────────────────┐
│ Solicitudes de Baja Temporal          Periodo: Ene-Jun 2026      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  M26111003 - Carlos Ruiz     Sem 3     Subida: 10/03/2026        │
│  [Ver solicitud]  [✅ Aprobar baja]  [❌ Rechazar]               │
│                                                                  │
│  ─── Sin más solicitudes pendientes ──────────────────────────── │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 7.6 Vista del Estudiante — Sección Movilidad

En el dashboard del estudiante, si el estudiante tiene `SemesterEnrollment.status='on_leave'`:

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠️ Estado: Baja Temporal                                         │
│ Tu solicitud de baja temporal fue aprobada para este periodo.    │
│ Para reincorporarte, contacta al coordinador.                    │
└──────────────────────────────────────────────────────────────────┘
```

Si el estudiante quiere solicitar baja temporal, el formulario de upload de "Solicitud de Baja Temporal" aparece como un documento especial (no vinculado a DocumentDeadline, sino siempre disponible si el step está activo en el programa).

---

## 8. Orden de Implementación

### Iteración 1 — Limpieza y Base (sin UI nueva) ✅
1. Migración: `Archive.is_active` campo nuevo
2. Script SQL: desactivar 4 archives obsoletos, corregir `is_uploadable` del Reporte
3. Migración: `UserProgram.has_conacyt_scholarship`
4. Registrar nuevo tipo `payment_reference` en `DocumentTemplate`
5. Endpoint `PATCH /user-program/{id}/conacyt-scholarship` (implementado junto con el modelo)

### Iteración 2 — Modelo DocumentDeadline ✅
1. Modelo `DocumentDeadline` (`app/models/document_deadline.py`)
2. Migración `6n4r6s7t8u9v_add_document_deadline.py`
3. Campo `Submission.document_deadline_id` + migración `7o5s7t8u9v0w_add_submission_deadline_fk.py`
4. Registrar en `app/models/__init__.py`

### Iteración 3 — Seguimiento Documental (Módulo B) ✅
1. Funciones en `permanence_service.py`:
   - `get_deadlines_for_program()`, `create_document_deadline()`, `toggle_document_deadline()`, `delete_document_deadline()`
   - `get_student_documents_for_period()` (con filtro CONACyT step_id=12 incluido)
   - `submit_permanence_document()`, `get_pending_documents()`, `review_permanence_document()`
2. Endpoints en `permanence_api.py`: GET/POST deadlines, toggle, delete, GET/POST documents, pending-documents, review
3. UI coordinador: 2 tabs (Estudiantes + Ventanas de Entrega); columna CONACyT toggle en tab Estudiantes
4. UI coordinador: revisión de docs **integrada dentro de cada tarjeta de ventana** (no tab separado)
   - Decisión de diseño: se descartó la pestaña "Revisión de Docs" separada para evitar duplicar
     la infraestructura de `admin/review/`. Las submissions pendientes aparecen inline en la
     tarjeta de su ventana correspondiente. Al aprobar/rechazar, la tarjeta se recarga.
5. UI del estudiante: sección "Documentos del Semestre" con upload inline por ventana
6. `coordinator_pages.py`: pasa `permanence_archives` (archives activos phase_id=2) al template

### Iteración 4 — CONACyT (Módulo C) ✅
1. ~~Endpoint PATCH conacyt-scholarship~~ (ya hecho en Iter. 1)
2. ~~Filtrado CONACyT en `get_student_documents_for_period()`~~ (ya hecho en Iter. 3)
3. ~~Toggle CONACyT en vista de coordinador~~ (ya hecho en Iter. 3)
4. **Pendiente:** Botón "Crear ventanas mensuales CONACyT" en UI coordinador
   (genera 6 DocumentDeadline de una vez con fechas del último día de cada mes del semestre)

### Iteración 5 — Movilidad / Baja Temporal (Módulo D) ✅
1. `process_leave_request()` en `permanence_service.py`
2. Endpoint `POST /submissions/{id}/leave-request`
3. Sección "Baja Temporal" en tab Estudiantes del coordinador (submissions de archive "Solicitud de Baja")
4. Sección Movilidad en dashboard del estudiante

### Iteración 6 — Referencia Bancaria Scaffolding (Módulo A) ✅
1. `payment_reference_service.py` (stub completo)
2. Endpoint `GET /user-program/{id}/payment-reference`
3. Bloque de referencia bancaria en dashboard del estudiante
4. **PENDIENTE PARA DESPUÉS**: Integrar algoritmo cuando esté disponible

---

## 9. Migraciones Necesarias

| # | Qué cambia | Archivo sugerido |
|---|------------|-----------------|
| 1 | `Archive.is_active` (nuevo campo) | `add_archive_is_active.py` |
| 2 | `UserProgram.has_conacyt_scholarship` (nuevo campo) | `add_conacyt_scholarship_flag.py` |
| 3 | `DocumentDeadline` (nueva tabla) | `add_document_deadline.py` |
| 4 | `Submission.document_deadline_id` (nuevo FK) | `add_submission_deadline_fk.py` |

Las migraciones 1 y 2 son simples `ADD COLUMN`. Las migraciones 3 y 4 requieren crear la tabla y el FK respectivamente.

---

## 10. Diagrama de Flujo General

```
ESTUDIANTE                          COORDINADOR
    │                                    │
    │  Inicio de periodo activo          │
    │◄───── Notificación ───────────────┤ Crea ventanas DocumentDeadline
    │                                    │ (abre fechas por archive)
    │                                    │
    │  Descarga Referencia Bancaria      │
    │◄── GET /payment-reference ────────┤ (si plantilla configurada)
    │                                    │
    │  Va al banco y paga               │
    │                                    │
    │                                    │◄── Marca como inscrito (ya existente)
    │◄───── Notificación ───────────────┤
    │                                    │
    │  Ve sección "Documentos del Sem." │
    │  Lista de ventanas abiertas        │
    │                                    │
    │  Sube Reporte de Avance           │
    │── POST /documents/{deadline_id} ──►│
    │                                    │ Revisa documento
    │◄───── Notificación ───────────────┤ [Aprobar / Rechazar]
    │                                    │
    │  (Si es becario CONACyT)           │
    │  Sube Formato Desempeño mensual   │
    │── POST /documents/{deadline_id} ──►│
    │                                    │
    │  (Si necesita baja temporal)       │
    │  Sube Solicitud de Baja           │
    │── POST /documents/{deadline_id} ──►│ Revisa solicitud
    │                                    │ [Aprobar → on_leave]
    │◄───── Notificación ───────────────┤ [Rechazar → notificación]
```

---

## Notas Finales

### Sobre la Referencia Bancaria (Módulo A)
Cuando el algoritmo esté disponible, solo se necesita:
1. Implementar `generate_payment_reference_number()` en `payment_reference_service.py`
2. Descomentar el bloque de generación en `get_payment_reference_for_student()`
3. Subir la plantilla HTML/DOCX al panel de plantillas (ya existente)

El resto del flujo (endpoint, UI del estudiante, botón de descarga) ya estará listo.

### Sobre la Distinción Maestría vs Doctorado
Se usa `Program.program_level` (ya existe). El coordinador verá una sugerencia en la UI:
- Si `program_level` contiene "Doctorado" → sugerencia: "Crear 2 ventanas de reporte"
- Caso contrario → sugerencia: "Crear 1 ventana de reporte"

### Sobre archives en Step 11 (Seguimiento Semestral)
Los archives de Step 11 (Protocolo de Investigación, Plan de Actividades, etc.) no fueron analizados en detalle en la última junta. Se recomienda **no implementarlos** en este plan y revisarlos en una iteración futura.
