# app/routes/api/admin/document_template_api.py
"""
API para gestionar plantillas de documentos y generar documentos rellenos.

Endpoints:
  GET    /api/admin/document-templates            — listar plantillas
  POST   /api/admin/document-templates            — subir plantilla (multipart)
  GET    /api/admin/document-templates/<uuid>     — detalle
  PATCH  /api/admin/document-templates/<uuid>     — activar/desactivar / cambiar nombre
  DELETE /api/admin/document-templates/<uuid>     — eliminar
  POST   /api/admin/document-templates/generate   — generar documento para un estudiante
  GET    /api/admin/document-templates/variables  — lista de variables disponibles
"""
from flask import Blueprint, request, send_file
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_error, api_server_error
from app.services import program_scope_service as scope_service
from app.services import template_access_service, document_template_service
from app.models.document_template import (
    DocumentTemplate, DOCUMENT_TYPES, TEMPLATE_FILE_TYPES
)
from app.models.user import User
from app.schemas.document_templates import (
    GenerateDocumentIn, UpdateTemplateIn, UploadTemplateForm,
)
from app.utils.validation import parse_form, parse_json

api_document_templates = Blueprint(
    'api_document_templates',
    __name__,
    url_prefix='/api/admin/document-templates',
)

ALLOWED_EXTENSIONS = {'html', 'docx'}


_ERROR_CODES = {
    400: 'VALIDATION_ERROR',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
}


def _err(msg, code=400):
    """Standard error envelope; the error code follows the HTTP status."""
    return api_error(_ERROR_CODES.get(code, 'BUSINESS_ERROR'), msg, status=code)


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _load_template_in_scope(template_uuid):
    """
    Carga una plantilla que esté dentro del ALCANCE del llamador.

    La capacidad (`admin_templates.api.list` / `.manage` / `.delete`) la exige
    el decorador; aquí sólo se responde "¿es tuya?" con la misma regla que
    guarda los bytes (`template_access_service.document_template_in_scope`).

    404 y no 403, igual que en el resto de la auditoría: una plantilla que no
    aparece en tu catálogo tampoco debe poder confirmarse recorriendo ids.

    Returns:
        (template, None) si procede; (None, respuesta_error) si no.
    """
    t = DocumentTemplate.by_uuid(template_uuid)
    if t is None or not template_access_service.document_template_in_scope(
            current_user, t.program_id):
        return None, _err("Plantilla no encontrada.", 404)
    return t, None


# ─────────────────────────────────────────────────────────────────────────────
# LISTAR
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.get('')
@login_required
@permission_required('admin_templates.api.list')
def list_templates():
    """
    Lista las plantillas que el llamador puede consultar.

    Filtros opcionales: document_type, program_id, active_only.

    ALCANCE: el permiso `admin_templates.api.list` lo tiene todo coordinador, y
    esta ruta devolvía el catálogo COMPLETO de la institución —nombre,
    descripción, programa y `file_path`— mientras `/files/template/<archivo>`
    ya negaba los bytes de esas mismas filas. Un índice que nombra archivos que
    no puedes abrir es la misma fuga a un salto de distancia, así que el
    filtrado lo hace `template_access_service.visible_document_templates`, que
    es literalmente el predicado que guarda los bytes: lo que se ve listado es
    exactamente lo que se puede descargar.
    """
    active_only = request.args.get('active_only', 'false').lower() == 'true'

    templates = template_access_service.visible_document_templates(
        current_user,
        document_template_service.query_templates(
            document_type=request.args.get('document_type'),
            program_id=request.args.get('program_id', type=int),
            active_only=active_only,
        ),
    )
    return api_ok([t.to_dict() for t in templates], meta={'total': len(templates)})


# ─────────────────────────────────────────────────────────────────────────────
# SUBIR PLANTILLA
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.post('')
@login_required
@permission_required('admin_templates.api.create')
def upload_template():
    """
    Sube un archivo de plantilla (HTML o DOCX) y registra la plantilla en BD.

    Form fields:
      file          (required) — archivo .html o .docx
      name          (required) — nombre descriptivo
      document_type (required) — acceptance_letter | enrollment_confirmation | course_schedule
      program_id    (optional) — si omitido, la plantilla es global
      description   (optional)

    ALCANCE: `program_id` lo elige quien sube el archivo, así que sin cerco se
    crea una plantilla para cualquier programa —o, omitiéndolo, la GLOBAL, que
    `DocumentTemplate.get_for_program` sirve como respaldo a todos—. Se exige
    el mismo alcance que para leerla: el programa dentro del alcance, y alcance
    global para una plantilla sin programa. Los roles semilla dan `create` sólo
    a la Jefatura, pero estos permisos se delegan (`permissions.api.delegate`),
    y un permiso delegado no amplía el alcance de quien lo recibe.
    """
    if 'file' not in request.files:
        return _err("Se requiere un archivo en el campo 'file'.")

    file = request.files['file']
    if not file.filename:
        return _err("El archivo no tiene nombre.")

    if not _allowed_file(file.filename):
        return _err(f"Tipo de archivo no permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    form = parse_form(UploadTemplateForm)
    name = form.name
    doc_type = form.document_type
    program_id = form.program_id
    description = form.description

    if not name:
        return _err("El campo 'name' es requerido.")
    if doc_type not in DOCUMENT_TYPES:
        return _err(f"document_type inválido. Opciones: {list(DOCUMENT_TYPES.keys())}")

    if not template_access_service.document_template_in_scope(current_user, program_id):
        return _err(
            "No tienes acceso a este programa."
            if program_id is not None
            else "Sólo la Jefatura de Posgrado puede crear plantillas globales.",
            403,
        )

    template = document_template_service.create_template(
        file=file,
        name=name,
        document_type=doc_type,
        program_id=program_id,
        description=description,
        created_by=current_user.id,
    )

    return api_ok(template.to_dict(), status=201)


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.get('/<uuid:template_uuid>')
@login_required
@permission_required('admin_templates.api.list')
def get_template(template_uuid):
    """
    Detalle de una plantilla.

    Mismo alcance que el listado —y que la descarga— vía
    `may_download_document_template`: si no sale en tu catálogo, tampoco se
    lee por id.
    """
    t = DocumentTemplate.by_uuid(template_uuid)
    if t is None or not template_access_service.may_download_document_template(
            current_user, t):
        return _err("Plantilla no encontrada.", 404)
    return api_ok(t.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# ACTUALIZAR (nombre, descripción, activar/desactivar)
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.patch('/<uuid:template_uuid>')
@login_required
@permission_required('admin_templates.api.manage')
def update_template(template_uuid):
    """
    Renombra, redescribe o (des)activa una plantilla dentro del alcance.

    `program_id` no es editable a propósito: mover una plantilla de programa
    sería una escritura fuera del alcance disfrazada de edición.
    """
    t, err = _load_template_in_scope(template_uuid)
    if err:
        return err

    body = parse_json(UpdateTemplateIn).model_dump(exclude_unset=True)
    t = document_template_service.update_template(t, body)
    return api_ok(t.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.delete('/<uuid:template_uuid>')
@login_required
@permission_required('admin_templates.api.delete')
def delete_template(template_uuid):
    """Elimina la fila y su archivo. Mismo alcance que leerla y editarla."""
    t, err = _load_template_in_scope(template_uuid)
    if err:
        return err
    deleted_public_id = str(t.uuid) if t.uuid else None

    document_template_service.delete_template(t)
    return api_ok({'deleted_id': deleted_public_id})


# ─────────────────────────────────────────────────────────────────────────────
# VARIABLES DISPONIBLES
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.get('/variables')
@login_required
@permission_required('admin_templates.api.list')
def list_variables():
    """Retorna la lista de variables disponibles para usar en plantillas."""
    variables = [
        {'key': '{{student_name}}',     'description': 'Nombre completo del estudiante'},
        {'key': '{{student_curp}}',     'description': 'CURP del estudiante'},
        {'key': '{{student_email}}',    'description': 'Correo electrónico del estudiante'},
        {'key': '{{control_number}}',   'description': 'Número de control asignado'},
        {'key': '{{program_name}}',     'description': 'Nombre del programa de posgrado'},
        {'key': '{{program_level}}',    'description': 'Nivel del programa (Maestría, Doctorado…)'},
        {'key': '{{period_code}}',      'description': 'Código del período académico (ej. 20261)'},
        {'key': '{{period_name}}',      'description': 'Nombre del período (ej. Enero-Junio 2026)'},
        {'key': '{{acceptance_date}}',  'description': 'Fecha de aceptación en formato largo'},
        {'key': '{{coordinator_name}}', 'description': 'Nombre del coordinador del programa'},
        {'key': '{{current_date}}',     'description': 'Fecha actual en formato dd/mm/yyyy'},
    ]
    return api_ok(variables)


# ─────────────────────────────────────────────────────────────────────────────
# GENERAR DOCUMENTO
# ─────────────────────────────────────────────────────────────────────────────

@api_document_templates.post('/generate')
@login_required
@permission_required('admin_templates.api.generate')
def generate_document():
    """
    Genera un documento relleno para un estudiante y lo retorna como descarga.

    Body JSON:
      user_id       (uuid str, required) — identificador público del estudiante
      program_id    (int, required)
      document_type (str, required)
      period_id     (int, optional)

    Alcance: la plantilla puede incrustar `{{student_curp}}` y
    `{{control_number}}`, así que esto NO es una lectura de catálogo. Exige el
    permiso propio `admin_templates.api.generate` y que TANTO el programa como
    el estudiante estén dentro del alcance del llamador. No hay nivel reducido:
    un documento relleno es dato personal completo o no es nada.
    """
    body = parse_json(GenerateDocumentIn)
    # `user_id` viaja en el CUERPO, no en el URL, pero es la misma clase de
    # identificador: UUID público. Se resuelve aquí y el servicio sigue
    # recibiendo el id interno.
    target = User.by_uuid(body.user_id)
    user_id = target.id if target else None
    program_id = body.program_id
    doc_type = body.document_type
    period_id = body.period_id

    if not user_id or not program_id or not doc_type:
        return _err("Se requieren: user_id, program_id, document_type.")

    if doc_type not in DOCUMENT_TYPES:
        return _err(f"document_type inválido. Opciones: {list(DOCUMENT_TYPES.keys())}")

    if not scope_service.program_in_scope(current_user, program_id):
        return _err("No tienes acceso a este programa.", 403)

    if not scope_service.user_in_scope(current_user, user_id, allow_self=False):
        return _err("No tienes acceso al expediente de este estudiante.", 403)

    try:
        from app.services.document_generation_service import DocumentGenerationService
        result = DocumentGenerationService.generate(
            user_id=user_id,
            program_id=program_id,
            document_type=doc_type,
            period_id=period_id,
        )
    except ValueError as e:
        return _err(str(e), 404)
    except Exception as e:
        return api_server_error(
            e, message='Error interno al generar el documento.',
            context='document_templates.generate_document',
        )

    mime = 'application/pdf' if result['file_type'] == 'pdf' else \
           'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    return send_file(
        result['output_path'],
        mimetype=mime,
        as_attachment=True,
        download_name=result['filename'],
    )
