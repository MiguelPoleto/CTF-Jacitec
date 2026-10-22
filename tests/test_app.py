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
    # Com feedback pendente, o fim do evento leva ao feedback antes do ranking.
    assert dashboard_redirect.headers['Location'].endswith('/feedback')
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
    client.post('/admin/generate', data={'challenge_list': 'ctf-1'}, follow_redirects=False)
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
    client.post('/admin/generate', data={'challenge_list': 'ctf-1'})
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

    for challenge_id in app_module.FIXED_CHALLENGE_LISTS['ctf-1']:
        response = client.get(f'/lab/{challenge_id}')
        assert response.status_code == 200, challenge_id
    assert client.get('/lab/5').headers['X-Campus-Notice'] == 'JACITEC{cookies_and_headers_tell_all}'
    assert client.get('/lab/2/sitemap.xml').status_code == 200

def test_live_hint_and_flag_endpoints_update_participant_state(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'challenge_list': 'ctf-1'})
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

    # Ao finalizar, o participante passa pela tela de feedback rápido antes da
    # classificação (pode pular, mas é o destino padrão).
    response = client.post('/dashboard/finish', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/feedback')
    assert client.get('/api/ctf-status').get_json()['status'] == 'ATIVO'
    assert client.get('/dashboard', follow_redirects=False).headers['Location'].endswith('/feedback')
    ranking = client.get('/api/ranking').get_json()['ranking']
    jordan = next(row for row in ranking if row['name'] == 'Jordan')
    assert jordan['participation_status'] == 'Finalizou antes do encerramento'
    home_response = client.get('/inicio')
    assert b'JACITEC CTF' in home_response.data
    rejoin_response = client.post('/join', data={'name': 'Jordan', 'code': ctf_code}, follow_redirects=False)
    assert rejoin_response.status_code == 302
    assert rejoin_response.headers['Location'].endswith('/dashboard')


def test_feedback_after_finishing_only_requires_the_name(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Alex', 'code': ctf_code})

    # Antes de finalizar não há tela de feedback para abrir.
    assert client.get('/feedback', follow_redirects=False).headers['Location'].endswith('/ranking')

    client.post('/dashboard/finish')
    form = client.get('/feedback')
    assert form.status_code == 200
    assert 'Alex'.encode() in form.data
    assert b'name="turma"' in form.data
    for field in ('difficulty', 'clarity', 'favorite_part', 'time_enough', 'organization_rating', 'improvements'):
        assert f'name="{field}"'.encode() in form.data

    # Só o nome vai preenchido: o resto fica nulo, sem erro.
    sent = client.post('/feedback', data={'name': 'Alex'}, follow_redirects=False)
    assert sent.status_code == 302
    assert sent.headers['Location'].endswith('/ranking')
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM participant_feedback').fetchone()
    assert row['name'] == 'Alex'
    assert [row[field] for field in ('turma', 'difficulty', 'clarity', 'favorite_part', 'time_enough', 'organization_rating', 'improvements')] == [None] * 7

    # Uma resposta por participante: a tela não reabre depois de enviada.
    assert client.get('/feedback', follow_redirects=False).headers['Location'].endswith('/ranking')


def test_feedback_stores_answers_and_rejects_invalid_values(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Sam', 'code': ctf_code})
    client.post('/dashboard/finish')

    client.post('/feedback', data={
        'name': 'Sam', 'turma': '3º Info', 'difficulty': 'Ideal', 'clarity': 'Sim',
        # "Qual parte você mais gostou" aceita várias marcações.
        'favorite_part': ['Desafios web', 'Ranking e competição'], 'time_enough': 'Parcialmente',
        'organization_rating': '5', 'improvements': 'Mais desafios de terminal.',
        # Valores forjados fora das opções não devem ser gravados.
        'unexpected': 'ignored',
    })
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM participant_feedback').fetchone()
    assert (row['turma'], row['difficulty'], row['clarity']) == ('3º Info', 'Ideal', 'Sim')
    assert row['favorite_part'] == 'Desafios web; Ranking e competição'
    assert (row['time_enough'], row['organization_rating']) == ('Parcialmente', 5)
    assert row['improvements'] == 'Mais desafios de terminal.'

    # O painel do admin mostra a resposta recebida.
    panel = client.get('/admin')
    assert b'Sam' in panel.data
    assert '3º Info'.encode() in panel.data
    assert 'Mais desafios de terminal.'.encode() in panel.data
    assert 'Desafios web, Ranking e competição'.encode() in panel.data

    # E a página dedicada lista a resposta com o resumo agregado.
    full = client.get('/admin/feedbacks')
    assert full.status_code == 200
    assert b'Sam' in full.data
    assert 'Mais desafios de terminal.'.encode() in full.data


def test_admin_reads_feedbacks_one_by_one_grouped_by_edition(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    app_instance = create_app(testing=True)
    client = app_instance.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})

    # Duas edições, cada uma com seus próprios respondentes.
    editions = {}
    for edition_label, names in (('primeira', ['Ana', 'Bruno']), ('segunda', ['Cora'])):
        client.post('/admin/generate')
        code = client.get('/api/ctf-status').get_json()['code']
        editions[edition_label] = code
        for name in names:
            client.post('/join', data={'name': name, 'code': code})
            client.post('/dashboard/finish')
            client.post('/feedback', data={'name': name, 'difficulty': 'Ideal',
                                           'improvements': f'Comentário de {name}.'})
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})

    with app_instance.app_context():
        import app as module
        conn = module.get_db()
        rows = {row['name']: dict(row) for row in conn.execute('SELECT id, name, ctf_id FROM participant_feedback')}
        conn.close()

    # A listagem abre a edição mais recente e não mistura respostas das outras.
    latest = client.get('/admin/feedbacks')
    assert b'Cora' in latest.data
    assert b'Ana' not in latest.data
    assert editions['primeira'].encode() in latest.data  # a outra edição fica disponível como aba

    older = client.get(f"/admin/feedbacks?ctf={rows['Ana']['ctf_id']}")
    assert b'Ana' in older.data and b'Bruno' in older.data
    assert b'Cora' not in older.data

    # Detalhe individual: respostas em branco aparecem como não respondidas.
    detail = client.get(f"/admin/feedbacks/{rows['Ana']['id']}")
    assert detail.status_code == 200
    assert b'Ana' in detail.data
    assert 'Comentário de Ana.'.encode() in detail.data
    assert 'Não respondeu'.encode() in detail.data

    # E navega um a um dentro da mesma edição, sem vazar para a outra.
    assert f"/admin/feedbacks/{rows['Bruno']['id']}".encode() in detail.data
    assert f"/admin/feedbacks/{rows['Cora']['id']}".encode() not in detail.data

    assert client.get('/admin/feedbacks/9999', follow_redirects=False).headers['Location'].endswith('/admin/feedbacks')


def _run_ctf_with_results(client, database_path, results, duration=600):
    """Roda um CTF (lista CTF 1) e grava desafios resolvidos: {nome: [challenge_id, ...]}."""
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'challenge_list': 'ctf-1', 'max_duration_minutes': str(duration)})
    code = client.get('/api/ctf-status').get_json()['code']
    with sqlite3.connect(database_path) as conn:
        ctf_id = conn.execute("SELECT id FROM ctfs WHERE code = ?", (code,)).fetchone()[0]
        points = dict(conn.execute(
            "SELECT challenge_id, base_points FROM ctf_challenges WHERE ctf_id = ?", (ctf_id,)).fetchall())
        for name, solved in results.items():
            conn.execute("INSERT INTO participants (ctf_id, name, entered_at, finished_at) VALUES (?,?,?,?)",
                         (ctf_id, name, '2026-10-01 10:00:00', '2026-10-01 10:30:00'))
            participant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for challenge_id in solved:
                conn.execute(
                    """INSERT INTO participant_challenges
                       (participant_id, challenge_id, status, hints_used, score_earned, solved_at)
                       VALUES (?,?, 'solved', 0, ?, ?)""",
                    (participant_id, challenge_id, points[challenge_id], '2026-10-01 10:20:00'))
    client.post('/admin/finalize')
    return ctf_id


def _merge(client, edition_id, participant_ids, name, **overrides):
    """Fluxo real da tela: prévia → confirmação da fusão."""
    preview = client.post(f'/admin/edicoes/{edition_id}/fusao/previa',
                          json={'participant_ids': participant_ids}).get_json()
    body = {
        'participant_ids': participant_ids,
        'display_name': name,
        'challenge_ids': [c['id'] for c in preview['challenges']],
        'points': preview['points'],
        'elapsed': preview['elapsed'],
    }
    body.update(overrides)
    return preview, client.post(f'/admin/edicoes/{edition_id}/fusao', json=body).get_json()


def _new_edition(client, database_path, name='JACITEC 2026'):
    client.post('/admin/edicoes', data={'name': name})
    with sqlite3.connect(database_path) as conn:
        edition_id = conn.execute('SELECT id FROM editions ORDER BY id DESC').fetchone()[0]
        ctf_ids = [row[0] for row in conn.execute('SELECT id FROM ctfs ORDER BY id')]
        ids = {n: pid for pid, n in conn.execute('SELECT id, name FROM participants')}
    for ctf_id in ctf_ids:
        client.post(f'/admin/edicoes/{edition_id}/rodadas', json={'ctf_id': ctf_id, 'included': True})
    return edition_id, ids


def test_merge_preview_dedupes_challenges_and_merges_time(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    fixed = app_module.FIXED_CHALLENGE_LISTS['ctf-1']
    # Ana jogou as duas rodadas: um desafio repetido e dois novos.
    _run_ctf_with_results(client, database_path, {'Ana': list(fixed[:2]), 'Bruno': list(fixed[:1])})
    _run_ctf_with_results(client, database_path, {'Ana': list(fixed[1:4])})
    edition_id, ids = _new_edition(client, database_path)

    # Sem fundir, as duas participações da Ana aparecem separadas.
    state = client.get(f'/admin/edicoes/{edition_id}/estado').get_json()
    assert sum(1 for row in state['ranking'] if row['name'] == 'Ana') == 2
    assert [r['ctf_code'] for r in state['round_rankings']] == sorted(state['rounds'])

    anas = [pid for pid, name in ids.items() if name == 'Ana'] if False else \
        [e['participant_id'] for e in state['entries'] if e['original_name'] == 'Ana']
    preview, after = _merge(client, edition_id, anas, 'Ana')
    # 4 desafios distintos; o repetido aparece marcado como duplicado.
    assert len(preview['challenges']) == 4
    assert sum(1 for c in preview['challenges'] if c['duplicated']) == 1
    assert preview['elapsed'] == 30 * 60 * 2

    ana = next(row for row in after['ranking'] if row['name'] == 'Ana')
    assert ana['kind'] == 'merge' and ana['solved'] == 4 and len(ana['sources']) == 2
    assert sum(1 for row in after['ranking'] if row['name'] == 'Ana') == 1
    assert next(r for r in after['ranking'] if r['name'] == 'Bruno')['kind'] == 'single'


def test_duplicated_challenge_keeps_the_lowest_score(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    ctf_a = _run_ctf_with_results(client, database_path, {'Nina': [1]})
    ctf_b = _run_ctf_with_results(client, database_path, {'Nina 2': [1]})

    # O mesmo desafio resolvido duas vezes, com pontuações diferentes.
    with sqlite3.connect(database_path) as conn:
        ids = {name: pid for pid, name in conn.execute('SELECT id, name FROM participants')}
        conn.execute('UPDATE participant_challenges SET score_earned = 100 WHERE participant_id = ?', (ids['Nina'],))
        conn.execute('UPDATE participant_challenges SET score_earned = 40 WHERE participant_id = ?', (ids['Nina 2'],))
    edition_id, _ = _new_edition(client, database_path)

    preview = client.post(f'/admin/edicoes/{edition_id}/fusao/previa',
                          json={'participant_ids': [ids['Nina'], ids['Nina 2']]}).get_json()
    assert len(preview['challenges']) == 1
    assert preview['challenges'][0]['duplicated'] is True
    # Vale a menor: quem repetiu não ganha a melhor nota das duas tentativas.
    assert preview['challenges'][0]['points'] == 40
    assert preview['points'] == 40

    # Cada participação traz seus horários para o admin conferir o tempo.
    for source in preview['sources']:
        assert source['entered_at'] and source['ended_at'] and source['ctf_code']
    assert {source['ctf_id'] for source in preview['sources']} == {ctf_a, ctf_b}
    assert all(source['counted'] for source in preview['sources'])


def test_two_entries_in_the_same_round_count_only_the_longest_time(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    ctf_a = _run_ctf_with_results(client, database_path, {'Duda': [1]})
    _run_ctf_with_results(client, database_path, {'Duda B': [2]})

    # Entrada duplicada por engano na primeira rodada, com tempo menor.
    with sqlite3.connect(database_path) as conn:
        conn.execute("INSERT INTO participants (ctf_id, name, entered_at, finished_at) VALUES (?,?,?,?)",
                     (ctf_a, 'Duda (2)', '2026-10-01 10:00:00', '2026-10-01 10:10:00'))
    edition_id, ids = _new_edition(client, database_path)

    preview = client.post(f'/admin/edicoes/{edition_id}/fusao/previa', json={
        'participant_ids': [ids['Duda'], ids['Duda (2)'], ids['Duda B']]}).get_json()
    # Rodada A: 30 min e 10 min valem só os 30. Rodada B: +30 min.
    assert preview['elapsed'] == 30 * 60 + 30 * 60
    ignored = [s for s in preview['sources'] if not s['counted']]
    assert [s['name'] for s in ignored] == ['Duda (2)']


def test_merge_lets_the_admin_drop_a_challenge_and_fix_the_score(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    fixed = app_module.FIXED_CHALLENGE_LISTS['ctf-1']
    _run_ctf_with_results(client, database_path, {'Carla': list(fixed[:2]), 'Carla 2': list(fixed[2:4])})
    edition_id, ids = _new_edition(client, database_path)

    preview, after = _merge(
        client, edition_id, [ids['Carla'], ids['Carla 2']], 'Carla',
        challenge_ids=[fixed[0], fixed[1], fixed[2]], points=123, elapsed=600,
    )
    assert len(preview['challenges']) == 4
    row = after['ranking'][0]
    # Vale o que o admin confirmou, não a prévia.
    assert (row['solved'], row['points'], row['elapsed']) == (3, 123, 600)
    assert len(after['ranking']) == 1

    # A fusão some do ranking ao esconder, e os dados originais continuam lá.
    client.post(f'/admin/edicoes/{edition_id}/entrada', json={'kind': 'merge', 'key': row['key'], 'hidden': True})
    assert client.get(f'/admin/edicoes/{edition_id}/estado').get_json()['ranking'] == []
    with sqlite3.connect(database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0] == 2

    # Apagar a fusão devolve as participações originais ao ranking.
    client.post(f'/admin/edicoes/{edition_id}/entrada', json={'kind': 'merge', 'key': row['key'], 'action': 'remover'})
    assert len(client.get(f'/admin/edicoes/{edition_id}/estado').get_json()['ranking']) == 2


def test_only_merged_entries_can_be_deleted(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    _run_ctf_with_results(client, database_path, {'Ivo': [1], 'Lia': [2]})
    edition_id, ids = _new_edition(client, database_path)

    # Participação real só pode ser escondida; continua no banco.
    client.post(f'/admin/edicoes/{edition_id}/entrada', json={'kind': 'single', 'key': ids['Ivo'], 'hidden': True})
    state = client.get(f'/admin/edicoes/{edition_id}/estado').get_json()
    assert [r['name'] for r in state['ranking']] == ['Lia']
    with sqlite3.connect(database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0] == 2
    # E volta quando o admin desfaz.
    client.post(f'/admin/edicoes/{edition_id}/entrada', json={'kind': 'single', 'key': ids['Ivo'], 'hidden': False})
    assert len(client.get(f'/admin/edicoes/{edition_id}/estado').get_json()['ranking']) == 2

    assert client.post(f'/admin/edicoes/{edition_id}/entrada',
                       json={'kind': 'merge', 'key': 999, 'action': 'remover'}).status_code == 404
    assert client.post(f'/admin/edicoes/{edition_id}/fusao/previa',
                       json={'participant_ids': [ids['Ivo']]}).status_code == 400


def test_edition_publishes_rounds_and_final_ranking(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    _run_ctf_with_results(client, database_path, {'Dani': [1, 2]})
    edition_id, _ = _new_edition(client, database_path)

    assert b'JACITEC 2026' not in client.get('/edicoes').data
    assert client.get(f'/edicoes/{edition_id}', follow_redirects=False).status_code == 302
    client.post(f'/admin/edicoes/{edition_id}/publicar')
    page = client.get(f'/edicoes/{edition_id}')
    assert page.status_code == 200
    assert b'Dani' in page.data
    # A página explica nomes repetidos, ausências e fusões.
    assert 'por que alguns nomes'.encode() in page.data.lower()
    # Gabaritos só saem quando o admin liberar.
    assert b'Ver solu' not in page.data
    client.post(f'/admin/edicoes/{edition_id}', data={'name': 'JACITEC 2026', 'show_challenges': 'on'})
    assert b'Ver solu' in client.get(f'/edicoes/{edition_id}').data


def test_training_mode_opens_labs_only_after_the_admin_enables_a_list(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()

    # Desligado por padrão: nada em /treino e laboratórios fechados.
    assert 'Nenhuma lista liberada'.encode() in client.get('/treino').data
    assert client.get('/treino/ctf-1', follow_redirects=False).headers['Location'].endswith('/treino')
    assert client.get('/lab/1', follow_redirects=False).status_code == 302

    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    library = client.get('/admin/desafios')
    assert b'Liberar para treino' in library.data
    client.post('/admin/desafios/treino', data={'list_id': 'ctf-1'})
    assert b'No treino livre' in client.get('/admin/desafios').data

    # Agora os laboratórios abrem para qualquer visitante, sem CTF nem sessão.
    public = create_app(testing=True).test_client()
    page = public.get('/treino')
    assert b'CTF 1' in page.data
    listing = public.get('/treino/ctf-1')
    assert listing.status_code == 200
    assert b'Abrir laborat' in listing.data
    assert public.get('/lab/1').status_code == 200

    # A flag é conferida sem gravar pontuação nem participação.
    wrong = public.post('/treino/flag', json={'challenge_id': 1, 'flag': 'JACITEC{errada}'})
    assert wrong.get_json() == {'correct': False}
    right = public.post('/treino/flag', json={'challenge_id': 1, 'flag': 'JACITEC{source_hidden_01}'})
    assert right.get_json() == {'correct': True}
    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        assert conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0] == 0

    # Desligar fecha tudo de novo.
    client.post('/admin/desafios/treino', data={'list_id': 'ctf-1'})
    assert public.get('/lab/1', follow_redirects=False).status_code == 302
    assert public.post('/treino/flag', json={'challenge_id': 1, 'flag': 'x'}).status_code == 404


def test_published_edition_with_gabarito_opens_its_labs(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    _run_ctf_with_results(client, database_path, {'Rafa': [1]})
    client.post('/admin/edicoes', data={'name': 'Edição aberta'})
    with sqlite3.connect(database_path) as conn:
        edition_id = conn.execute('SELECT id FROM editions').fetchone()[0]
        ctf_id = conn.execute('SELECT id FROM ctfs').fetchone()[0]
    client.post(f'/admin/edicoes/{edition_id}/rodadas', json={'ctf_id': ctf_id, 'included': True})
    client.post(f'/admin/edicoes/{edition_id}/publicar')

    public = create_app(testing=True).test_client()
    # Sem gabarito liberado o laboratório continua fechado.
    assert public.get('/lab/1', follow_redirects=False).status_code == 302
    client.post(f'/admin/edicoes/{edition_id}', data={'name': 'Edição aberta', 'show_challenges': 'on'})
    assert public.get('/lab/1').status_code == 200
    assert b'Abrir laborat' in public.get(f'/edicoes/{edition_id}').data


def test_edition_admin_pages_require_login(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    for method, path in (('get', '/admin/edicoes'), ('post', '/admin/edicoes'),
                         ('get', '/admin/edicoes/1'), ('post', '/admin/edicoes/1/publicar'),
                         ('post', '/admin/edicoes/1/remover')):
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.status_code == 302, path
        assert response.headers['Location'].endswith('/admin/login'), path
    # Os endpoints de autosave são API: respondem 401 em vez de redirecionar.
    for path in ('/admin/edicoes/1/estado', '/admin/edicoes/1/rodadas',
                 '/admin/edicoes/1/participantes', '/admin/edicoes/1/feedbacks'):
        method = client.get if path.endswith('estado') else client.post
        assert method(path, json={}).status_code == 401, path


def test_admin_can_add_extra_time_to_a_running_ctf(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'max_duration_minutes': '60'})

    panel = client.get('/admin')
    assert b'Tempo extra' in panel.data
    assert b'/admin/tempo-extra' in panel.data

    client.post('/admin/tempo-extra', data={'extra_minutes': '15'})
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT max_duration_minutes FROM ctfs WHERE status='ATIVO'").fetchone()[0] == 75
    assert client.get('/api/ctf-status').get_json()['max_duration_minutes'] == 75

    # Valores fora da faixa não mexem no evento.
    for invalid in ('0', '999', 'abc'):
        client.post('/admin/tempo-extra', data={'extra_minutes': invalid})
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT max_duration_minutes FROM ctfs WHERE status='ATIVO'").fetchone()[0] == 75

    # Sem CTF ativo não há o que prorrogar.
    client.post('/admin/finalize')
    assert b'Tempo extra' not in client.get('/admin').data
    client.post('/admin/tempo-extra', data={'extra_minutes': '10'})
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ctfs WHERE status='ATIVO'").fetchone()[0] == 0


def test_feedback_also_appears_when_the_ctf_runs_out_of_time(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'max_duration_minutes': '1'})
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Val', 'code': ctf_code})

    # Durante o evento ainda não há feedback para responder.
    assert client.get('/feedback', follow_redirects=False).headers['Location'].endswith('/ranking')

    # O tempo acaba sem a pessoa clicar em "finalizar": o finished_at dela fica
    # vazio, mas a tela de feedback precisa aparecer mesmo assim. Em vez de
    # mexer no relógio, o início do evento é empurrado para trás.
    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE ctfs SET created_at = datetime('now', '-30 minutes') WHERE status = 'ATIVO'")
    assert client.get('/api/ctf-status').get_json()['status'] != 'ATIVO'
    with sqlite3.connect(database_path) as conn:
        assert conn.execute('SELECT finished_at FROM participants').fetchone()[0] is None

    assert client.get('/dashboard', follow_redirects=False).headers['Location'].endswith('/feedback')
    form = client.get('/feedback')
    assert form.status_code == 200
    assert b'Val' in form.data

    client.post('/feedback', data={'name': 'Val', 'difficulty': 'Ideal'})
    assert client.get('/feedback', follow_redirects=False).headers['Location'].endswith('/ranking')


def test_admin_schedules_an_event_and_banner_respects_its_window(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})

    client.post('/admin/agenda', data={
        'title': 'JACITEC CTF 2026 — 2ª edição',
        'location': 'Laboratório de Informática 2 — Bloco B',
        'details': 'Traga seu notebook.',
        'event_date': '2026-11-14', 'event_time': '19:00', 'event_end_time': '22:00',
        'banner_start_date': '2026-11-01', 'banner_start_time': '00:00',
        'banner_end_date': '2026-11-14', 'banner_end_time': '23:59',
    })

    # Horário local (America/Sao_Paulo, UTC-3) é convertido para UTC no banco.
    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM scheduled_events').fetchone()
    assert row['starts_at'] == '2026-11-14 22:00:00'
    assert row['ends_at'] == '2026-11-15 01:00:00'
    assert row['banner_starts_at'] == '2026-11-01 03:00:00'

    # Dentro da janela, o banner aparece na página inicial com data, hora e local.
    monkeypatch.setattr(app_module, 'timestamp_now', lambda: '2026-11-05 12:00:00')
    page = client.get('/')
    assert b'event-banner' in page.data
    assert '2ª edição'.encode() in page.data
    assert 'Laboratório de Informática 2'.encode() in page.data
    assert b'14/11/2026' in page.data and b'19h00' in page.data

    # Antes e depois da janela, some.
    for moment in ('2026-10-20 12:00:00', '2026-11-20 12:00:00'):
        monkeypatch.setattr(app_module, 'timestamp_now', lambda moment=moment: moment)
        assert b'event-banner' not in client.get('/').data


def test_banner_button_uses_the_signup_link_and_rejects_unsafe_schemes(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    base = {'title': 'CTF com inscrição', 'event_date': '2026-11-14', 'event_time': '19:00',
            'banner_start_date': '2026-11-01', 'banner_start_time': '00:00',
            'banner_end_date': '2026-11-14', 'banner_end_time': '23:59'}
    monkeypatch.setattr(app_module, 'timestamp_now', lambda: '2026-11-05 12:00:00')

    # Sem link, o botão aponta para a página de participação do próprio site.
    client.post('/admin/agenda', data=base)
    assert b'href="/participar"' in client.get('/').data

    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        event_id = conn.execute('SELECT id FROM scheduled_events').fetchone()[0]

    # Com link, o botão abre o formulário externo em outra aba.
    client.post('/admin/agenda', data={**base, 'event_id': event_id,
                                       'signup_url': 'https://forms.gle/exemplo123'})
    page = client.get('/').data
    assert b'https://forms.gle/exemplo123' in page
    assert b'rel="noopener noreferrer"' in page

    # Um esquema perigoso é recusado e o link anterior continua valendo.
    client.post('/admin/agenda', data={**base, 'event_id': event_id,
                                       'signup_url': 'javascript:alert(1)'})
    assert 'http:// ou https://'.encode() in client.get('/admin/agenda').data
    assert b'javascript:alert' not in client.get('/').data


def test_schedule_form_rejects_invalid_windows(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    base = {'title': 'CTF', 'event_date': '2026-11-14', 'event_time': '19:00',
            'banner_start_date': '2026-11-01', 'banner_start_time': '00:00',
            'banner_end_date': '2026-11-14', 'banner_end_time': '23:59'}

    for payload, expected in (
        ({**base, 'title': '   '}, 'nome do evento'),
        ({**base, 'event_date': ''}, 'data válida'),
        ({**base, 'banner_end_date': '2026-10-01'}, 'depois do início'),
        ({**base, 'event_end_time': '18:00'}, 'depois do horário de início'),
    ):
        client.post('/admin/agenda', data=payload)
        assert expected.encode() in client.get('/admin/agenda').data

    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        assert conn.execute('SELECT COUNT(*) FROM scheduled_events').fetchone()[0] == 0


def test_admin_can_edit_and_remove_a_scheduled_event(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    base = {'event_date': '2026-11-14', 'event_time': '19:00',
            'banner_start_date': '2026-11-01', 'banner_start_time': '00:00',
            'banner_end_date': '2026-11-14', 'banner_end_time': '23:59'}
    client.post('/admin/agenda', data={**base, 'title': 'Primeira versão', 'location': 'Bloco A'})

    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        event_id = conn.execute('SELECT id FROM scheduled_events').fetchone()[0]

    # O formulário de edição vem preenchido com o horário local, não o UTC.
    form = client.get(f'/admin/agenda?editar={event_id}')
    assert b'value="19:00"' in form.data
    assert b'Primeira vers' in form.data

    client.post('/admin/agenda', data={**base, 'event_id': event_id, 'title': 'Versão corrigida', 'location': 'Bloco C'})
    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM scheduled_events').fetchall()
    assert len(rows) == 1 and rows[0]['title'] == 'Versão corrigida' and rows[0]['location'] == 'Bloco C'

    client.post(f'/admin/agenda/{event_id}/remover')
    with sqlite3.connect(tmp_path / 'ctf.db') as conn:
        assert conn.execute('SELECT COUNT(*) FROM scheduled_events').fetchone()[0] == 0


def test_schedule_admin_pages_require_login(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    for method, path in (('get', '/admin/agenda'), ('post', '/admin/agenda'), ('post', '/admin/agenda/1/remover')):
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/admin/login')


def test_feedback_admin_pages_require_login(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    for path in ('/admin/feedbacks', '/admin/feedbacks/1'):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/admin/login')


def test_feedback_other_option_stores_free_text_only_when_selected(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']

    form = None
    for name, payload, expected in (
        ('Noa', {'favorite_part': ['Outro'], 'favorite_part_other': 'A parte de redes'}, 'A parte de redes'),
        # Sem marcar "Outro", o texto livre é descartado em vez de guardado.
        ('Lia', {'favorite_part': ['Desafios web'], 'favorite_part_other': 'texto solto'}, None),
    ):
        client.post('/join', data={'name': name, 'code': ctf_code})
        client.post('/dashboard/finish')
        if form is None:
            form = client.get('/feedback').data
        client.post('/feedback', data={'name': name, **payload})
        with sqlite3.connect(database_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM participant_feedback WHERE name = ?', (name,)).fetchone()
        assert row['favorite_part_other'] == expected

    # A pergunta de múltipla escolha usa checkbox e traz o campo de "Outro".
    assert b'type="checkbox" name="favorite_part"' in form
    assert b'name="favorite_part_other"' in form
    assert b'feedback-other-trigger' in form


def test_feedback_rejects_an_empty_name_and_out_of_range_answers(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate')
    ctf_code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Robin', 'code': ctf_code})
    client.post('/dashboard/finish')

    blank = client.post('/feedback', data={'name': '   '})
    assert blank.status_code == 400
    with sqlite3.connect(database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM participant_feedback').fetchone()[0] == 0

    client.post('/feedback', data={'name': 'Robin', 'difficulty': 'Impossível', 'organization_rating': '9'})
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM participant_feedback').fetchone()
    assert row['difficulty'] is None
    assert row['organization_rating'] is None


def test_landing_page_shows_the_explainer_video(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    page = client.get('/')
    assert b'id="o-que-e-ctf"' in page.data
    assert b'video/jacitec-ctf.mp4' in page.data
    assert b'video/jacitec-ctf-poster.jpg' in page.data
    # Vídeo com áudio: nunca deve tocar sozinho.
    assert b'autoplay' not in page.data
    assert client.get('/static/video/jacitec-ctf.mp4').status_code == 200
    assert client.get('/static/video/jacitec-ctf-poster.jpg').status_code == 200


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
    client.post('/admin/generate', data={'challenge_list': 'ctf-1'})
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
    }
    for path, brand in scenarios.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert brand.encode('utf-8').lower() in response.data.lower(), path
    assert client.get('/lab/17/guide').status_code == 200

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


def test_catalog_has_two_fixed_editions_ordered_by_difficulty(monkeypatch, tmp_path):
    database_path = isolate_database(monkeypatch, tmp_path)
    counts = {}
    for challenge in app_module.CHALLENGES:
        key = (challenge['list_id'], challenge['difficulty'])
        counts[key] = counts.get(key, 0) + 1
    # Duas edições fixas, cada uma 5 fáceis / 2 médios / 1 difícil.
    assert len(app_module.CHALLENGES) == 16
    for list_id in ('lista-1', 'lista-2'):
        assert counts[(list_id, 'Fácil')] == 5
        assert counts[(list_id, 'Médio')] == 2
        assert counts[(list_id, 'Difícil')] == 1
    assert list(app_module.CHALLENGE_LISTS) == ['ctf-1', 'ctf-2']

    app = create_app(testing=True)
    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})

    # Uma lista inexistente não gera nada.
    client.post('/admin/generate', data={'challenge_list': 'lista-2'})
    with sqlite3.connect(database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM ctfs').fetchone()[0] == 0

    # Cada edição sai sempre ordenada fáceis → médios → difícil.
    for list_id in ('ctf-1', 'ctf-2'):
        client.post('/admin/generate', data={'challenge_list': list_id})
        with sqlite3.connect(database_path) as conn:
            ids = [row[0] for row in conn.execute(
                "SELECT challenge_id FROM ctf_challenges WHERE ctf_id = (SELECT id FROM ctfs WHERE status='ATIVO') ORDER BY position")]
        difficulties = [app_module.CHALLENGE_BY_ID[cid]['difficulty'] for cid in ids]
        assert difficulties == ['Fácil'] * 5 + ['Médio'] * 2 + ['Difícil']
        assert set(ids) == set(app_module.FIXED_CHALLENGE_LISTS[list_id])


def test_every_ctf2_challenge_is_solvable(monkeypatch, tmp_path):
    import base64, re
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/generate', data={'challenge_list': 'ctf-2', 'max_duration_minutes': '600'})
    code = client.get('/api/ctf-status').get_json()['code']
    client.post('/join', data={'name': 'Solver', 'code': code})
    flag = lambda cid: app_module.CHALLENGE_BY_ID[cid]['flags'][0]

    # 18 caesar: decodificar o texto cifrado mostrado na página.
    s = app_module.CHALLENGE_BY_ID[18]['site2']
    assert app_module._caesar_shift(s['caesar'], -s['shift']) == flag(18)
    # 19 backup: a cópia .bak traz o campo interno.
    assert client.get('/lab/19/catalogo.json.bak').get_json()['_nota_marceneiro'] == flag(19)
    # 20 cookie: Set-Cookie na home.
    assert flag(20) in client.get('/lab/20').headers.get('Set-Cookie', '')  # preferencia_padaria
    # 21 svg: anotação dentro do arquivo vetorial.
    assert flag(21) in client.get('/lab/21/assets/cobre.svg').get_data(as_text=True)
    assert flag(21) not in client.get('/lab/21/assets/mare.svg').get_data(as_text=True)
    # 22 debug: ?debug=1 revela o diagnóstico.
    assert client.get('/lab/22/rastreio?debug=1').get_json()['interno']['chave_operacao'] == flag(22)
    assert 'interno' not in client.get('/lab/22/rastreio').get_json()
    # 23 login_sqli: tautologia no login.
    assert client.post('/lab/23/entrar', data={'user': "' OR '1'='1' --", 'password': 'x'}).get_json()['mural_interno'] == flag(23)
    assert client.post('/lab/23/entrar', data={'user': 'ana', 'password': '123'}).get_json()['ok'] is False
    assert client.post('/lab/23/entrar', data={'user': '', 'password': ''}).status_code == 400
    # credenciais reais tambem entram (login de verdade), mas sem a flag
    assert client.post('/lab/23/entrar', data={'user': 'mariana', 'password': 'cafe-2024'}).get_json()['ok'] is True
    # 24 token: trocar role para admin no cookie Base64.
    raw = re.search(r'cracha=([^;]+)', client.get('/lab/24').headers['Set-Cookie']).group(1)
    forged = base64.b64encode(base64.b64decode(raw).decode().replace('papel=visitante', 'papel=admin').encode()).decode()
    client.set_cookie('cracha', forged, path='/lab/24')
    assert client.get('/lab/24/restrito').get_json()['chave_mestra'] == flag(24)
    # 25 recovery: robots → debug → usuarios → redefinir (só curl/base64, sem Burp).
    assert '/lab/25/interno/gerador-token' in client.get('/lab/25/robots.txt').get_data(as_text=True)
    assert 'base64' in client.get('/lab/25/interno/gerador-token').get_json()['algoritmo']
    email = client.get('/lab/25/equipe.json').get_json()['equipe'][0]['email']
    token = base64.b64encode(email.encode()).decode()
    assert client.get(f'/lab/25/redefinir?user={email}&token={token}').get_json()['codigo_confirmacao'] == flag(25)
    assert client.get(f'/lab/25/redefinir?user={email}&token=errado').get_json()['ok'] is False


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
    })
    with sqlite3.connect(database_path) as conn:
        ids = [row[0] for row in conn.execute('SELECT challenge_id FROM ctf_challenges ORDER BY position')]
    # A ordem de uma edição é sempre fáceis → médios → difíceis. O desafio de
    # IDOR (6) é o Difícil desta seleção, e o de redirecionamento (17) é um
    # dos Médios — refletindo o rebalanceamento feito após o desafio de
    # redirecionamento (cadeia simples de 1 salto) se mostrar fácil demais
    # para "Difícil", e o de IDOR (indireção de autorização entre dois
    # recursos) se mostrar difícil demais para "Médio".
    assert ids == [1, 2, 3, 4, 5, 7, 17, 6]
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
    # Cadeia de 3 saltos: start (devolve um token) -> processing (só traz a
    # flag se a requisição for refeita manualmente com esse token) -> receipt
    # (200 final, sem flag). Um clique normal (ou seguir os redirects
    # automaticamente, como o navegador faz sozinho) NUNCA deve expor a flag,
    # mesmo acompanhando toda a cadeia pelo Network.
    start = client.get('/lab/17/delivery/start', follow_redirects=False)
    assert start.status_code == 302
    assert 'X-Delivery-Receipt' not in start.headers
    token = start.headers['X-Delivery-Token']
    processing_without_token = client.get(start.headers['Location'], follow_redirects=False)
    assert processing_without_token.status_code == 302
    assert 'X-Delivery-Receipt' not in processing_without_token.headers
    processing_with_token = client.get(start.headers['Location'], follow_redirects=False, headers={'X-Delivery-Token': token})
    assert processing_with_token.status_code == 302
    assert processing_with_token.headers['X-Delivery-Receipt'] == 'JACITEC{catalog_17_redirect}'
    receipt = client.get(processing_with_token.headers['Location'], follow_redirects=False)
    assert receipt.status_code == 200
    assert 'X-Delivery-Receipt' not in receipt.headers
    followed_fully = client.get('/lab/17/delivery/start', follow_redirects=True)
    assert 'X-Delivery-Receipt' not in followed_fully.headers


def test_search_challenge_requires_a_real_tautology_not_just_the_word_or(monkeypatch, tmp_path):
    isolate_database(monkeypatch, tmp_path)
    client = create_app(testing=True).test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adm2026'})
    client.post('/admin/desafios/executar', data={'list_id': 'ctf-1'})
    flag = app_module.CHALLENGE_BY_ID[7]['flags'][0]

    empty = client.get('/lab/7/search', query_string={'q': ''}).get_json()
    assert empty['results'] == []

    public_hit = client.get('/lab/7/search', query_string={'q': 'jazz'}).get_json()
    assert len(public_hit['results']) == 1
    assert 'nota' not in public_hit['results'][0]

    not_actually_sqli = client.get('/lab/7/search', query_string={'q': 'jazz or blues'}).get_json()
    assert not_actually_sqli['results'] == []

    bypass = client.get('/lab/7/search', query_string={'q': "' OR '1'='1"}).get_json()
    titles = [result['title'] for result in bypass['results']]
    notes = [result.get('nota', '') for result in bypass['results']]
    assert len(bypass['results']) == len(app_module.NIGHT_OWL_ARCHIVE)
    assert any(flag in note for note in notes)
    assert all(flag not in title for title in titles)

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

