# app/routes/api/api_archives.py
from __future__ import annotations
import os
from typing import Set

from flask import Blueprint, request, send_file
from flask_login import login_required, current_user

from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_error, api_not_found, api_server_error
from app.models.archive import Archive
from app.schemas.archives import CreateArchiveIn, UpdateArchiveIn
from app.services import archive_service, template_access_service
from app.services.errors import DomainError
from app.utils.validation import parse_json

api_archives = Blueprint("api_archives", __name__, url_prefix="/api/v1/archives")

# =========================
# Helpers
# =========================
def _permitted_step_ids_for_user() -> Set[int]:
    """Step_ids que el usuario actual puede VER en el catálogo.

    OJO — esto NO es un permiso de escritura. Un Step puede estar enganchado a
    varios programas a la vez, así que "toca uno de mis programas" no reparte
    el catálogo entre coordinadores. Para escribir usa
    `_exclusive_step_ids_for_user` / `_archive_write_denied`.
    """
    return archive_service.permitted_step_ids(current_user.get_accessible_program_ids())


def _exclusive_step_ids_for_user() -> Set[int] | None:
    """Step_ids cuyo CATÁLOGO de documentos puede modificar el usuario actual.

    None si tiene alcance global. La regla (un step compartido sólo lo modifica
    el alcance global) vive en `archive_service.exclusive_step_ids`.
    """
    return archive_service.exclusive_step_ids(current_user.get_accessible_program_ids())

# Los steps que un usuario puede CONSULTAR (descargar plantillas) ya no se
# calculan aquí: la regla es `template_access_service.visible_step_ids`, porque
# `/files/template/<filename>` sirve las mismas plantillas por otra puerta y
# tiene que responder exactamente lo mismo.


def _deny(code: str, message: str, status: int):
    """Denegación con el envelope del proyecto y mensaje en español."""
    return api_error(code, message, status=status, level="danger")


def _archive_write_denied(step_id):
    """
    Guarda de ESCRITURA sobre el catálogo: alta, edición, borrado y plantilla.

    Exige que el step sea exclusivo del alcance del usuario
    (`_exclusive_step_ids_for_user`). Devuelve la respuesta 403 o None.
    """
    exclusive = _exclusive_step_ids_for_user()
    if exclusive is None:          # alcance global
        return None
    try:
        step_id = int(step_id)
    except (TypeError, ValueError):
        step_id = None
    if step_id is not None and step_id in exclusive:
        return None
    return _deny(
        "FORBIDDEN",
        "Esta etapa la comparten varios programas o pertenece a otro, así que "
        "su catálogo de documentos sólo lo puede modificar la Jefatura de "
        "Posgrado.",
        403,
    )


# =========================
# Listado principal
# =========================
@api_archives.route("", methods=["GET"])
@login_required
def list_archives():
    """
    ?include=step → agrega nombre del step
    Estructura:
      id, name, description, is_uploadable, is_downloadable,
      allow_coordinator_upload, allow_extension_request,
      step_id, step_name, template_url, template_name, can_manage
    Filtrado por alcance de coordinador (solo archivos en steps permitidos).
    `can_manage` distingue lo que además puede EDITAR: los steps compartidos
    entre programas se listan pero sólo los modifica la Jefatura de Posgrado.
    """
    include_step = request.args.get("include") == "step"
    is_scoped = current_user.get_accessible_program_ids() is not None
    exclusive = _exclusive_step_ids_for_user()

    if include_step:
        # alcance: usuarios scoped (no globales) sólo ven steps de sus programas accesibles
        permitted = None
        if is_scoped:
            permitted = _permitted_step_ids_for_user()
            if not permitted:
                return api_ok({"items": []})
        rows = archive_service.list_archive_rows_with_step(permitted)
        items = []
        for r in rows:
            (aid, auuid, name, desc, up, down, step_id, step_name, fpath, allow_coord, allow_ext) = r
            public_id = str(auuid) if auuid else None
            items.append({
                # Public handle — it is what the browser puts back in the URL.
                "id": public_id,
                "name": name,
                "description": desc,
                "is_uploadable": bool(up),
                "is_downloadable": bool(down),
                "allow_coordinator_upload": bool(allow_coord),
                "allow_extension_request": bool(allow_ext) if allow_ext is not None else False,
                "step_id": step_id,
                "step_name": step_name,
                "can_manage": exclusive is None or step_id in exclusive,
                "template_url": f"/api/v1/archives/{public_id}/template" if fpath else None,
                "template_name": os.path.basename(fpath) if fpath else None
            })
        return api_ok({"items": items})

    # sin join
    permitted = None
    if is_scoped:
        permitted = _permitted_step_ids_for_user()
        if not permitted:
            return api_ok({"items": []})
    archives = archive_service.list_archives(permitted)
    items = []
    for a in archives:
        allow_ext = getattr(a, "allow_extension_request", False)
        items.append({
            "id": str(a.uuid) if a.uuid else None,
            "name": a.name,
            "description": a.description,
            "is_uploadable": a.is_uploadable,
            "is_downloadable": a.is_downloadable,
            "allow_coordinator_upload": a.allow_coordinator_upload,
            "allow_extension_request": bool(allow_ext),
            "step_id": a.step_id,
            "can_manage": exclusive is None or a.step_id in exclusive,
            "template_url": f"/api/v1/archives/{a.uuid}/template" if a.file_path else None,
            "template_name": os.path.basename(a.file_path) if a.file_path else None
        })
    return api_ok({"items": items})

# =========================
# Steps disponibles (para selects)
# =========================
@api_archives.route("/steps", methods=["GET"])
@login_required
def list_steps():
    """
    Lista de steps. Por defecto devuelve SOLO los permitidos al usuario (scope=permitted).
    Admins pueden pedir scope=all.
    Devuelve: id, name, phase_id, phase_name, can_manage

    `can_manage=False` marca los steps compartidos por varios programas: se
    listan (el coordinador ve el trámite) pero su catálogo no se puede editar
    desde ahí. El front debe deshabilitarlos en los selects de alta/edición.
    """
    scope = request.args.get("scope", "permitted")
    is_scoped = current_user.get_accessible_program_ids() is not None
    exclusive = _exclusive_step_ids_for_user()

    # Usuarios scoped siempre quedan filtrados; los globales sólo si scope=permitted
    permitted = None
    if scope != "all" or is_scoped:
        permitted = _permitted_step_ids_for_user()
        if not permitted:
            return api_ok({"items": []})

    rows = archive_service.list_step_rows(permitted)
    items = [{
        "id": i,
        "name": n,
        "phase_id": pid,
        "phase_name": pn,
        "can_manage": exclusive is None or i in exclusive,
    } for (i, n, pid, pn) in rows]
    return api_ok({"items": items})

# =========================
# Crear archivo
# =========================
@api_archives.route("", methods=["POST"])
@login_required
@permission_required('archives.api.create')
def create_archive():
    data = parse_json(CreateArchiveIn)
    name = data.name
    step_id = data.step_id
    if not name or not step_id:
        return api_error("VALIDATION_ERROR", "El nombre y la etapa son requeridos.", status=400)

    try:
        step_id = int(step_id)
    except (TypeError, ValueError):
        return _deny("VALIDATION_ERROR", "step_id inválido.", 400)

    # Alcance de escritura: sólo steps exclusivos de sus programas. Un step
    # compartido pertenece a toda la institución (ver `_archive_write_denied`).
    denied = _archive_write_denied(step_id)
    if denied:
        return denied

    a = archive_service.create_archive(
        name=name,
        step_id=step_id,
        description=data.description,
        is_downloadable=data.is_downloadable,
        is_uploadable=data.is_uploadable,
        allow_coordinator_upload=data.allow_coordinator_upload,
        allow_extension_request=data.allow_extension_request,
        actor_id=current_user.id,
    )
    return api_ok({"id": str(a.uuid) if a.uuid else None}, status=201)

# =========================
# Actualizar (toggles + meta + mover de step)
# =========================
@api_archives.route("/<uuid:archive_uuid>", methods=["PUT", "PATCH"])
@login_required
@permission_required('archives.api.update')
def update_archive(archive_uuid):
    data = parse_json(UpdateArchiveIn).model_dump(exclude_unset=True)
    # Identificador desconocido o malformado: el mismo 404 que un archive
    # inexistente. El alcance de escritura se resuelve después, por step.
    a = Archive.by_uuid(archive_uuid)
    if not a:
        return api_not_found("Archivo no encontrado")

    # Alcance de escritura sobre el step actual Y sobre el destino si cambia.
    denied = _archive_write_denied(a.step_id)
    if denied:
        return denied
    if "step_id" in data and data["step_id"]:
        try:
            data["step_id"] = int(data["step_id"])
        except (TypeError, ValueError):
            return _deny("VALIDATION_ERROR", "step_id inválido.", 400)
        denied = _archive_write_denied(data["step_id"])
        if denied:
            return denied

    try:
        a = archive_service.update_archive(a, data, actor_id=current_user.id)
        # Handle público, nunca la clave primaria entera.
        return api_ok({"id": str(a.uuid) if a.uuid else None})
    except DomainError:
        raise
    except Exception as e:
        return api_server_error(e, context="archives.update_archive")

# =========================
# Borrar archivo (con seguridad)
# =========================
@api_archives.route("/<uuid:archive_uuid>", methods=["DELETE"])
@login_required
@permission_required('archives.api.delete')
def delete_archive(archive_uuid):
    force = request.args.get("force") in ("1", "true", "True", "yes")
    a = Archive.by_uuid(archive_uuid)
    if not a:
        return api_not_found("Archivo no encontrado")
    # El id interno sigue mandando en disco: `_templates_dir_for` y las rutas
    # de plantilla usan el entero, y los archivos NO se mueven.
    archive_id = a.id
    archive_public_id = str(a.uuid) if a.uuid else None

    # Alcance de escritura por step. El borrado arrastra las entregas de todos
    # los programas que usan esa etapa, así que exige step exclusivo.
    denied = _archive_write_denied(a.step_id)
    if denied:
        return denied

    cnt = archive_service.count_submissions(archive_id)

    if cnt and not force:
        return api_error("CONFLICT", f"Hay {cnt} entregas relacionadas. Marca «Eliminar forzado» para eliminar.", status=409)

    try:
        archive_service.delete_archive(a, force=force, actor_id=current_user.id)
        return api_ok({"deleted": archive_public_id})
    except DomainError:
        raise
    except Exception as e:
        return api_server_error(e, context=f"archives.delete_archive id={archive_id}")

# =========================
# Plantillas
# =========================
@api_archives.route("/<uuid:archive_uuid>/template", methods=["POST"])
@login_required
@permission_required('archives.api.manage_template')
def upload_template(archive_uuid):
    a = Archive.by_uuid(archive_uuid)
    if not a:
        return api_not_found("Archivo no encontrado")
    archive_id = a.id

    # Alcance de escritura por step: sin esto un coordinador sobrescribía la
    # plantilla oficial que descargan los aspirantes de otro programa. Como el
    # step es compartido, "toca mi programa" no basta: tiene que ser mío entero.
    denied = _archive_write_denied(a.step_id)
    if denied:
        return denied

    if "file" not in request.files:
        return api_error("VALIDATION_ERROR", "Archivo no provisto", status=400)
    fs = request.files["file"]
    if not fs or not fs.filename:
        return api_error("VALIDATION_ERROR", "Nombre de archivo inválido", status=400)
    try:
        fname = archive_service.upload_template(a, fs, actor_id=current_user.id)
        public_id = str(a.uuid) if a.uuid else None
        return api_ok({"id": public_id, "template_url": f"/api/v1/archives/{public_id}/template", "template_name": fname})
    except DomainError:
        # Bad extension / missing extension: Spanish message, nothing changed.
        raise
    except Exception as e:
        return api_server_error(e, context="archives.upload_template")

@api_archives.route("/<uuid:archive_uuid>/template", methods=["GET"])
@login_required
def download_template(archive_uuid):
    # Identificador desconocido, archive sin plantilla y plantilla fuera del
    # alcance: los tres devuelven el mismo 404 con el mismo texto.
    a = Archive.by_uuid(archive_uuid)
    if not a or not a.file_path:
        return api_not_found("Plantilla no disponible")
    archive_id = a.id

    # `is_downloadable` marca las plantillas publicadas: son formatos en
    # blanco que la página del programa ofrece a cualquier interesado, así que
    # siguen abiertas a cualquier usuario autenticado.
    #
    # Las que NO son descargables son material interno: sólo las ve quien
    # administra ese step o quien cursa un programa que lo incluye.
    # 404 deliberado: quien no ve el step tampoco debe confirmar que existe.
    #
    # El predicado es el compartido con `/files/template/<filename>`, que sirve
    # estas mismas plantillas por otra puerta.
    if not template_access_service.may_download_archive_template(current_user, a):
        return api_not_found("Plantilla no disponible")

    abs_path, fname = archive_service.template_abs_path(a)
    if not abs_path or not os.path.exists(abs_path):
        return api_not_found("Archivo no encontrado en el servidor")
    return send_file(abs_path, as_attachment=True, download_name=fname or f"plantilla_{archive_id}")
