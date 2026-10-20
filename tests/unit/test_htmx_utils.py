"""app/utils/htmx.py: detection, HX-Trigger merging and response builders."""

import json

from flask import Flask, make_response
from jinja2 import DictLoader

from app.utils import htmx as hx


def test_is_htmx_true_only_for_true_header(app):
    with app.test_request_context(headers={'HX-Request': 'true'}):
        assert hx.is_htmx() and hx.wants_html_fragment()
    with app.test_request_context(headers={'HX-Request': 'false'}):
        assert not hx.is_htmx()
    with app.test_request_context():
        assert not hx.is_htmx() and not hx.wants_html_fragment()


def test_hx_trigger_sets_json_payload(app):
    with app.test_request_context():
        resp = hx.hx_trigger(make_response('x'), 'siiap:done', {'id': 3})
        assert json.loads(resp.headers['HX-Trigger']) == {'siiap:done': {'id': 3}}


def test_hx_trigger_without_payload_uses_empty_string(app):
    with app.test_request_context():
        resp = hx.hx_trigger(make_response('x'), 'siiap:ping')
        assert json.loads(resp.headers['HX-Trigger']) == {'siiap:ping': ''}


def test_hx_trigger_merges_with_existing_events(app):
    with app.test_request_context():
        resp = hx.hx_trigger(make_response('x'), 'a', 1)
        resp = hx.hx_trigger(resp, 'b', 2)
        assert json.loads(resp.headers['HX-Trigger']) == {'a': 1, 'b': 2}


def test_hx_trigger_accepts_plain_name_list_header(app):
    with app.test_request_context():
        resp = make_response('x')
        resp.headers['HX-Trigger'] = 'one, two'
        resp = hx.hx_trigger(resp, 'three', {'k': 1})
        assert json.loads(resp.headers['HX-Trigger']) == {'one': '', 'two': '', 'three': {'k': 1}}


def test_hx_trigger_accepts_plain_body_value(app):
    with app.test_request_context():
        resp = hx.hx_trigger('<p>x</p>', 'e')
        assert resp.get_data(as_text=True) == '<p>x</p>' and 'HX-Trigger' in resp.headers


def test_hx_trigger_is_ascii_for_spanish_text(app):
    with app.test_request_context():
        resp = hx.hx_flash(make_response(''), 'success', 'Operación ¡lista! ñ')
        resp.headers['HX-Trigger'].encode('ascii')
        payload = json.loads(resp.headers['HX-Trigger'])['siiap:flash']
        assert payload == {'level': 'success', 'message': 'Operación ¡lista! ñ'}


def test_hx_redirect(app):
    with app.test_request_context():
        resp = hx.hx_redirect('/login', status=401)
        assert resp.status_code == 401
        assert resp.headers['HX-Redirect'] == '/login'
        assert 'Location' not in resp.headers


def test_hx_error(app):
    with app.test_request_context():
        resp = hx.hx_error(403, 'No.')
        assert resp.status_code == 403
        assert resp.headers['HX-Reswap'] == 'none'
        assert json.loads(resp.headers['HX-Trigger'])['siiap:flash'] == {'level': 'danger', 'message': 'No.'}


def test_render_fragment_sets_vary_and_status():
    fragment_app = Flask(__name__)
    fragment_app.jinja_loader = DictLoader({'_p.html': '<li id="{{ ident }}">{{ name }}</li>'})
    with fragment_app.test_request_context():
        resp = hx.render_fragment('_p.html', status=201, ident='row-1', name='<b>x</b>')
        assert resp.status_code == 201
        assert resp.get_data(as_text=True) == '<li id="row-1">&lt;b&gt;x&lt;/b&gt;</li>'
        assert 'HX-Request' in resp.headers['Vary']
