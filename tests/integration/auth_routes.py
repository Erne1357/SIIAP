"""Probe routes registered on the app fixture for error-handler / gating tests."""


def register_test_routes(app):
    """Register probe routes on the app fixture (before its first request)."""
    from flask import abort, jsonify, request
    from flask_login import login_required
    from app.utils.permissions import permission_required

    app.config['PROPAGATE_EXCEPTIONS'] = False

    def ok():
        return jsonify({'data': 'ok', 'error': None, 'meta': {}})

    def page_ok():
        return 'ok'

    app.add_url_rule('/_t/page', 't_page', login_required(page_ok))
    app.add_url_rule('/_t/open', 't_open', page_ok)
    app.add_url_rule('/_t/form', 't_form', ok, methods=['POST'])
    app.add_url_rule('/_t/boom', 't_boom', lambda: 1 / 0)
    app.add_url_rule('/api/v1/_t/boom', 't_api_boom', lambda: 1 / 0)
    app.add_url_rule('/_t/abort/<int:code>', 't_abort', lambda code: abort(code),
                     methods=['GET', 'POST'])
    app.add_url_rule('/api/v1/_t/abort/<int:code>', 't_api_abort', lambda code: abort(code),
                     methods=['GET', 'POST'])
    app.add_url_rule('/api/v1/_t/echo', 't_echo', ok, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    app.add_url_rule('/api/v1/_t/echo/<seg>', 't_echo_seg', lambda seg: ok())
    app.add_url_rule('/api/v1/_t/perm', 't_perm', permission_required('t.api.secret')(ok))
    app.add_url_rule('/_t/perm', 't_perm_page', permission_required('t.page.secret')(page_ok))

    def big():
        request.get_data()
        return ok()

    app.add_url_rule('/api/v1/_t/big', 't_big', big, methods=['POST'])
    app.add_url_rule('/_t/big', 't_big_page', big, methods=['POST'])
    return app
