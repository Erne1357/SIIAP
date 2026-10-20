"""Flow 4 — the applicant's own pages and a document upload."""

import re

import pytest
from playwright.sync_api import expect

import accounts as acc
from audit import audit_page, settle

pytestmark = pytest.mark.e2e

#: Smallest valid-looking PDF; the app only checks the extension and size.
TINY_PDF = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
            b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
            b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 3 3]>>endobj\n'
            b'trailer<</Root 1 0 R>>\n%%EOF\n')


def mark_page(page):
    """Tag the current document so a later reload (marker gone) can be told apart."""
    page.evaluate('() => { window.__e2e_marker = true; }')


def wait_for_reload(page):
    """
    admission.js sets location.hash and then calls location.reload(). The hash
    change alone already satisfies expect_navigation(), so wait for the marker
    set by mark_page() to disappear: that only happens on the real reload.
    """
    page.wait_for_function('() => window.__e2e_marker === undefined')
    settle(page)


@pytest.fixture
def applicant(login_as):
    return login_as(acc.APPLICANT)


@pytest.fixture
def no_submission(page, applicant):
    """Start from a state with no uploaded document (a previous run may have left one)."""
    page.goto(f'/programs/admission/{acc.PROGRAM_SLUG}')
    token = page.locator('meta[name="csrf-token"]').get_attribute('content')
    for button in page.locator('[data-delete-submission]').all():
        uuid = button.get_attribute('data-delete-submission')
        page.request.delete(f'/api/v1/submissions/{uuid}', headers={'X-CSRFToken': token})


def test_applicant_dashboard_renders(page, applicant):
    page.goto('/user/dashboard')
    settle(page)
    expect(page.get_by_role('heading', level=1, name='Panel de control')).to_be_attached()
    expect(page.locator('#main-content')).to_contain_text(acc.PROGRAM_NAME)
    problems, _ = audit_page(page)
    assert not problems, problems


def test_applicant_profile_renders(page, applicant):
    page.goto('/user/profile')
    settle(page)
    expect(page.get_by_role('heading', level=1)).to_contain_text('Ana Aspirante')


def test_applicant_sidebar_links_to_admission(page, applicant):
    page.goto('/user/dashboard')
    # Menu is organised by workflow: the Admisión group starts collapsed on the dashboard.
    sidebar = page.locator('#sidebar')
    sidebar.get_by_role('button', name='Admisión').click()
    sidebar.get_by_role('link', name='Mi admisión').click()
    expect(page).to_have_url(re.compile(rf'/programs/admission/{acc.PROGRAM_SLUG}$'))


def test_admission_page_lists_the_required_document(page, applicant, no_submission):
    page.goto(f'/programs/admission/{acc.PROGRAM_SLUG}')
    settle(page)
    expect(page.get_by_role('heading', level=1, name='Proceso de admisión')).to_be_visible()
    expect(page.get_by_role('tab', name=re.compile(acc.STEP_NAME))).to_be_visible()
    table = page.get_by_role('table', name=re.compile('Documentos requeridos'))
    expect(table).to_be_visible()
    expect(table.get_by_text(acc.ARCHIVE_NAME)).to_be_visible()
    expect(table.get_by_text('Pendiente').first).to_be_visible()
    problems, _ = audit_page(page)
    assert not problems, problems


def test_other_roles_cannot_open_the_admission_page(page, login_as):
    login_as(acc.COORDINATOR)
    page.goto(f'/programs/admission/{acc.PROGRAM_SLUG}')
    expect(page.locator('#flash-container')).to_contain_text('No tienes permiso')


def test_upload_replace_and_delete_a_pdf(page, applicant, no_submission):
    page.goto(f'/programs/admission/{acc.PROGRAM_SLUG}')
    settle(page)
    row = page.get_by_role('row', name=re.compile(acc.ARCHIVE_NAME))
    expect(row.get_by_text('Pendiente')).to_be_visible()

    # --- upload -----------------------------------------------------------
    row.get_by_role('button', name=f'Subir el documento {acc.ARCHIVE_NAME}').click()
    dialog = page.get_by_role('dialog', name='Subir documento')
    expect(dialog).to_be_visible()
    dialog.get_by_label('Seleccionar archivo').set_input_files(
        {'name': 'acta.pdf', 'mimeType': 'application/pdf', 'buffer': TINY_PDF})
    mark_page(page)
    dialog.get_by_role('button', name='Subir').click()
    wait_for_reload(page)  # the page reloads after a successful upload
    row = page.get_by_role('row', name=re.compile(acc.ARCHIVE_NAME))
    try:
        expect(row.get_by_text('En revisión')).to_be_visible()
        expect(row.get_by_role('link', name=re.compile('Ver el documento'))).to_be_visible()

        # --- the uploaded file is served back to its owner ------------------
        href = row.get_by_role('link', name=re.compile('Ver el documento')).get_attribute('href')
        served = page.request.get(href)
        assert served.status == 200
        assert served.body().startswith(b'%PDF')
    finally:
        # --- delete (cleans up so the test is repeatable) -------------------
        row.get_by_role('button', name=f'Eliminar el archivo de {acc.ARCHIVE_NAME}').click()
        mark_page(page)
        page.get_by_role('button', name='Sí, eliminar').click()
        wait_for_reload(page)
    row = page.get_by_role('row', name=re.compile(acc.ARCHIVE_NAME))
    expect(row.get_by_text('Pendiente')).to_be_visible()


def test_upload_rejects_non_pdf_files_in_spanish(page, applicant, no_submission):
    page.goto(f'/programs/admission/{acc.PROGRAM_SLUG}')
    settle(page)
    row = page.get_by_role('row', name=re.compile(acc.ARCHIVE_NAME))
    row.get_by_role('button', name=f'Subir el documento {acc.ARCHIVE_NAME}').click()
    dialog = page.get_by_role('dialog', name='Subir documento')
    dialog.get_by_label('Seleccionar archivo').set_input_files(
        {'name': 'notas.txt', 'mimeType': 'text/plain', 'buffer': b'hola'})
    dialog.get_by_role('button', name='Subir').click()
    expect(page.locator('#flash-container')).to_contain_text('Solo se permiten archivos PDF')
    expect(dialog).to_be_visible()
