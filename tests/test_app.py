import base64
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
    hidden_resource_redirect = client.get('/lab/2/sitemap.xml', follow_redirects=False)
    assert hidden_resource_redirect.status_code == 302
    assert hidden_resource_redirect.headers['Location'].endswith('/ranking')
    ended_state = client.get('/api/participant-state')
    assert ended_state.status_code == 409
    ended_payload = ended_state.get_json()
    assert ended_payload['status'] == 'FINALIZADO'
    assert ended_payload['ranking_url'].endswith('/ctf/1/archive')
    assert ended_payload['home_url'] == '/inicio'

    home_after_finish = client.get('/', follow_redirects=True)
    assert home_after_finish.request.path == '/'
    assert b'JACITEC CTF' in home_after_finish.data
    assert b'href="/inicio"' in client.get('/ranking').data
    explicit_home = client.get('/inicio', follow_redirects=False)
    assert explicit_home.status_code == 200
    assert b'JACITEC CTF' in explicit_home.data

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
        client.post('/api/challenge/1/hint')

    challenge_flag = 'JACITEC{source_hidden_01}'
    response = client.post('/api/challenge/1/submit', json={'flag': challenge_flag})
    assert response.status_code == 200

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
    assert b'class="lab-addressbar"' not in workspace.data
    assert b'id="lab-addr-input"' not in workspace.data
    assert b'Digite um caminho do laborat\xc3\xb3rio' not in workspace.data
    assert b'Ver ranking' not in workspace.data
    assert client.get('/desafios').status_code == 404
    assert client.get('/challenge/1').status_code == 404
    assert client.post('/dashboard/flag').status_code == 404

    for challenge_id in range(1, 9):
        response = client.get(f'/lab/{challenge_id}')
        assert response.status_code == 200
    assert client.get('/lab/5').headers['X-Campus-Notice'] == 'JACITEC{cookies_and_headers_tell_all}'
    assert client.get('/lab/2/sitemap.xml').status_code == 200


def test_challenge_12_receipt_is_discoverable_and_has_no_robots_dependency(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    monkeypatch.setattr(
        app_module.random,
        'sample',
        lambda population, count: (
            [next(challenge for challenge in population if challenge['id'] == 12)]
            if count
            else []
        ),
    )
    app = create_app(testing=True)
    client = app.test_client()

    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={
        'challenge_list': 'lista-1',
        'easy_count': '1',
        'medium_count': '0',
        'hard_count': '0',
    })
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Riley', 'code': ctf_code})

    lab_response = client.get('/lab/12')
    assert lab_response.status_code == 200
    assert b'href="/lab/12/receipt">Baixar recibo</a>' in lab_response.data
    assert client.get('/lab/12/robots.txt').status_code == 404

    receipt_response = client.get('/lab/12/receipt')
    assert receipt_response.status_code == 200
    assert receipt_response.headers['X-Receipt-Note'] == 'JACITEC{catalog_12_receipt}'


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
    assert b'event-ended-dialog' in workspace.data

    response = client.post('/dashboard/finish', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/ranking')
    assert client.get('/api/ctf-status').get_json()['status'] == 'ATIVO'
    assert client.get('/dashboard', follow_redirects=False).headers['Location'].endswith('/ranking')
    ranking = client.get('/api/ranking').get_json()['ranking']
    jordan = next(row for row in ranking if row['name'] == 'Jordan')
    assert jordan['participation_status'] == 'Finalizou antes do encerramento'
    home_response = client.get('/inicio')
    assert b'JACITEC CTF' in home_response.data
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
    active_admin_page = client.get('/admin')
    assert b'id="finalize-dialog"' in active_admin_page.data
    assert b'id="delete-dialog"' in active_admin_page.data
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


def test_admin_can_delete_only_finalized_ctf_archive(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    active_id = client.get('/api/ctf-status').get_json()
    with sqlite3.connect(app_module.DATABASE_PATH) as conn:
        active_ctf_id = conn.execute('SELECT id FROM ctfs WHERE code = ?', (active_id['code'],)).fetchone()[0]

    blocked_delete = client.post(f'/admin/ctf/{active_ctf_id}/delete', follow_redirects=False)
    assert blocked_delete.status_code == 302
    assert client.get('/ctf/%s/archive' % active_ctf_id).status_code == 200

    client.post('/admin/finalize')
    deleted = client.post(f'/admin/ctf/{active_ctf_id}/delete', follow_redirects=False)
    assert deleted.status_code == 302
    assert client.get('/ctf/%s/archive' % active_ctf_id).status_code == 302


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


def test_landing_participation_cta_opens_technology_and_token_page(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    landing = client.get('/inicio')
    assert b'href="/participar"' in landing.data
    assert b'id="entrar"' not in landing.data
    assert b'name="code"' not in landing.data

    participation = client.get('/participar')
    assert participation.status_code == 200
    assert b'Tecnologias e ferramentas' in participation.data
    assert b'name="name"' in participation.data
    assert b'name="code"' in participation.data
    assert b'Burp Suite Community' in participation.data
    assert b'curl' in participation.data


def test_participants_can_open_full_rules_from_homepage(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()

    landing = client.get('/inicio')
    assert landing.status_code == 200
    assert b'href="/regras"' in landing.data
    assert b'Ler todas as regras de participa' in landing.data

    rules = client.get('/regras')
    assert rules.status_code == 200
    assert b'Regras de' in rules.data
    assert b'ESCOPO AUTORIZADO' in rules.data
    assert b'IA generativa' in rules.data
    assert b'1.000 pontos' in rules.data
    assert b'hor\xc3\xa1rios de abertura e encerramento' in rules.data


def test_admin_entry_is_discreet_but_linked_from_landing(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    response = app.test_client().get('/inicio')
    assert b'class="admin-stealth-link"' in response.data
    assert b'Equipe' in response.data


def test_catalog_has_10_5_3_per_list_and_event_is_ordered_by_difficulty(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    counts = {}
    for challenge in app_module.CHALLENGES:
        key = (challenge['list_id'], challenge['difficulty'])
        counts[key] = counts.get(key, 0) + 1
    assert len(app_module.CHALLENGES) == 54
    for list_id in ('lista-1', 'lista-2', 'lista-3'):
        assert counts[(list_id, 'Fácil')] == 10
        assert counts[(list_id, 'Médio')] == 5
        assert counts[(list_id, 'Difícil')] == 3

    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'challenge_list': 'lista-2', 'easy_count': '5', 'medium_count': '2', 'hard_count': '1'})
    with sqlite3.connect(database_path) as conn:
        ids = [row[0] for row in conn.execute('SELECT challenge_id FROM ctf_challenges ORDER BY position')]
    difficulties = [app_module.CHALLENGE_BY_ID[challenge_id]['difficulty'] for challenge_id in ids]
    assert difficulties == ['Fácil'] * 5 + ['Médio'] * 2 + ['Difícil']
    assert all(app_module.CHALLENGE_BY_ID[challenge_id]['list_id'] == 'lista-2' for challenge_id in ids)


def test_ctf_1_preset_uses_the_fixed_eight_challenges(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})

    response = client.get('/admin')
    assert b'CTF 1' in response.data
    assert b'Sele\xc3\xa7\xc3\xa3o fixa' in response.data

    client.post('/admin/generate', data={
        'challenge_list': 'ctf-1',
        'easy_count': '0',
        'medium_count': '0',
        'hard_count': '0',
    })
    with sqlite3.connect(database_path) as conn:
        ids = [row[0] for row in conn.execute('SELECT challenge_id FROM ctf_challenges ORDER BY position')]
    assert ids == [1, 2, 3, 4, 5, 6, 7, 17]
    assert [app_module.CHALLENGE_BY_ID[challenge_id]['difficulty'] for challenge_id in ids] == (
        ['Fácil'] * 5 + ['Médio'] * 2 + ['Difícil']
    )


def test_ctf_1_lab_sites_are_richer_without_breaking_challenge_flows(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/desafios/executar', data={'list_id': 'ctf-1'})

    home_pages = {
        1: (b'editorial-hero', b'studio-journal-strip'),
        2: (b'destination-grid', b'travel-editorial'),
        3: (b'dev-hero-visual', b'dev-customer-story'),
        4: (b'arcade-cabinet', b'arcade-community'),
        5: (b'product-grid', b'repair-story'),
        6: (b'cloud-dashboard', b'cloud-security-note'),
        7: (b'event-list', b'nightlife-guide'),
        17: (b'service-details', b'service-faq'),
    }
    for challenge_id, expected_content in home_pages.items():
        response = client.get(f'/lab/{challenge_id}')
        assert response.status_code == 200, response.headers.get('Location')
        for content_marker in expected_content:
            assert content_marker in response.data

    subpages = {
        1: '/journal',
        2: '/destinations',
        3: '/docs',
        4: '/games',
        5: '/shop',
        6: '/files',
        7: '/events',
        17: '/guide',
    }
    for challenge_id, subpage in subpages.items():
        assert client.get(f'/lab/{challenge_id}{subpage}').status_code == 200

    assert b'<!-- JACITEC{source_hidden_01} -->' in client.get('/lab/1').data
    guides = client.get('/lab/2/guides')
    assert b'Mapa do site do portal' in guides.data
    assert b'robots.txt' not in guides.data
    sitemap = client.get('/lab/2/sitemap.xml')
    assert sitemap.status_code == 200
    assert b'/lab/2/files/report' in sitemap.data
    assert client.get('/lab/2/robots.txt').status_code == 404
    assert b'JACITEC{map_the_hidden_routes}' in client.get('/lab/2/files/report').data
    encoded_flag = base64.b64encode(b'JACITEC{base64_is_not_a_secret}')
    assert encoded_flag in client.get('/lab/3/docs').data
    assert b'const arcadeReleaseNote = "JACITEC{js_holds_the_truth}"' in client.get('/lab/4').data
    assert client.get('/lab/5').headers['X-Campus-Notice'] == 'JACITEC{cookies_and_headers_tell_all}'
    for challenge_id in range(1, 6):
        assert len(app_module.CHALLENGE_BY_ID[challenge_id]['hints']) == 3
        assert app_module.CHALLENGE_BY_ID[challenge_id]['hints'] == app_module.CHALLENGE_HINTS[challenge_id]
    assert 'Base64' in app_module.CHALLENGE_HINTS[3][1]
    assert 'JACITEC{base64_is_not_a_secret}' not in app_module.CHALLENGE_HINTS[3][1]
    assert 'JACITEC{base64_is_not_a_secret}' in app_module.CHALLENGE_HINTS[3][2]
    assert b'id="cloud-profile-load"' in client.get('/lab/6/files/101').data
    assert b'id="ticket-search"' in client.get('/lab/7').data
    start = client.get('/lab/17/delivery/start', follow_redirects=False)
    assert start.status_code == 302
    receipt = client.get(start.headers['Location'])
    assert receipt.headers['X-Delivery-Receipt'] == 'JACITEC{catalog_17_redirect}'


def test_admin_challenge_library_is_protected_and_guides_to_flag(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()

    # Sem login de admin, as rotas de gabarito redirecionam para o login.
    index_anon = client.get('/admin/desafios', follow_redirects=False)
    assert index_anon.status_code == 302
    assert index_anon.headers['Location'].endswith('/admin/login')
    detail_anon = client.get('/admin/desafios/1', follow_redirects=False)
    assert detail_anon.status_code == 302
    assert detail_anon.headers['Location'].endswith('/admin/login')

    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    index = client.get('/admin/desafios')
    assert index.status_code == 200
    assert 'Gabarito dos desafios'.encode('utf-8') in index.data
    assert b'L1-F01' in index.data

    detail = client.get('/admin/desafios/3')
    assert detail.status_code == 200
    assert b'JACITEC{base64_is_not_a_secret}' in detail.data
    assert 'Como chegar à flag'.encode('utf-8') in detail.data
    assert 'participantes'.encode('utf-8') in detail.data

    missing = client.get('/admin/desafios/999', follow_redirects=False)
    assert missing.status_code == 302


def _start_ctf_with_challenge(client, database_path, challenge):
    import app as _m
    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE ctfs SET status='FINALIZADO' WHERE status='ATIVO'")
        code = _m.generate_ctf_code()
        conn.execute(
            "INSERT INTO ctfs (code,status,created_at,max_duration_minutes,challenge_list_id) VALUES (?,?,?,?,?)",
            (code, 'ATIVO', _m.timestamp_now(), 600, challenge['list_id']),
        )
        ctf_id = conn.execute("SELECT id FROM ctfs WHERE code=?", (code,)).fetchone()[0]
        conn.execute(
            "INSERT INTO ctf_challenges (ctf_id,challenge_id,position,base_points,hint_penalty) VALUES (?,?,?,?,?)",
            (ctf_id, challenge['id'], 1, challenge['points'], 1),
        )
    return code


def test_sitemap_challenge_2_report_page_exposes_flag(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    challenge = app_module.CHALLENGE_BY_ID[2]
    code = _start_ctf_with_challenge(client, database_path, challenge)
    client.post('/join', data={'name': 'Rev', 'code': code})
    report = client.get('/lab/2/files/report')
    assert report.status_code == 200
    assert challenge['flags'][0].encode('utf-8') in report.data


def test_manifest_challenge_endpoint_and_reference_present(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    challenge = next(c for c in app_module.CHALLENGES if c['mechanism'] == 'manifest')
    code = _start_ctf_with_challenge(client, database_path, challenge)
    client.post('/join', data={'name': 'Rev', 'code': code})
    home = client.get(f"/lab/{challenge['id']}")
    assert f"/lab/{challenge['id']}/app.webmanifest".encode('utf-8') in home.data
    manifest = client.get(f"/lab/{challenge['id']}/app.webmanifest")
    assert manifest.get_json()['maintenance_note'] == challenge['flags'][0]
