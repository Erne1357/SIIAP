# app/routes/api/submissions_api.py
from flask import Blueprint, request
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok
from app.utils.validation import parse_form
from app.schemas.submissions import UploadSubmissionIn
from app.services import submissions_service

api_submissions = Blueprint("api_submissions", __name__, url_prefix="/api/v1/submissions")

@api_submissions.post("")
@login_required
@permission_required('submissions.api.create')
def upload_submission():
    """
    multipart/form-data:
      - archive_id (uuid)         obligatorio — identificador público
      - file (File)               obligatorio
      - program_id (int)          opcional (uno de program_id o program_slug)
      - program_slug (string)     opcional
    """
    # `archive_id` viaja en el FORM y es el UUID público del Archive.
    form = parse_form(UploadSubmissionIn)
    sub, archive, program, ps = submissions_service.upload_submission(
        current_user, form.archive_id, form.program_id, form.program_slug,
        request.files.get("file"),
    )

    # WebSocket: notificar a coordinadores en tiempo real
    try:
        # Sólo a los coordinadores con alcance sobre el programa: el payload ata
        # un user_id al nombre de un documento suyo y eso no cruza de programa.
        from app.sockets.emitters import emit_to_coordinators
        emit_to_coordinators('submission:new', {
            # Identificadores públicos: el navegador los compara con los `id`
            # que publican los payloads REST, que también son UUID.
            'user_id': str(current_user.uuid) if current_user.uuid else None,
            'submission_id': str(sub.uuid) if sub.uuid else None,
            'archive_name': archive.name,
            'program_id': program.id,
        }, program.id)
    except Exception:
        pass

    return api_ok(
        {
            "submission": {
                "id": str(sub.uuid) if sub.uuid else None,
                "archive_id": str(archive.uuid) if archive.uuid else None,
                "status": sub.status,
                "file_path": sub.file_path,
                "program_id": program.id,
                "program_step_id": ps.id
            }
        },
        status=201,
        flash=[{"level": "success", "message": "Documento enviado exitosamente."}],
    )


@api_submissions.delete("/<uuid:sub_uuid>")
@login_required
@permission_required('submissions.api.delete_own')
def delete_submission(sub_uuid):
    # "No existe" y "no es tuya" responden EXACTAMENTE lo mismo (el servicio
    # lanza el mismo NotFoundError): recorriendo ids, un 403 marcaría las
    # entregas reales de otras personas.
    submissions_service.delete_own_submission(current_user.id, sub_uuid)
    return api_ok(True, flash=[{"level": "success", "message": "Archivo eliminado."}])
