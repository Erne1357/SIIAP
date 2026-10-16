"""Unit tests for app/utils/files.py using a tmp_path based config."""

import io
import os
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from app.utils import files as F


def fs(name='a.pdf', data=b'x'):
    return FileStorage(stream=io.BytesIO(data), filename=name)


# --- _validate_ext ----------------------------------------------------------

@pytest.mark.parametrize('name,expected', [
    ('a.pdf', 'pdf'), ('A.PDF', 'pdf'), ('x.y.docx', 'docx'), ('.pdf', 'pdf'), ('a.Doc', 'doc'),
])
def test_validate_ext_allowed(name, expected):
    assert F._validate_ext(name, {'pdf', 'doc', 'docx'}) == expected


@pytest.mark.parametrize('name', ['noext', ''])
def test_validate_ext_without_extension(name):
    with pytest.raises(BadRequest) as e:
        F._validate_ext(name, {'pdf'})
    assert 'sin extensión' in e.value.description


@pytest.mark.parametrize('name', ['a.exe', 'a.pdf.exe', 'a.php', 'a.', 'a.pdf ', 'a.svg', 'shell.sh'])
def test_validate_ext_rejects_disallowed(name):
    with pytest.raises(BadRequest) as e:
        F._validate_ext(name, {'pdf'})
    assert 'no permitida' in e.value.description


def test_validate_ext_double_extension_uses_last():
    assert F._validate_ext('evil.php.pdf', {'pdf'}) == 'pdf'


def test_uuid_name_format():
    n = F._uuid_name('PNG')
    stem, ext = n.split('.')
    assert ext == 'png' and len(stem) == 32 and int(stem, 16) >= 0
    assert F._uuid_name('png') != F._uuid_name('png')


# --- abs_path_from_db -------------------------------------------------------

def test_abs_path_normal(tmp_path):
    p = F.abs_path_from_db('42/avatar.webp', tmp_path)
    assert Path(p) == tmp_path / '42' / 'avatar.webp'


@pytest.mark.parametrize('rel', [
    '../secret.txt', '../../etc/passwd', '42/../../secret', '..', '/etc/passwd',
    '..\\..\\secret' if os.sep == '\\' else '../x/../../y', 'a/../../b',
])
def test_abs_path_rejects_traversal(tmp_path, rel):
    assert F.abs_path_from_db(rel, tmp_path) is None


def test_abs_path_inner_dotdot_that_stays_inside_is_ok(tmp_path):
    p = F.abs_path_from_db('a/../b.txt', tmp_path)
    assert p is not None and Path(p).parent == tmp_path


def test_abs_path_empty_returns_base(tmp_path):
    p = F.abs_path_from_db('', tmp_path)
    assert p is None or Path(p) == tmp_path


def test_abs_path_sibling_prefix_not_confused(tmp_path):
    base = tmp_path / 'uploads'
    (tmp_path / 'uploads_evil').mkdir()
    assert F.abs_path_from_db('../uploads_evil/x', base) is None


def test_abs_path_symlink_inside_is_lexical_only(tmp_path):
    """safe_join is lexical: a symlink in base pointing outside is NOT resolved.

    Documented here so a future change to resolve() is a conscious decision."""
    outside = tmp_path / 'outside'
    outside.mkdir()
    base = tmp_path / 'base'
    base.mkdir()
    try:
        (base / 'link').symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks unavailable')
    p = F.abs_path_from_db('link/f.txt', base)
    assert p is not None and Path(p) == base / 'link' / 'f.txt'


# --- save_* with tmp config -------------------------------------------------

def test_save_avatar(app):
    rel = F.save_avatar(fs('me.PNG'), 7)
    uid, name = rel.split('/')
    assert uid == '7' and name.endswith('.png')
    assert (app.config['AVATAR_FOLDER'] / '7' / name).read_bytes() == b'x'


def test_save_avatar_rejects_pdf(app):
    with pytest.raises(BadRequest):
        F.save_avatar(fs('me.pdf'), 7)


def test_save_avatar_unique_names(app):
    assert F.save_avatar(fs('a.jpg'), 1) != F.save_avatar(fs('a.jpg'), 1)


def test_save_user_doc(app):
    rel = F.save_user_doc(fs('orig.pdf', b'data'), 5, 'admission', 'Acta de Nacimiento.pdf')
    assert rel == '5/admission/Acta_de_Nacimiento.pdf'
    assert (app.config['USER_DOCS_FOLDER'] / '5' / 'admission' / 'Acta_de_Nacimiento.pdf').read_bytes() == b'data'


def test_save_user_doc_name_traversal_sanitized(app):
    rel = F.save_user_doc(fs('o.pdf'), 5, 'admission', '../../evil.pdf')
    assert '..' not in rel and rel.startswith('5/admission/')
    assert (app.config['USER_DOCS_FOLDER'] / '5' / 'admission' / 'evil.pdf').exists()


def test_save_user_doc_extension_from_upload_not_name(app):
    rel = F.save_user_doc(fs('o.docx'), 5, 'permanence', 'cv.pdf')
    assert rel.endswith('/cv.docx')


def test_save_user_doc_rejects_bad_ext(app):
    with pytest.raises(BadRequest):
        F.save_user_doc(fs('o.exe'), 5, 'admission', 'x.pdf')


def test_save_user_doc_overwrites_same_name(app):
    F.save_user_doc(fs('o.pdf', b'one'), 5, 'admission', 'a.pdf')
    F.save_user_doc(fs('o.pdf', b'two'), 5, 'admission', 'a.pdf')
    assert (app.config['USER_DOCS_FOLDER'] / '5' / 'admission' / 'a.pdf').read_bytes() == b'two'


def test_save_system_template(app):
    name = F.save_system_template(fs('t.docx', b'tpl'), 'Formato Beca.docx')
    assert name == 'Formato_Beca.docx'
    assert (app.config['TEMPLATE_STORE'] / name).read_bytes() == b'tpl'


def test_save_system_template_rejects_bad_ext(app):
    with pytest.raises(BadRequest):
        F.save_system_template(fs('t.zip'), 'x.zip')


def test_docs_dir_and_avatar_dir(app):
    assert F.docs_dir(3, 'admission') == app.config['USER_DOCS_FOLDER'] / '3' / 'admission'
    assert F.avatar_dir(3) == app.config['AVATAR_FOLDER'] / '3'


# --- events -----------------------------------------------------------------

@pytest.mark.parametrize('kind,expected', [(None, ''), ('gallery', 'gallery'), ('host', 'hosts'), ('cover', '')])
def test_events_dir(app, kind, expected):
    base = app.config['EVENTS_FOLDER'] / '9'
    assert F.events_dir(9, kind) == (base / expected if expected else base)


def test_save_event_image_cover_replaces_previous_extensions(app):
    first = F.save_event_image(fs('a.jpg'), 1, 'cover')
    assert first == '1/cover.jpg'
    second = F.save_event_image(fs('b.png'), 1, 'cover')
    assert second == '1/cover.png'
    assert not (app.config['EVENTS_FOLDER'] / '1' / 'cover.jpg').exists()
    assert (app.config['EVENTS_FOLDER'] / '1' / 'cover.png').exists()


def test_save_event_image_gallery_and_host_paths(app):
    g = F.save_event_image(fs('a.webp'), 2, 'gallery')
    h = F.save_event_image(fs('a.webp'), 2, 'host')
    assert g.startswith('2/gallery/') and h.startswith('2/hosts/')
    assert (app.config['EVENTS_FOLDER'] / g).exists() and (app.config['EVENTS_FOLDER'] / h).exists()


def test_save_event_image_invalid_kind(app):
    with pytest.raises(BadRequest):
        F.save_event_image(fs('a.jpg'), 1, 'banner')


def test_save_event_image_too_large(app):
    app.config['MAX_EVENT_IMAGE_BYTES'] = 10
    with pytest.raises(BadRequest) as e:
        F.save_event_image(fs('a.jpg', b'x' * 11), 1, 'cover')
    assert 'excede' in e.value.description


def test_save_event_image_exact_limit_ok(app):
    app.config['MAX_EVENT_IMAGE_BYTES'] = 10
    assert F.save_event_image(fs('a.jpg', b'x' * 10), 1, 'cover') == '1/cover.jpg'


def test_save_event_image_bad_ext(app):
    with pytest.raises(BadRequest):
        F.save_event_image(fs('a.gif'), 1, 'cover')


def test_delete_event_image_file(app):
    rel = F.save_event_image(fs('a.jpg'), 3, 'gallery')
    assert F.delete_event_image_file(rel) is True
    assert F.delete_event_image_file(rel) is False


@pytest.mark.parametrize('rel', ['', None])
def test_delete_event_image_file_empty(app, rel):
    assert F.delete_event_image_file(rel) is False


def test_delete_event_image_file_traversal_does_not_delete_outside(app, tmp_path):
    victim = tmp_path / 'uploads' / 'victim.txt'
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text('keep')
    assert F.delete_event_image_file('../victim.txt') is False
    assert victim.exists()


def test_delete_event_image_file_directory_not_deleted(app):
    d = app.config['EVENTS_FOLDER'] / '4' / 'gallery'
    d.mkdir(parents=True)
    assert F.delete_event_image_file('4/gallery') is False
    assert d.exists()


def test_delete_all_event_files(app):
    F.save_event_image(fs('a.jpg'), 5, 'cover')
    F.save_event_image(fs('a.jpg'), 5, 'gallery')
    F.save_event_image(fs('a.jpg'), 5, 'host')
    assert F.delete_all_event_files(5) == 3
    assert not (app.config['EVENTS_FOLDER'] / '5').exists()


def test_delete_all_event_files_idempotent(app):
    assert F.delete_all_event_files(99) == 0
    assert F.delete_all_event_files(99) == 0
