# 📚 Plan de Implementación: Periodos Académicos y Transición Aspirante-Estudiante

> **Fecha de creación:** 16 de Enero de 2026  
> **Sistema:** SIIAP - Sistema Integral de Información Académica de Posgrado  
> **Versión del plan:** 1.0

---

## 📋 Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Fase 1: Periodos Académicos](#2-fase-1-periodos-académicos)
3. [Fase 2: Migración de Datos Existentes](#3-fase-2-migración-de-datos-existentes)
4. [Fase 3: Estado de Deliberación](#4-fase-3-estado-de-deliberación)
5. [Fase 4: Aceptación y Documentos de Inscripción](#5-fase-4-aceptación-y-documentos-de-inscripción)
6. [Fase 5: Transición a Estudiante](#6-fase-5-transición-a-estudiante)
7. [Fase 6: Permanencia Semestral](#7-fase-6-permanencia-semestral)
8. [Fase 7: Sistema de Diferimiento](#8-fase-7-sistema-de-diferimiento)
9. [Fase 8: Limpieza y Retención de Datos](#9-fase-8-limpieza-y-retención-de-datos)
10. [Fase 9: Generación Automática de Documentos](#10-fase-9-generación-automática-de-documentos)
11. [Consideraciones de Responsividad](#11-consideraciones-de-responsividad)
12. [Cronograma Estimado](#12-cronograma-estimado)
13. [Modelo de Datos Propuesto](#13-modelo-de-datos-propuesto)

---

## 1. Resumen Ejecutivo

Este plan detalla la implementación de un sistema completo de periodos académicos que permitirá:

- ✅ Gestionar periodos académicos con código único (ej: `20253` para Ago-Dic 2025)
- ✅ Asociar todas las submissions a un periodo específico
- ✅ Manejar el flujo completo de admisión → deliberación → aceptación → inscripción
- ✅ Permitir diferimiento de inscripción hasta por 2 periodos
- ✅ Transicionar aspirantes a estudiantes con cambio de rol y fase
- ✅ Gestionar documentos de permanencia semestre a semestre
- ✅ Limpiar datos de aspirantes que no completaron el proceso en 1 año
- ✅ Generar automáticamente cartas de aceptación y tiras de materias

---

## 2. Fase 1: Periodos Académicos

### 2.1 Objetivo
Crear el modelo `AcademicPeriod` y la interfaz de administración para gestionar periodos.

### 2.2 Modelo de Datos

```python
# app/models/academic_period.py
class AcademicPeriod(db.Model):
    __tablename__ = 'academic_period'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(5), unique=True, nullable=False)  # Ej: "20253"
    name = db.Column(db.String(100), nullable=False)  # Ej: "Agosto-Diciembre 2025"
    
    # Fechas del periodo académico (cuando se cursa)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    # Fechas de inscripción/admisión (cuando se hace el proceso)
    admission_start_date = db.Column(db.Date, nullable=False)
    admission_end_date = db.Column(db.Date, nullable=False)
    
    # Estado
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default='upcoming', nullable=False)
    # Estados: upcoming, active, admission_closed, completed
    
    # Metadatos
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relaciones
    submissions = db.relationship('Submission', back_populates='academic_period')
    user_programs = db.relationship('UserProgram', back_populates='admission_period')
```

### 2.3 Formato del Código

| Código | Significado | Periodo Académico |
|--------|-------------|-------------------|
| `20251` | 2025 + 1 | Enero-Junio 2025 |
| `20252` | 2025 + 2 | Verano 2025 (si aplica) |
| `20253` | 2025 + 3 | Agosto-Diciembre 2025 |
| `20261` | 2026 + 1 | Enero-Junio 2026 |

### 2.4 Interfaz de Administración

**Ubicación:** Dropdown de Configuración → Nueva pestaña "Periodos Académicos"

**Funcionalidades:**
- Lista de todos los periodos (activos, pasados, futuros)
- Crear nuevo periodo
- Editar periodo existente
- Activar/desactivar periodo (solo uno activo a la vez)
- Indicador visual del periodo activo actual

**Wireframe de la vista:**

```
┌─────────────────────────────────────────────────────────────────────┐
│ Configuración > Periodos Académicos                                 │
├─────────────────────────────────────────────────────────────────────┤
│ [+ Nuevo Periodo]                                                   │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 🟢 20253 - Agosto-Diciembre 2025                    [ACTIVO]   │ │
│ │    Admisión: 01/05/2025 - 30/06/2025                           │ │
│ │    Clases: 01/08/2025 - 15/12/2025                             │ │
│ │    Aspirantes: 45 | Aceptados: 32                  [Editar]    │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ ⚪ 20261 - Enero-Junio 2026                        [PRÓXIMO]   │ │
│ │    Admisión: 01/11/2025 - 15/01/2026                           │ │
│ │    Clases: 15/01/2026 - 30/06/2026                             │ │
│ │    [Activar] [Editar]                                          │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.5 Archivos a Crear/Modificar

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `app/models/academic_period.py` | Crear | Modelo de datos |
| `app/models/__init__.py` | Modificar | Agregar import |
| `app/routes/api/academic_period_api.py` | Crear | Endpoints API |
| `app/routes/pages/admin/settings_pages.py` | Modificar | Nueva ruta de página |
| `app/templates/admin/settings/academic_periods.html` | Crear | Vista de gestión |
| `app/templates/base.html` | Modificar | Agregar ítem al dropdown |
| `app/services/academic_period_service.py` | Crear | Lógica de negocio |

### 2.6 Reglas de Negocio

1. **Solo un periodo activo:** Al activar un periodo, se desactiva automáticamente el anterior
2. **Validación de código:** El código debe seguir el formato `YYYYN` y ser único
3. **Validación de fechas:** Las fechas de admisión deben ser anteriores a las fechas de clases
4. **No eliminar periodos con datos:** Un periodo con submissions o inscripciones no puede eliminarse

---

## 3. Fase 2: Migración de Datos Existentes

### 3.1 Objetivo
Migrar las submissions existentes al periodo académico `20253`.

### 3.2 Script de Migración

```python
# migrations/versions/xxx_add_academic_period.py

def upgrade():
    # 1. Crear tabla academic_period
    op.create_table('academic_period',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(5), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('admission_start_date', sa.Date(), nullable=False),
        sa.Column('admission_end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('status', sa.String(20), default='upcoming'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'])
    )
    
    # 2. Agregar columna academic_period_id a submission
    op.add_column('submission', 
        sa.Column('academic_period_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_submission_academic_period',
        'submission', 'academic_period',
        ['academic_period_id'], ['id']
    )
    
    # 3. Agregar columna admission_period_id a user_program
    op.add_column('user_program',
        sa.Column('admission_period_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_user_program_admission_period',
        'user_program', 'academic_period',
        ['admission_period_id'], ['id']
    )
    
    # 4. Insertar periodo inicial 20253
    op.execute("""
        INSERT INTO academic_period 
        (code, name, start_date, end_date, admission_start_date, admission_end_date, is_active, status, created_at)
        VALUES 
        ('20253', 'Agosto-Diciembre 2025', '2025-08-01', '2025-12-15', '2025-05-01', '2025-07-31', true, 'active', NOW())
    """)
    
    # 5. Migrar submissions existentes al periodo 20253
    op.execute("""
        UPDATE submission 
        SET academic_period_id = (SELECT id FROM academic_period WHERE code = '20253')
        WHERE academic_period_id IS NULL
    """)
    
    # 6. Migrar user_programs existentes al periodo 20253
    op.execute("""
        UPDATE user_program 
        SET admission_period_id = (SELECT id FROM academic_period WHERE code = '20253')
        WHERE admission_period_id IS NULL
    """)
```

### 3.3 Consideraciones

- **Backup obligatorio** antes de ejecutar la migración
- **Mantener campo `period`** en submission temporalmente para compatibilidad
- **Validar integridad** después de la migración

---

## 4. Fase 3: Estado de Deliberación

### 4.1 Objetivo
Implementar el estado de "En Deliberación" después de que el aspirante complete la entrevista.

### 4.2 Flujo Actualizado

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Registro   │───▶│ Documentos  │───▶│  Entrevista │───▶│ Deliberación│
│  Completo   │    │  Aprobados  │    │  Completada │    │  (Espera)   │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                                │
                                            ┌───────────────────┴───────────────────┐
                                            ▼                                       ▼
                                     ┌─────────────┐                        ┌─────────────┐
                                     │  ACEPTADO   │                        │  RECHAZADO  │
                                     │             │                        │             │
                                     └──────┬──────┘                        └──────┬──────┘
                                            │                                       │
                                            ▼                                       ▼
                                     ┌─────────────┐                        ┌─────────────┐
                                     │   Subir     │                        │  Reiniciar  │
                                     │   Docs de   │                        │  Proceso o  │
                                     │ Inscripción │                        │  Corregir   │
                                     └─────────────┘                        └─────────────┘
```

### 4.3 Modificaciones al Modelo UserProgram

```python
# Agregar campos a UserProgram
class UserProgram(db.Model):
    # ... campos existentes ...
    
    # Nuevos campos para deliberación
    admission_status = db.Column(db.String(30), default='in_progress')
    # Estados: in_progress, interview_completed, deliberation, accepted, 
    #          rejected, deferred, enrolled
    
    deliberation_started_at = db.Column(db.DateTime, nullable=True)
    decision_at = db.Column(db.DateTime, nullable=True)
    decision_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    decision_notes = db.Column(db.Text, nullable=True)
    
    # Para rechazos parciales (ej: cambiar línea de investigación)
    rejection_type = db.Column(db.String(30), nullable=True)
    # Tipos: full (reiniciar todo), partial (corregir algo específico)
    correction_required = db.Column(db.Text, nullable=True)
```

### 4.4 Vista del Aspirante en Deliberación

Cuando `admission_status = 'deliberation'`, la vista de admisión mostrará:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│            ┌───────────────────────────────────────┐                │
│            │         ⏳ EN DELIBERACIÓN            │                │
│            │                                        │                │
│            │  Tu proceso de admisión está siendo   │                │
│            │  evaluado por el comité de admisión.  │                │
│            │                                        │                │
│            │  Te notificaremos por correo cuando   │                │
│            │  tengamos una decisión.               │                │
│            │                                        │                │
│            │  Fecha de entrevista: 15/01/2026      │                │
│            └───────────────────────────────────────┘                │
│                                                                     │
│  ─────────────────── Tu Progreso ───────────────────                │
│                                                                     │
│  ✅ Registro completado                                             │
│  ✅ Documentos aprobados                                            │
│  ✅ Entrevista realizada                                            │
│  ⏳ Decisión pendiente                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.5 Vista del Coordinador

Panel para gestionar aspirantes en deliberación:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Aspirantes en Deliberación - MII                                    │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 👤 Juan Pérez García                                            │ │
│ │    Entrevista: 10/01/2026 | Puntaje: 85/100                    │ │
│ │    [Ver Expediente] [✅ Aceptar] [❌ Rechazar] [📝 Corrección]  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 👤 María López Hernández                                        │ │
│ │    Entrevista: 12/01/2026 | Puntaje: 78/100                    │ │
│ │    [Ver Expediente] [✅ Aceptar] [❌ Rechazar] [📝 Corrección]  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.6 Archivos a Crear/Modificar

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `app/models/user_program.py` | Modificar | Agregar campos de deliberación |
| `app/services/deliberation_service.py` | Crear | Lógica de deliberación |
| `app/routes/api/deliberation_api.py` | Crear | Endpoints API |
| `app/templates/programs/admission/deliberation.html` | Crear | Vista aspirante |
| `app/templates/coordinator/deliberation.html` | Crear | Vista coordinador |
| `app/services/admission_service.py` | Modificar | Detectar estado deliberación |

---

## 5. Fase 4: Aceptación y Documentos de Inscripción

### 5.1 Objetivo
Implementar el flujo de aceptación donde el coordinador sube documentos y el aspirante los recibe.

### 5.2 Nuevos Tipos de Documentos

```python
# Nuevos archives a crear para la fase de "pre-inscripción"
# Estos van en un nuevo step "Documentos de Aceptación"

ACCEPTANCE_DOCUMENTS = [
    {
        'name': 'Carta de Aceptación',
        'description': 'Carta oficial de aceptación al programa',
        'is_downloadable': True,
        'is_uploadable': False,  # Solo el coordinador la sube
        'allow_coordinator_upload': True,
        'step_id': 'acceptance_step'  # Nuevo step
    },
    {
        'name': 'Tira de Materias',
        'description': 'Materias a cursar en el primer semestre',
        'is_downloadable': True,
        'is_uploadable': False,
        'allow_coordinator_upload': True,
        'step_id': 'acceptance_step'
    },
    {
        'name': 'Boleta de Servicios Escolares',
        'description': 'Comprobante de inscripción de Servicios Escolares',
        'is_downloadable': False,
        'is_uploadable': True,  # El aspirante la sube
        'allow_coordinator_upload': False,
        'step_id': 'enrollment_step'  # Nuevo step
    }
]
```

### 5.3 Modelo de Datos Adicional

```python
# app/models/acceptance_document.py
class AcceptanceDocument(db.Model):
    """
    Documentos que el coordinador sube para un aspirante aceptado.
    Estos son documentos específicos por usuario, no plantillas.
    """
    __tablename__ = 'acceptance_document'
    
    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    # Tipos: acceptance_letter, course_schedule, enrollment_receipt
    
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=now_local, nullable=False)
    
    # Para documentos que sube el aspirante
    status = db.Column(db.String(20), default='pending')
    # Estados: pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    
    # Relaciones
    user_program = db.relationship('UserProgram', back_populates='acceptance_documents')
```

### 5.4 Vista del Aspirante Aceptado

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│            ┌───────────────────────────────────────┐                │
│            │      🎉 ¡FELICIDADES!                 │                │
│            │                                        │                │
│            │  Has sido aceptado en el programa     │                │
│            │  Maestría en Ingeniería Industrial    │                │
│            │                                        │                │
│            │  Periodo: Enero-Junio 2026            │                │
│            └───────────────────────────────────────┘                │
│                                                                     │
│  ─────────────── Documentos para Inscripción ───────────────────    │
│                                                                     │
│  📄 Carta de Aceptación                           [⬇️ Descargar]    │
│  📄 Tira de Materias                              [⬇️ Descargar]    │
│                                                                     │
│  ─────────────── Siguiente Paso ────────────────────────────────    │
│                                                                     │
│  Lleva estos documentos a Servicios Escolares para completar       │
│  tu inscripción. Una vez que tengas tu boleta, súbela aquí:        │
│                                                                     │
│  📤 Boleta de Servicios Escolares     [Subir archivo]              │
│     Estado: Pendiente                                               │
│                                                                     │
│  ⚠️ Tienes hasta el 20/01/2026 para completar tu inscripción       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.5 Vista del Coordinador para Subir Documentos

```
┌─────────────────────────────────────────────────────────────────────┐
│ Gestionar Aceptación - Juan Pérez García                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Estado actual: ACEPTADO ✅                                         │
│  Periodo: 20261 (Ene-Jun 2026)                                      │
│                                                                     │
│  ─────────────── Documentos a Entregar ─────────────────────────    │
│                                                                     │
│  📄 Carta de Aceptación                                             │
│     [ ] Usar plantilla automática                                   │
│     [Subir documento] o [Generar automático]                        │
│     Estado: ❌ No subido                                            │
│                                                                     │
│  📄 Tira de Materias                                                │
│     [Subir documento] o [Generar automático]                        │
│     Estado: ❌ No subido                                            │
│                                                                     │
│  ─────────────── Documento del Aspirante ───────────────────────    │
│                                                                     │
│  📤 Boleta de Servicios Escolares                                   │
│     Estado: ⏳ Esperando que el aspirante la suba                   │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  [Guardar y Notificar al Aspirante]                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Fase 5: Transición a Estudiante

### 6.1 Objetivo
Implementar el proceso de asignación de número de control y cambio de rol.

### 6.2 Flujo de Transición

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    ACEPTADO     │────▶│  Boleta subida  │────▶│   Coordinador   │
│   (aspirante)   │     │   por aspirante │     │    verifica     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │ Asignar número  │
                                                │   de control    │
                                                └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        ▼                                ▼                                ▼
               ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
               │ Cambiar rol a   │              │ Cambiar status  │              │ Mover a fase    │
               │   "student"     │              │  a "enrolled"   │              │  "permanence"   │
               └─────────────────┘              └─────────────────┘              └─────────────────┘
```

### 6.3 Modificaciones al Modelo User

```python
# El campo control_number ya existe en User
# Agregar validación y formato específico

class User(db.Model):
    # ... campos existentes ...
    
    # Ya existe:
    # control_number = db.Column(db.String(20), unique=True, nullable=True)
    # control_number_assigned_at = db.Column(db.DateTime, nullable=True)
    
    def assign_control_number(self, control_number, assigned_by=None):
        """
        Asigna número de control y cambia rol a estudiante.
        """
        from app.models import Role
        
        self.control_number = control_number
        self.username = control_number  # El username se vuelve el número de control
        self.control_number_assigned_at = now_local()
        
        # Cambiar rol a estudiante
        student_role = Role.query.filter_by(name='student').first()
        if student_role:
            self.role_id = student_role.id
```

### 6.4 Crear Rol de Estudiante

```sql
-- Agregar rol de estudiante si no existe
INSERT INTO role (name, description) 
VALUES ('student', 'Estudiante activo del programa')
ON CONFLICT (name) DO NOTHING;
```

### 6.5 Vista del Coordinador para Asignar Número de Control

```
┌─────────────────────────────────────────────────────────────────────┐
│ Verificar Inscripción - Juan Pérez García                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📄 Boleta de Servicios Escolares                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    [Vista previa del PDF]                   │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  [Ver documento completo]                                           │
│                                                                     │
│  ─────────────── Asignar Número de Control ─────────────────────    │
│                                                                     │
│  Número de Control: [M26111001        ]                             │
│                     (Como aparece en la boleta)                     │
│                                                                     │
│  [ ] Confirmo que la boleta es válida y los datos coinciden        │
│                                                                     │
│  ⚠️ Al confirmar:                                                   │
│     • El usuario cambiará de rol "Aspirante" a "Estudiante"        │
│     • Se asignará el número de control como username               │
│     • Pasará a la fase de Permanencia                              │
│                                                                     │
│  [Cancelar]                        [✅ Confirmar Inscripción]       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.6 Servicio de Transición

```python
# app/services/enrollment_service.py
class EnrollmentService:
    
    @staticmethod
    def complete_enrollment(user_id: int, program_id: int, control_number: str, 
                          coordinator_id: int) -> dict:
        """
        Completa el proceso de inscripción:
        1. Valida el número de control
        2. Cambia el rol del usuario
        3. Actualiza user_program
        4. Registra en historial
        5. Envía notificación
        """
        user = User.query.get(user_id)
        user_program = UserProgram.query.filter_by(
            user_id=user_id, 
            program_id=program_id
        ).first()
        
        # Validar número de control único
        if User.query.filter_by(control_number=control_number).first():
            raise ValueError("El número de control ya está asignado")
        
        # 1. Asignar número de control y cambiar rol
        student_role = Role.query.filter_by(name='student').first()
        user.control_number = control_number
        user.username = control_number
        user.control_number_assigned_at = now_local()
        user.role_id = student_role.id
        
        # 2. Actualizar user_program
        user_program.admission_status = 'enrolled'
        user_program.current_semester = 1
        user_program.status = 'active'
        
        # 3. Registrar en historial
        UserHistoryService.log_action(
            user_id=user_id,
            admin_id=coordinator_id,
            action='enrollment_completed',
            details=f"Número de control asignado: {control_number}"
        )
        
        # 4. Enviar notificación
        NotificationService.send(
            user_id=user_id,
            title="¡Inscripción completada!",
            message=f"Tu número de control es {control_number}. Bienvenido al programa."
        )
        
        db.session.commit()
        
        return {"success": True, "control_number": control_number}
```

---

## 7. Fase 6: Permanencia Semestral

### 7.1 Objetivo
Implementar el seguimiento semestral de estudiantes con documentos requeridos por periodo.

### 7.2 Modelo de Datos Adicional

```python
# app/models/semester_enrollment.py
class SemesterEnrollment(db.Model):
    """
    Registro de inscripción semestral del estudiante.
    """
    __tablename__ = 'semester_enrollment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id'), nullable=False)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'), nullable=False)
    semester_number = db.Column(db.Integer, nullable=False)
    
    # Estado de inscripción del semestre
    status = db.Column(db.String(30), default='pending')
    # Estados: pending, active, completed, on_leave, dropped
    
    # Confirmación de pago/inscripción por coordinador
    enrollment_confirmed = db.Column(db.Boolean, default=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    # Fechas límite
    documents_deadline = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local)
```

### 7.3 Flujo de Permanencia por Semestre

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INICIO DE NUEVO SEMESTRE                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Coordinador confirma inscripción/pago del estudiante            │
│    (marca como "inscrito" en este semestre)                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Sistema incrementa current_semester en user_program              │
│    Crea registro en semester_enrollment                             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Estudiante ve documentos requeridos para el semestre             │
│    (de los steps de phase="permanence")                             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Estudiante sube documentos antes del deadline                    │
│    Si no sube → notificación y posible prórroga                     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Coordinador revisa y aprueba documentos                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.4 Vista del Estudiante - Dashboard de Permanencia

```
┌─────────────────────────────────────────────────────────────────────┐
│ 👤 M26111001 - Juan Pérez García                                    │
│ Maestría en Ingeniería Industrial | Semestre 2                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Periodo Actual: 20261 (Enero-Junio 2026)                           │
│  Estado: ✅ Inscrito                                                │
│                                                                     │
│  ─────────────── Documentos del Semestre ───────────────────────    │
│                                                                     │
│  📄 Avance de Tesis                                                 │
│     Fecha límite: 15/03/2026                                        │
│     Estado: ⏳ Pendiente                    [Subir]                 │
│                                                                     │
│  📄 Constancia de Inscripción                                       │
│     Fecha límite: 28/02/2026                                        │
│     Estado: ✅ Aprobado                     [Ver]                   │
│                                                                     │
│  📄 Reporte Semestral                                               │
│     Fecha límite: 30/06/2026                                        │
│     Estado: ⏳ Pendiente                    [Subir]                 │
│                                                                     │
│  ─────────────── Historial de Semestres ────────────────────────    │
│                                                                     │
│  │ Sem 1 │ 20253 │ ✅ Completado │ 4/4 documentos │                 │
│  │ Sem 2 │ 20261 │ 🔄 En curso   │ 1/3 documentos │                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.5 Vista del Coordinador - Gestión de Permanencia

```
┌─────────────────────────────────────────────────────────────────────┐
│ Gestión de Permanencia - MII | Periodo: 20261                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Confirmar inscripciones del periodo]                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Filtros: [Todos ▼] [Semestre ▼] [Estado documentos ▼]      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ [ ] M26111001 - Juan Pérez          Sem 2   📄 1/3  ⏳      │    │
│  │ [ ] M26111002 - María López         Sem 2   📄 3/3  ✅      │    │
│  │ [ ] M26111003 - Carlos Ruiz         Sem 1   📄 0/4  ⚠️      │    │
│  │ [ ] M25111010 - Ana García          Sem 4   📄 2/3  🔄      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Acciones masivas: [Notificar pendientes] [Exportar reporte]        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Fase 7: Sistema de Diferimiento

### 8.1 Objetivo
Permitir que aspirantes aceptados difieran su inscripción hasta por 2 periodos.

### 8.2 Modelo de Datos

```python
# app/models/enrollment_deferral.py
class EnrollmentDeferral(db.Model):
    """
    Registro de diferimiento de inscripción.
    """
    __tablename__ = 'enrollment_deferral'
    
    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id'), nullable=False)
    
    # Periodo original de aceptación
    original_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'), nullable=False)
    
    # Periodo al que difiere
    deferred_to_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'), nullable=True)
    
    # Conteo de diferimientos (máximo 2)
    deferral_count = db.Column(db.Integer, default=1, nullable=False)
    
    # Estado
    status = db.Column(db.String(20), default='active')
    # Estados: active, used (se inscribió), expired (pasó el límite)
    
    # Razón del diferimiento
    reason = db.Column(db.Text, nullable=True)
    
    # Metadatos
    created_at = db.Column(db.DateTime, default=now_local)
    expires_at = db.Column(db.DateTime, nullable=False)  # Fecha límite para usar
    
    # Notificaciones
    notification_sent_at = db.Column(db.DateTime, nullable=True)
```

### 8.3 Reglas de Negocio

1. **Máximo 2 diferimientos:** Un aspirante puede diferir máximo 2 periodos
2. **Misma carta de aceptación:** Se mantienen válidos los documentos de aceptación
3. **Notificación automática:** 30 días antes de que expire, notificar al aspirante
4. **Expiración automática:** Si no se inscribe después de 2 periodos, se marca como expirado

### 8.4 Flujo de Diferimiento

```
┌─────────────┐                    ┌─────────────┐
│  ACEPTADO   │───── No se ───────▶│ DIFERIDO    │
│  Periodo 1  │     inscribió      │ Periodo 2   │
└─────────────┘                    └──────┬──────┘
                                          │
                           ┌──────────────┴──────────────┐
                           ▼                              ▼
                   ┌─────────────┐                ┌─────────────┐
                   │ Se inscribe │                │ No se       │
                   │ en Periodo 2│                │ inscribe    │
                   └─────────────┘                └──────┬──────┘
                                                         │
                                          ┌──────────────┴──────────────┐
                                          ▼                              ▼
                                  ┌─────────────┐                ┌─────────────┐
                                  │ DIFERIDO    │                │  EXPIRADO   │
                                  │ Periodo 3   │                │ (último     │
                                  │ (último)    │                │ diferimiento│
                                  └─────────────┘                └─────────────┘
```

### 8.5 Vista del Aspirante con Diferimiento

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ⚠️ Tu inscripción está diferida                                   │
│                                                                     │
│  Fuiste aceptado en el periodo Ago-Dic 2025 pero no completaste    │
│  tu inscripción. Tu carta de aceptación sigue vigente.             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Diferimientos usados: 1 de 2                                │    │
│  │ Periodo actual de diferimiento: Ene-Jun 2026                │    │
│  │ Fecha límite para inscribirte: 20/01/2026                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  📄 Tu carta de aceptación sigue disponible: [Descargar]           │
│  📄 Tu tira de materias puede cambiar: [Ver tira actualizada]      │
│                                                                     │
│  [Continuar con mi inscripción]                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Fase 8: Limpieza y Retención de Datos

### 9.1 Objetivo
Implementar políticas de limpieza automática para aspirantes que no completaron el proceso.

### 9.2 Políticas de Retención

| Tipo de Usuario | Condición | Tiempo | Acción |
|-----------------|-----------|--------|--------|
| Aspirante | No completó documentos | 1 año | Borrar archivos, marcar como `expired` |
| Aspirante | Aceptado pero no inscrito | 2 periodos (~1 año) | Borrar archivos, marcar como `expired` |
| Estudiante | Documentos de permanencia | Según política del archivo | Algunos nunca se borran |
| Estudiante | Inactivo (no sube docs) | Después de notificaciones | Marcar como `inactive` |

### 9.3 Servicio de Limpieza

```python
# app/services/data_cleanup_service.py
class DataCleanupService:
    
    @staticmethod
    def get_expired_applicants(cutoff_date: datetime) -> List[User]:
        """
        Obtiene aspirantes que no completaron el proceso en más de 1 año.
        """
        return User.query.join(UserProgram).filter(
            User.role.has(name='applicant'),
            UserProgram.admission_status.in_(['in_progress', 'interview_completed']),
            UserProgram.enrollment_date < cutoff_date
        ).all()
    
    @staticmethod
    def cleanup_expired_applicant(user_id: int) -> dict:
        """
        Limpia los datos de un aspirante expirado:
        1. Borra archivos físicos de submissions
        2. Borra registros de submissions
        3. Actualiza status a 'expired'
        4. Registra en historial
        """
        user = User.query.get(user_id)
        
        # Obtener submissions del usuario
        submissions = Submission.query.filter_by(user_id=user_id).all()
        
        deleted_files = 0
        for sub in submissions:
            # Borrar archivo físico
            if sub.file_path and os.path.exists(sub.file_path):
                os.remove(sub.file_path)
                deleted_files += 1
            
            # Borrar registro
            db.session.delete(sub)
        
        # Actualizar user_programs
        UserProgram.query.filter_by(user_id=user_id).update({
            'status': 'expired',
            'admission_status': 'expired'
        })
        
        # Registrar en historial
        UserHistoryService.log_action(
            user_id=user_id,
            admin_id=None,  # Sistema
            action='data_cleanup',
            details=f"Datos limpiados por inactividad. Archivos eliminados: {deleted_files}"
        )
        
        db.session.commit()
        
        return {
            'user_id': user_id,
            'deleted_files': deleted_files,
            'status': 'expired'
        }
    
    @staticmethod
    def run_cleanup_job():
        """
        Job programado para ejecutar limpieza automática.
        Ejecutar diariamente o semanalmente.
        """
        cutoff_date = now_local() - timedelta(days=365)
        
        expired_users = DataCleanupService.get_expired_applicants(cutoff_date)
        
        results = []
        for user in expired_users:
            result = DataCleanupService.cleanup_expired_applicant(user.id)
            results.append(result)
        
        return {
            'processed': len(results),
            'details': results
        }
```

### 9.4 Notificaciones de Inactividad para Estudiantes

```python
# app/services/permanence_notification_service.py
class PermanenceNotificationService:
    
    @staticmethod
    def notify_pending_documents():
        """
        Notifica a estudiantes con documentos pendientes de permanencia.
        """
        # Obtener periodo activo
        active_period = AcademicPeriod.query.filter_by(is_active=True).first()
        if not active_period:
            return
        
        # Obtener estudiantes con documentos pendientes
        students = db.session.query(User, UserProgram).join(
            UserProgram, User.id == UserProgram.user_id
        ).filter(
            User.role.has(name='student'),
            UserProgram.status == 'active'
        ).all()
        
        for user, user_program in students:
            pending_docs = get_pending_permanence_docs(user.id, user_program.program_id)
            
            if pending_docs:
                NotificationService.send(
                    user_id=user.id,
                    title="Documentos pendientes",
                    message=f"Tienes {len(pending_docs)} documento(s) pendiente(s) de subir para el periodo actual."
                )
```

### 9.5 Integración con Módulo Existente de Retención

El sistema ya tiene `RetentionPolicy` y `RetentionService`. Se debe:

1. Verificar que las políticas estén actualizadas
2. Agregar nuevas políticas para documentos de aceptación
3. Asegurar que documentos críticos (título, actas) tengan `keep_forever=True`

---

## 10. Fase 9: Generación Automática de Documentos

### 10.1 Objetivo
Permitir la generación automática de cartas de aceptación y tiras de materias.

### 10.2 Estructura de Plantillas

```
instance/
└── templates_sys/
    └── admission/
        ├── acceptance_letter_template.docx
        ├── acceptance_letter_template.html
        └── course_schedule_template.html
    └── permanence/
        └── ...
```

### 10.3 Modelo de Plantillas

```python
# app/models/document_template.py
class DocumentTemplate(db.Model):
    """
    Plantillas de documentos configurables por programa.
    """
    __tablename__ = 'document_template'
    
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    # Si program_id es null, es plantilla global
    
    document_type = db.Column(db.String(50), nullable=False)
    # Tipos: acceptance_letter, course_schedule, enrollment_confirmation
    
    name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # docx, html, pdf
    
    # Variables disponibles en la plantilla
    available_variables = db.Column(db.JSON)
    # Ej: ["student_name", "program_name", "period_name", "acceptance_date"]
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local)
```

### 10.4 Servicio de Generación de Documentos

```python
# app/services/document_generation_service.py
from docx import Document
from docx.shared import Pt, Inches
import pdfkit

class DocumentGenerationService:
    
    VARIABLE_MAP = {
        'student_name': lambda u, p, ap: f"{u.first_name} {u.last_name} {u.mother_last_name or ''}",
        'student_curp': lambda u, p, ap: u.curp or '',
        'student_email': lambda u, p, ap: u.email,
        'program_name': lambda u, p, ap: p.name,
        'program_level': lambda u, p, ap: p.program_level or 'Posgrado',
        'period_code': lambda u, p, ap: ap.code,
        'period_name': lambda u, p, ap: ap.name,
        'acceptance_date': lambda u, p, ap: now_local().strftime('%d de %B de %Y'),
        'coordinator_name': lambda u, p, ap: f"{p.coordinator.first_name} {p.coordinator.last_name}",
        'current_date': lambda u, p, ap: now_local().strftime('%d/%m/%Y'),
    }
    
    @staticmethod
    def generate_acceptance_letter(user_id: int, program_id: int, 
                                   period_id: int) -> str:
        """
        Genera carta de aceptación en PDF.
        Retorna la ruta del archivo generado.
        """
        user = User.query.get(user_id)
        program = Program.query.get(program_id)
        period = AcademicPeriod.query.get(period_id)
        
        # Obtener plantilla
        template = DocumentTemplate.query.filter_by(
            program_id=program_id,
            document_type='acceptance_letter',
            is_active=True
        ).first()
        
        if not template:
            # Usar plantilla global
            template = DocumentTemplate.query.filter_by(
                program_id=None,
                document_type='acceptance_letter',
                is_active=True
            ).first()
        
        if not template:
            raise ValueError("No hay plantilla de carta de aceptación configurada")
        
        # Generar variables
        variables = {}
        for var_name, var_func in DocumentGenerationService.VARIABLE_MAP.items():
            variables[var_name] = var_func(user, program, period)
        
        # Generar documento según tipo
        if template.file_type == 'html':
            output_path = DocumentGenerationService._generate_from_html(
                template, variables, user_id, 'acceptance_letter'
            )
        elif template.file_type == 'docx':
            output_path = DocumentGenerationService._generate_from_docx(
                template, variables, user_id, 'acceptance_letter'
            )
        
        return output_path
    
    @staticmethod
    def _generate_from_html(template, variables, user_id, doc_type):
        """Genera PDF desde plantilla HTML."""
        with open(template.file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Reemplazar variables
        for var_name, var_value in variables.items():
            html_content = html_content.replace(f'{{{{{var_name}}}}}', str(var_value))
        
        # Generar PDF
        output_dir = f"instance/uploads/generated/{user_id}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{doc_type}_{now_local().strftime('%Y%m%d')}.pdf"
        
        pdfkit.from_string(html_content, output_path)
        
        return output_path
```

### 10.5 Variables Disponibles para Plantillas

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{{student_name}}` | Nombre completo del estudiante | Juan Pérez García |
| `{{student_curp}}` | CURP del estudiante | PEGJ900101HCHRRN09 |
| `{{student_email}}` | Email del estudiante | juan@email.com |
| `{{program_name}}` | Nombre del programa | Maestría en Ingeniería Industrial |
| `{{program_level}}` | Nivel del programa | Maestría |
| `{{period_code}}` | Código del periodo | 20261 |
| `{{period_name}}` | Nombre del periodo | Enero-Junio 2026 |
| `{{acceptance_date}}` | Fecha de aceptación | 15 de enero de 2026 |
| `{{coordinator_name}}` | Nombre del coordinador | Dr. Carlos Martínez |
| `{{current_date}}` | Fecha actual | 16/01/2026 |

---

## 11. Consideraciones de Responsividad

### 11.1 Principios Generales

Toda la interfaz debe ser **mobile-first** y completamente funcional en:
- 📱 Móviles (320px - 767px)
- 📱 Tablets (768px - 1023px)
- 💻 Desktop (1024px+)

### 11.2 Componentes Críticos a Revisar

| Componente | Estado Actual | Acciones Necesarias |
|------------|---------------|---------------------|
| Dashboard de admisión | Revisar | Ajustar tarjetas y timeline |
| Vista de deliberación | Nueva | Diseñar responsive desde inicio |
| Gestión de periodos | Nueva | Diseñar responsive desde inicio |
| Vista de permanencia | Nueva | Diseñar responsive desde inicio |
| Tablas de estudiantes | Revisar | Implementar scroll horizontal o cards |
| Modales de acción | Revisar | Ajustar tamaños en móvil |
| Formularios | Revisar | Stack vertical en móvil |

### 11.3 Patrones de Diseño Responsivo

```html
<!-- Ejemplo: Cards que cambian de horizontal a vertical -->
<div class="row">
    <div class="col-12 col-md-6 col-lg-4">
        <!-- Card de periodo académico -->
    </div>
</div>

<!-- Ejemplo: Tabla que se convierte en cards en móvil -->
<div class="d-none d-md-block">
    <!-- Tabla normal para desktop -->
</div>
<div class="d-md-none">
    <!-- Cards para móvil -->
</div>
```

### 11.4 Breakpoints de Bootstrap a Usar

```scss
// Ya definidos en Bootstrap 5
$grid-breakpoints: (
  xs: 0,
  sm: 576px,
  md: 768px,
  lg: 992px,
  xl: 1200px,
  xxl: 1400px
);
```

---

## 12. Cronograma Estimado

### Vista General

```
Semana 1-2:   Fase 1 (Periodos Académicos) + Fase 2 (Migración)
Semana 3:     Fase 3 (Estado de Deliberación)
Semana 4:     Fase 4 (Aceptación y Documentos)
Semana 5:     Fase 5 (Transición a Estudiante)
Semana 6-7:   Fase 6 (Permanencia Semestral)
Semana 8:     Fase 7 (Sistema de Diferimiento)
Semana 9:     Fase 8 (Limpieza y Retención)
Semana 10:    Fase 9 (Generación de Documentos) [Opcional]
Semana 11-12: Testing, ajustes y despliegue
```

### Desglose Detallado

| Fase | Duración | Prioridad | Dependencias |
|------|----------|-----------|--------------|
| 1. Periodos Académicos | 5 días | 🔴 Alta | Ninguna |
| 2. Migración de Datos | 2 días | 🔴 Alta | Fase 1 |
| 3. Deliberación | 4 días | 🔴 Alta | Fase 1 |
| 4. Aceptación | 5 días | 🔴 Alta | Fase 3 |
| 5. Transición | 4 días | 🔴 Alta | Fase 4 |
| 6. Permanencia | 7 días | 🟡 Media | Fase 5 |
| 7. Diferimiento | 4 días | 🟡 Media | Fase 4 |
| 8. Limpieza | 3 días | 🟢 Baja | Fase 1 |
| 9. Generación Docs | 5 días | 🟢 Baja | Fase 4 |

---

## 13. Modelo de Datos Propuesto

### Diagrama de Relaciones (Nuevas Tablas)

```
┌─────────────────────┐
│   academic_period   │
├─────────────────────┤
│ id                  │
│ code (único)        │◄──────────────────────────────────────┐
│ name                │                                        │
│ start_date          │                                        │
│ end_date            │                                        │
│ admission_start     │                                        │
│ admission_end       │                                        │
│ is_active           │                                        │
│ status              │                                        │
└─────────────────────┘                                        │
         │                                                     │
         │ 1:N                                                 │
         ▼                                                     │
┌─────────────────────┐     ┌─────────────────────┐           │
│     submission      │     │    user_program     │           │
├─────────────────────┤     ├─────────────────────┤           │
│ ...existentes...    │     │ ...existentes...    │           │
│ academic_period_id  │◄────│ admission_period_id │───────────┘
└─────────────────────┘     │ admission_status    │
                            │ deliberation_at     │
                            │ decision_at         │
                            │ decision_by         │
                            │ rejection_type      │
                            │ correction_required │
                            └─────────────────────┘
                                      │
                                      │ 1:N
                                      ▼
                            ┌─────────────────────┐
                            │ acceptance_document │
                            ├─────────────────────┤
                            │ id                  │
                            │ user_program_id     │
                            │ document_type       │
                            │ file_path           │
                            │ uploaded_by         │
                            │ status              │
                            └─────────────────────┘
                                      │
                                      │ 1:N
                                      ▼
                            ┌─────────────────────┐
                            │ semester_enrollment │
                            ├─────────────────────┤
                            │ id                  │
                            │ user_program_id     │
                            │ academic_period_id  │
                            │ semester_number     │
                            │ status              │
                            │ enrollment_confirmed│
                            └─────────────────────┘

┌─────────────────────┐
│ enrollment_deferral │
├─────────────────────┤
│ id                  │
│ user_program_id     │
│ original_period_id  │
│ deferred_to_id      │
│ deferral_count      │
│ status              │
│ expires_at          │
└─────────────────────┘

┌─────────────────────┐
│  document_template  │
├─────────────────────┤
│ id                  │
│ program_id          │
│ document_type       │
│ name                │
│ file_path           │
│ available_variables │
└─────────────────────┘
```

### Script SQL de Creación (Resumen)

```sql
-- 1. academic_period
CREATE TABLE academic_period (
    id SERIAL PRIMARY KEY,
    code VARCHAR(5) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    admission_start_date DATE NOT NULL,
    admission_end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'upcoming',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    created_by INTEGER REFERENCES "user"(id)
);

-- 2. Modificar submission
ALTER TABLE submission 
ADD COLUMN academic_period_id INTEGER REFERENCES academic_period(id);

-- 3. Modificar user_program
ALTER TABLE user_program 
ADD COLUMN admission_period_id INTEGER REFERENCES academic_period(id),
ADD COLUMN admission_status VARCHAR(30) DEFAULT 'in_progress',
ADD COLUMN deliberation_started_at TIMESTAMP,
ADD COLUMN decision_at TIMESTAMP,
ADD COLUMN decision_by INTEGER REFERENCES "user"(id),
ADD COLUMN decision_notes TEXT,
ADD COLUMN rejection_type VARCHAR(30),
ADD COLUMN correction_required TEXT;

-- 4. acceptance_document
CREATE TABLE acceptance_document (
    id SERIAL PRIMARY KEY,
    user_program_id INTEGER NOT NULL REFERENCES user_program(id),
    document_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES "user"(id),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_by INTEGER REFERENCES "user"(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT
);

-- 5. semester_enrollment
CREATE TABLE semester_enrollment (
    id SERIAL PRIMARY KEY,
    user_program_id INTEGER NOT NULL REFERENCES user_program(id),
    academic_period_id INTEGER NOT NULL REFERENCES academic_period(id),
    semester_number INTEGER NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    enrollment_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_by INTEGER REFERENCES "user"(id),
    confirmed_at TIMESTAMP,
    documents_deadline TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- 6. enrollment_deferral
CREATE TABLE enrollment_deferral (
    id SERIAL PRIMARY KEY,
    user_program_id INTEGER NOT NULL REFERENCES user_program(id),
    original_period_id INTEGER NOT NULL REFERENCES academic_period(id),
    deferred_to_period_id INTEGER REFERENCES academic_period(id),
    deferral_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'active',
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    notification_sent_at TIMESTAMP
);

-- 7. document_template
CREATE TABLE document_template (
    id SERIAL PRIMARY KEY,
    program_id INTEGER REFERENCES program(id),
    document_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    available_variables JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- 8. Agregar rol de estudiante
INSERT INTO role (name, description) 
VALUES ('student', 'Estudiante activo inscrito en un programa')
ON CONFLICT DO NOTHING;
```

---

## 📝 Notas Finales

### Orden de Implementación Recomendado

1. **Empezar con Fase 1 y 2** - Son la base de todo el sistema
2. **Luego Fase 3, 4 y 5** - Flujo completo de admisión hasta inscripción
3. **Fase 6** - Permanencia para estudiantes ya inscritos
4. **Fases 7, 8 y 9** - Mejoras y automatizaciones

### Consideraciones de Testing

- Crear tests unitarios para cada servicio nuevo
- Tests de integración para flujos completos
- Tests de UI para responsividad
- Datos de prueba para cada estado posible

### Rollback

- Mantener backup de base de datos antes de cada migración
- Scripts de rollback para cada fase
- Compatibilidad hacia atrás durante la transición

---

**Documento creado por:** GitHub Copilot  
**Fecha:** 16 de Enero de 2026  
**Versión:** 1.0
