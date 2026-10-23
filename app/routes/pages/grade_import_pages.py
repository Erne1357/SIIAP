# app/routes/pages/grade_import_pages.py
"""
Page routes for importing grade history from past periods (phase 6B3).
Rules live in `history_import_service`; the preview never writes and `execute`
re-validates the CSV text it receives.
"""
from flask import Blueprint, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required

from app.services import history_import_service
from app.services.history_import_service import HistoryImportError
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import current_accessible_program_ids, permission_required

pages_grade_import = Blueprint('pages_grade_import', __name__, url_prefix='/grade-import')

_PREVIEW_PARTIAL = 'grade_import/_partials/_preview.html'
_RESULT_PARTIAL = 'grade_import/_partials/_result.html'
_MAX_BYTES = 1024 * 1024


def _uploaded_text() -> str:
    """The uploaded CSV decoded as UTF-8 (BOM tolerated); refuses missing/oversized/odd files."""
    upload = request.files.get('file')
    if upload is None or not upload.filename:
        raise HistoryImportError('Selecciona un archivo CSV.')
    raw = upload.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise HistoryImportError('El archivo excede el tamaño máximo de 1 MB.')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise HistoryImportError('El archivo debe estar codificado en UTF-8.')


@pages_grade_import.route('/')
@login_required
@permission_required('grades.page.import_history')
def index():
    return render_template('grade_import/index.html',
                           columns_template=history_import_service.TEMPLATE.strip())


@pages_grade_import.route('/preview', methods=['POST'])
@login_required
@permission_required('grades.page.import_history')
def preview():
    if not is_htmx():
        return redirect(url_for('pages_grade_import.index'))
    text = _uploaded_text()
    summary = history_import_service.preview(text, current_accessible_program_ids())
    return render_fragment(_PREVIEW_PARTIAL, summary=summary, csv_text=text)


@pages_grade_import.route('/execute', methods=['POST'])
@login_required
@permission_required('grades.page.import_history')
def execute():
    if not is_htmx():
        return redirect(url_for('pages_grade_import.index'))
    summary = history_import_service.execute(
        request.form.get('csv_text', ''), current_user.id, current_accessible_program_ids())
    return hx_flash(render_fragment(_RESULT_PARTIAL, summary=summary), 'success',
                    f'Se importaron {summary["valid_count"]} calificaciones.')


@pages_grade_import.route('/template.csv')
@login_required
@permission_required('grades.page.import_history')
def template_csv():
    return Response(history_import_service.TEMPLATE, mimetype='text/csv',
                    headers={'Content-Disposition':
                             'attachment; filename=plantilla_historial.csv'})
