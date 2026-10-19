"""
Document template service — persistence of institutional `DocumentTemplate`
rows and their files (HTML / DOCX under `instance/templates_sys`).

Backs `app/routes/api/admin/document_template_api.py`. Scope decisions stay in
`template_access_service`; this module only reads and writes.
"""
from __future__ import annotations

import os
from typing import Optional

from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.models.document_template import DocumentTemplate
from app.utils.datetime_utils import now_local


def templates_sys_dir() -> str:
    """Root directory of the stored template files."""
    return current_app.config.get(
        'TEMPLATES_SYS_FOLDER',
        os.path.join(current_app.instance_path, 'templates_sys'),
    )


def query_templates(*, document_type: Optional[str] = None,
                    program_id: Optional[int] = None,
                    active_only: bool = False) -> list:
    """Templates ordered by type and name, optionally filtered (no scope applied)."""
    q = DocumentTemplate.query
    if document_type:
        q = q.filter_by(document_type=document_type)
    if program_id is not None:
        q = q.filter_by(program_id=program_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.order_by(DocumentTemplate.document_type, DocumentTemplate.name).all()


def create_template(*, file, name: str, document_type: str,
                    program_id: Optional[int], description: Optional[str],
                    created_by: int) -> DocumentTemplate:
    """Save the uploaded file under `<document_type>/` and register the row."""
    ext = file.filename.rsplit('.', 1)[1].lower()

    subdir = os.path.join(templates_sys_dir(), document_type)
    os.makedirs(subdir, exist_ok=True)

    timestamp = now_local().strftime('%Y%m%d_%H%M%S')
    safe_name = secure_filename(f"{timestamp}_{file.filename}")
    abs_path = os.path.join(subdir, safe_name)
    file.save(abs_path)

    template = DocumentTemplate(
        program_id=program_id,
        document_type=document_type,
        name=name,
        file_path=os.path.join(document_type, safe_name),
        file_type=ext,
        description=description,
        is_active=True,
        created_by=created_by,
    )
    db.session.add(template)
    db.session.commit()
    return template


def update_template(template: DocumentTemplate, fields: dict) -> DocumentTemplate:
    """Apply the PRESENT keys of `fields` (name, description, is_active)."""
    # `name: null` means "not sent": an empty name is never written.
    if fields.get('name') is not None and fields['name'].strip():
        template.name = fields['name'].strip()
    if 'description' in fields:
        template.description = fields['description'] or None
    if 'is_active' in fields:
        template.is_active = bool(fields['is_active'])
    db.session.commit()
    return template


def delete_template(template: DocumentTemplate) -> None:
    """Remove the physical file (best effort) and the row."""
    abs_path = os.path.join(templates_sys_dir(), template.file_path)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass  # already gone, carry on
    db.session.delete(template)
    db.session.commit()
