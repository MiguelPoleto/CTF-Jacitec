import sqlite3

import app as app_module
from app import create_app


def isolate_database(monkeypatch, tmp_path):
    database_path = tmp_path / 'ctf.db'
    monkeypatch.setattr(app_module, 'DATABASE_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'DATABASE_PATH', database_path)
    return database_path


def test_finished_ctf_redirect_and_history_are_exposed(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()

    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'}, follow_redirects=False)
    client.post('/admin/generate', follow_redirects=False)
    ctf_code = client.get('/api/ctf-status').get_json()['code']

    client.post('/join', data={'name': 'Alice', 'code': ctf_code}, follow_redirects=False)
    client.post('/admin/finalize', follow_redirects=False)

    dashboard_redirect = client.get('/dashboard', follow_redirects=False)
    assert dashboard_redirect.status_code == 302
    assert dashboard_redirect.headers['Location'].endswith('/ranking')
    lab_redirect = client.get('/lab/1', follow_redirects=False)
    assert lab_redirect.status_code == 302
    assert lab_redirect.headers['Location'].endswith('/ranking')
    hidden_resource_redirect = client.get('/lab/2/robots.txt', follow_redirects=False)
    assert hidden_resource_redirect.status_code == 302
    assert hidden_resource_redirect.headers['Location'].endswith('/ranking')

    home_after_finish = client.get('/', follow_redirects=True)
    assert home_after_finish.request.path == '/'
    assert b'ENTRAR NO CTF' in home_after_finish.data
    assert b'href="/inicio"' in client.get('/ranking').data
    explicit_home = client.get('/inicio', follow_redirects=False)
    assert explicit_home.status_code == 200
    assert b'ENTRAR NO CTF' in explicit_home.data

    history = client.get('/api/ctf-history').get_json()
    assert history['ctfs']
    assert any(item['code'] == ctf_code for item in history['ctfs'])
    archive = client.get(f"/ctf/{history['ctfs'][0]['id']}/archive")
    assert archive.status_code == 200
    assert b'Classifica' in archive.data
    assert b'Alice' in archive.data


def test_three_hints_still_award_a_point(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()

    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'}, follow_redirects=False)
    client.post('/admin/generate', follow_redirects=False)
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Bob', 'code': ctf_code}, follow_redirects=False)

    for _ in range(3):
        client.post('/dashboard/hint', data={'challenge_id': 1}, follow_redirects=False)

    challenge_flag = 'JACITEC{source_hidden_01}'
    client.post('/dashboard/flag', data={'challenge_id': 1, 'flag': challenge_flag}, follow_redirects=False)

    with sqlite3.connect(database_path) as conn:
        row = conn.execute(
            "SELECT score_earned FROM participant_challenges WHERE participant_id = 1 AND challenge_id = 1"
        ).fetchone()

    assert row is not None
    assert row[0] >= 1


def test_single_workspace_and_local_challenge_sites_work(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Casey', 'code': ctf_code})

    workspace = client.get('/dashboard?challenge=5')
    assert workspace.status_code == 200
    assert b'id="challenge-site"' in workspace.data
    assert b'id="control-panel"' in workspace.data
    assert b'Ver ranking' not in workspace.data

    for challenge_id in range(1, 9):
        response = client.get(f'/lab/{challenge_id}')
        assert response.status_code == 200
    assert client.get('/lab/5').headers['X-Campus-Notice'] == 'JACITEC{cookies_and_headers_tell_all}'
    assert client.get('/lab/2/robots.txt').status_code == 200


def test_live_hint_and_flag_endpoints_update_participant_state(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Dana', 'code': ctf_code})

    hint_response = client.post('/api/challenge/1/hint')
    assert hint_response.status_code == 200
    assert hint_response.get_json()['hints_used'] == 1

    flag_response = client.post('/api/challenge/1/submit', json={'flag': 'JACITEC{source_hidden_01}'})
    assert flag_response.status_code == 200
    assert flag_response.get_json()['solved'] is True
    state = client.get('/api/participant-state').get_json()
    assert state['points'] >= 1
    assert state['challenges'][0]['status'] == 'solved'


def test_participant_can_confirm_finish_without_ending_global_ctf(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Jordan', 'code': ctf_code})

    workspace = client.get('/dashboard')
    assert b'Finalizar minha participa' in workspace.data
    assert b'finish-dialog' in workspace.data

    response = client.post('/dashboard/finish', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/ranking')
    assert client.get('/api/ctf-status').get_json()['status'] == 'ATIVO'
    assert client.get('/dashboard', follow_redirects=False).headers['Location'].endswith('/ranking')
    ranking = client.get('/api/ranking').get_json()['ranking']
    jordan = next(row for row in ranking if row['name'] == 'Jordan')
    assert jordan['participation_status'] == 'Finalizou antes do encerramento'
    home_response = client.get('/inicio')
    assert b'ENTRAR NO CTF' in home_response.data
    rejoin_response = client.post('/join', data={'name': 'Jordan', 'code': ctf_code}, follow_redirects=False)
    assert rejoin_response.status_code == 302
    assert rejoin_response.headers['Location'].endswith('/dashboard')


def test_admin_duration_automatically_finalizes_and_archives_ctf(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    admin_dashboard = client.get('/admin')
    assert b'name="max_duration_minutes"' in admin_dashboard.data
    client.post('/admin/generate', data={'max_duration_minutes': '1'})
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Rafa', 'code': ctf_code})

    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE ctfs SET created_at='2020-01-01 00:00:00' WHERE code=?", (ctf_code,))

    status = client.get('/api/ctf-status').get_json()
    assert status['status'] == 'AGUARDANDO'
    history = client.get('/api/ctf-history').get_json()['ctfs']
    archived_ctf = next(item for item in history if item['code'] == ctf_code)
    archive = client.get(f"/ctf/{archived_ctf['id']}/archive")
    assert archive.status_code == 200
    assert b'Rafa' in archive.data
    assert b'Encerrado pelo administrador/tempo limite' in archive.data


def test_scenario_subpages_are_available(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Taylor', 'code': ctf_code})

    scenarios = {
        '/lab/1/journal': 'Estúdio Northstar',
        '/lab/2/destinations': 'Viagens Wayfarer',
        '/lab/3/docs': 'Devdesk',
        '/lab/4/games': 'Pixel Arcade',
        '/lab/5/shop': 'Second Story',
        '/lab/6/files': 'CloudVault',
        '/lab/7/events': 'Night Owl',
        '/lab/8/calendar': 'ReservaF',
    }
    for path, brand in scenarios.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert brand.encode('utf-8').lower() in response.data.lower(), path

    audit_response = client.get('/lab/8/audit-log')
    assert audit_response.status_code == 200
    assert b'JACITEC{final_layer_unlocked}' in audit_response.data


def test_app_status_and_join_flow_work(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()

    status_response = client.get('/api/ctf-status')
    assert status_response.status_code == 200
    payload = status_response.get_json()
    assert 'status' in payload
    assert payload['status'] in {'AGUARDANDO', 'ATIVO'}

    login_response = client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'}, follow_redirects=False)
    assert login_response.status_code == 302

    generate_response = client.post('/admin/generate', follow_redirects=False)
    assert generate_response.status_code == 302

    ctf_status = client.get('/api/ctf-status').get_json()
    assert ctf_status['status'] == 'ATIVO'

    join_response = client.post('/join', data={'name': 'Joao', 'code': ctf_status['code']}, follow_redirects=False)
    assert join_response.status_code == 302
