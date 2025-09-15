# app/routes/api/api_archives.py
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Set

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from sqlalchemy import select, func, join

from werkzeug.utils import secure_filename

from app import db
from app.utils.auth import roles_required
from app.models.archive import Archive
from app.models.step import Step
from app.models.phase import Phase
from app.models.program import Program
from app.models.program_step import ProgramStep
from app.models.submission import Submission

api_archives = Blueprint("api_archives", __name__, url_prefix="/api/v1/archives")

# =========================
# Helpers
# =========================
def _instance_path() -> str:
    return current_app.instance_path

def _templates_dir_for(archive_id: int) -> str:
    return os.path.join(_instance_path(), "uploads", "templates", "archives", str(archive_id))

def _store_template(archive_id: int, file_storage) -> tuple[str, str]:
    os.makedirs(_templates_dir_for(archive_id), exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = secure_filename(file_storage.filename or f"plantilla_{archive_id}.bin")
    fname = f"{stamp}_{fname}"
    abs_path = os.path.join(_templates_dir_for(archive_id), fname)
    file_storage.save(abs_path)
    rel_path = os.path.relpath(abs_path, _instance_path())
    return rel_path, fname

def _abs_path_from_archive(a: Archive) -> tuple[str|None, str|None]:
    if not a.file_path:
        return None, None
    fpath = a.file_path
    abs_path = os.path.join(_instance_path(), fpath) if not os.path.isabs(fpath) else fpath
    return abs_path, os.path.basename(abs_path)

def _permitted_step_ids_for_user() -> Set[int]:
    """Devuelve los step_ids que el usuario actual puede administrar."""
    role = (current_user.role.name if current_user.role else None)
    if role in ("postgraduate_admin", "program_admin"):
        ids = db.session.execute(select(Step.id)).scalars().all()
        return set(ids)
    if role == "coordinator":
        prog_ids = db.session.execute(
            select(Program.id).where(Program.coordinator_id == current_user.id)
        ).scalars().all()
        if not prog_ids:
            return set()
        step_ids = db.session.execute(
            select(ProgramStep.step_id).where(ProgramStep.program_id.in_(prog_ids))
        ).scalars().all()
        return set(step_ids)
    return set()

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
      step_id, step_name, template_url, template_name
    Filtrado por alcance de coordinador (solo archivos en steps permitidos).
    """
    include_step = request.args.get("include") == "step"
    role = (current_user.role.name if current_user.role else None)

    if include_step:
        j = join(Archive, Step, Archive.step_id == Step.id)
        sel = select(
            Archive.id, Archive.name, Archive.description,
            Archive.is_uploadable, Archive.is_downloadable,
            Archive.step_id, Step.name.label("step_name"),
            Archive.file_path,
            getattr(Archive, "allow_coordinator_upload"),
            getattr(Archive, "allow_extension_request", None),
        ).select_from(j)
        # alcance coordinador
        if role == "coordinator":
            permitted = _permitted_step_ids_for_user()
            if not permitted:
                return jsonify({"ok": True, "items": []}), 200
            sel = sel.where(Archive.step_id.in_(permitted))
        rows = db.session.execute(sel).all()
        items = []
        for r in rows:
            (aid, name, desc, up, down, step_id, step_name, fpath, allow_coord, allow_ext) = r
            items.append({
                "id": aid,
                "name": name,
                "description": desc,
                "is_uploadable": bool(up),
                "is_downloadable": bool(down),
                "allow_coordinator_upload": bool(allow_coord),
                "allow_extension_request": bool(allow_ext) if allow_ext is not None else False,
                "step_id": step_id,
                "step_name": step_name,
                "template_url": f"/api/v1/archives/{aid}/template" if fpath else None,
                "template_name": os.path.basename(fpath) if fpath else None
            })
        return jsonify({"ok": True, "items": items}), 200

    # sin join
    sel = select(Archive)
    if role == "coordinator":
        permitted = _permitted_step_ids_for_user()
        if not permitted:
            return jsonify({"ok": True, "items": []}), 200
        sel = sel.where(Archive.step_id.in_(permitted))
    archives = db.session.execute(sel).scalars().all()
    items = []
    for a in archives:
        allow_ext = getattr(a, "allow_extension_request", False)
        items.append({
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "is_uploadable": a.is_uploadable,
            "is_downloadable": a.is_downloadable,
            "allow_coordinator_upload": a.allow_coordinator_upload,
            "allow_extension_request": bool(allow_ext),
            "step_id": a.step_id,
            "template_url": f"/api/v1/archives/{a.id}/template" if a.file_path else None,
            "template_name": os.path.basename(a.file_path) if a.file_path else None
        })
    return jsonify({"ok": True, "items": items}), 200

# =========================
# Steps disponibles (para selects)
# =========================
@api_archives.route("/steps", methods=["GET"])
@login_required
def list_steps():
    """
    Lista de steps. Por defecto devuelve SOLO los permitidos al usuario (scope=permitted).
    Admins pueden pedir scope=all.
    Devuelve: id, name, phase_id, phase_name
    """
    scope = request.args.get("scope", "permitted")
    role = (current_user.role.name if current_user.role else None)

    j = join(Step, Phase, Step.phase_id == Phase.id)
    sel = select(
        Step.id, Step.name, Step.phase_id, Phase.name.label("phase_name")
    ).select_from(j)

    if scope != "all" or role == "coordinator":
        permitted = _permitted_step_ids_for_user()
        if not permitted:
            return jsonify({"ok": True, "items": []}), 200
        sel = sel.where(Step.id.in_(permitted))

    rows = db.session.execute(sel.order_by(Phase.id, Step.id)).all()
    items = [{"id": i, "name": n, "phase_id": pid, "phase_name": pn} for (i, n, pid, pn) in rows]
    return jsonify({"ok": True, "items": items}), 200

# =========================
# Crear archivo
# =========================
@api_archives.route("", methods=["POST"])
@login_required
@roles_required("postgraduate_admin", "program_admin", "coordinator")
def create_archive():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    step_id = data.get("step_id")
    if not name or not step_id:
        return jsonify({"ok": False, "error": "name y step_id son requeridos"}), 400

    # permiso por step
    role = (current_user.role.name if current_user.role else None)
    if role == "coordinator":
        permitted = _permitted_step_ids_for_user()
        if step_id not in permitted:
            return jsonify({"ok": False, "error": "No tienes permiso para crear en ese step"}), 403

    a = Archive(
        name=name,
        description=data.get("description"),
        file_path=None,
        step_id=step_id,
        is_downloadable=bool(data.get("is_downloadable", False)),
        is_uploadable=bool(data.get("is_uploadable", False)),
    )
    if hasattr(Archive, "allow_coordinator_upload"):
        a.allow_coordinator_upload = bool(data.get("allow_coordinator_upload", False))
    if hasattr(Archive, "allow_extension_request"):
        setattr(a, "allow_extension_request", bool(data.get("allow_extension_request", False)))

    db.session.add(a)
    db.session.commit()
    return jsonify({"ok": True, "id": a.id}), 201

# =========================
# Actualizar (toggles + meta + mover de step)
# =========================
@api_archives.route("/<int:archive_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("postgraduate_admin", "program_admin", "coordinator")
def update_archive(archive_id: int):
    data = request.get_json() or {}
    a = db.session.get(Archive, archive_id)
    if not a:
        return jsonify({"ok": False, "error": "Archivo no encontrado"}), 404

    # permiso por step (actual y destino si cambia)
    role = (current_user.role.name if current_user.role else None)
    if role == "coordinator":
        permitted = _permitted_step_ids_for_user()
        if a.step_id not in permitted:
            return jsonify({"ok": False, "error": "No puedes modificar este archivo"}), 403
        if "step_id" in data and data["step_id"] not in permitted:
            return jsonify({"ok": False, "error": "No puedes mover a ese step"}), 403

    try:
        # meta
        if "name" in data and data["name"].strip():
            a.name = data["name"].strip()
        if "description" in data:
            a.description = data["description"]
        if "step_id" in data and data["step_id"]:
            a.step_id = int(data["step_id"])

        # toggles
        if "is_uploadable" in data:
            a.is_uploadable = bool(data["is_uploadable"])
        if "is_downloadable" in data:
            a.is_downloadable = bool(data["is_downloadable"])
        if "allow_coordinator_upload" in data and hasattr(Archive, "allow_coordinator_upload"):
            a.allow_coordinator_upload = bool(data["allow_coordinator_upload"])
        if "allow_extension_request" in data and hasattr(Archive, "allow_extension_request"):
            setattr(a, "allow_extension_request", bool(data["allow_extension_request"]))

        db.session.commit()
        return jsonify({"ok": True, "id": a.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

# =========================
# Borrar archivo (con seguridad)
# =========================
@api_archives.route("/<int:archive_id>", methods=["DELETE"])
@login_required
@roles_required("postgraduate_admin", "program_admin", "coordinator")
def delete_archive(archive_id: int):
    force = request.args.get("force") in ("1", "true", "True", "yes")
    a = db.session.get(Archive, archive_id)
    if not a:
        return jsonify({"ok": False, "error": "Archivo no encontrado"}), 404

    # permiso por step
    role = (current_user.role.name if current_user.role else None)
    if role == "coordinator":
        permitted = _permitted_step_ids_for_user()
        if a.step_id not in permitted:
            return jsonify({"ok": False, "error": "No puedes borrar este archivo"}), 403

    # Revisar submissions relacionados
    cnt = db.session.execute(
        select(func.count(Submission.id)).where(Submission.archive_id == archive_id)
    ).scalar_one()
    if cnt and not force:
        return jsonify({"ok": False, "requires_force": True, "message": f"Hay {cnt} submissions relacionados. Usa ?force=true para eliminar."}), 409

    try:
        db.session.delete(a)
        db.session.commit()
        return jsonify({"ok": True, "deleted": archive_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

# =========================
# Plantillas
# =========================
@api_archives.route("/<int:archive_id>/template", methods=["POST"])
@login_required
@roles_required("postgraduate_admin", "program_admin")
def upload_template(archive_id: int):
    a = db.session.get(Archive, archive_id)
    if not a:
        return jsonify({"ok": False, "error": "Archivo no encontrado"}), 404
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Archivo no provisto"}), 400
    fs = request.files["file"]
    if not fs or not fs.filename:
        return jsonify({"ok": False, "error": "Nombre de archivo inválido"}), 400
    try:
        rel_path, fname = _store_template(archive_id, fs)
        a.file_path = rel_path
        db.session.commit()
        return jsonify({"ok": True, "id": a.id, "template_url": f"/api/v1/archives/{a.id}/template", "template_name": fname}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

@api_archives.route("/<int:archive_id>/template", methods=["GET"])
@login_required
def download_template(archive_id: int):
    a = db.session.get(Archive, archive_id)
    if not a or not a.file_path:
        return jsonify({"ok": False, "error": "Plantilla no disponible"}), 404
    abs_path, fname = _abs_path_from_archive(a)
    if not abs_path or not os.path.exists(abs_path):
        return jsonify({"ok": False, "error": "Archivo no encontrado en el servidor"}), 404
    return send_file(abs_path, as_attachment=True, download_name=fname or f"plantilla_{archive_id}")
