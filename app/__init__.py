import os
import random
import sqlite3
import string
import base64
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, make_response, redirect, render_template, request, session, url_for

DATABASE_DIR = Path("/app/data")
DATABASE_PATH = DATABASE_DIR / "ctf.db"

CHALLENGES = [
    {
        "id": 1,
        "title": "Desafio 1",
        "name": "Olhe melhor",
        "points": 10,
        "difficulty": "Fácil",
        "flags": ["JACITEC{source_hidden_01}"],
        "description": "Encontre uma informação escondida na página.",
        "hints": [
            "Observe tudo que existe por trás da página.",
            "Use o código-fonte da página.",
            "Procure por comentários ocultos no HTML."
        ],
        "hint_deductions": [0, 3, 6, 10],
    },
    {
        "id": 2,
        "title": "Desafio 2",
        "name": "Mapa do site",
        "points": 10,
        "difficulty": "Fácil",
        "flags": ["JACITEC{robots_are_not_for_kids}"],
        "description": "Uma rota importante não aparece na interface.",
        "hints": [
            "Procure por arquivos de descoberta do site.",
            "O navegador não mostra tudo automaticamente.",
            "Revise o arquivo de robots e caminhos escondidos."
        ],
        "hint_deductions": [0, 3, 6, 10],
    },
    {
        "id": 3,
        "title": "Desafio 3",
        "name": "Base64 em branco",
        "points": 10,
        "difficulty": "Fácil",
        "flags": ["JACITEC{base64_is_not_a_secret}"],
        "description": "Identifique o conteúdo escondido em uma string codificada.",
        "hints": [
            "O dado parece ser texto codificado em base64.",
            "Testar a decodificação pode revelar a pista.",
            "A string parece estar em um formato de texto simples."
        ],
        "hint_deductions": [0, 3, 6, 10],
    },
    {
        "id": 4,
        "title": "Desafio 4",
        "name": "Arquivo de frontend",
        "points": 10,
        "difficulty": "Fácil",
        "flags": ["JACITEC{js_holds_the_truth}"],
        "description": "Uma informação está escondida em um trecho do JavaScript do frontend.",
        "hints": [
            "Abra o console e veja os scripts carregados.",
            "O código do JavaScript pode revelar strings úteis.",
            "Procure por valores que parecem pistas ou flags."
        ],
        "hint_deductions": [0, 3, 6, 10],
    },
    {
        "id": 5,
        "title": "Desafio 5",
        "name": "Cabeçalhos curiosos",
        "points": 15,
        "difficulty": "Fácil",
        "flags": ["JACITEC{cookies_and_headers_tell_all}"],
        "description": "Uma informação se esconde em cookies ou headers.",
        "hints": [
            "Observe os dados enviados em requisições e cookies.",
            "O navegador guarda metadados importantes em headers.",
            "A pista pode estar em uma variável de sessão discreta."
        ],
        "hint_deductions": [0, 5, 10, 15],
    },
    {
        "id": 6,
        "title": "Desafio 6",
        "name": "IDOR no perfil",
        "points": 15,
        "difficulty": "Médio",
        "flags": ["JACITEC{idor_is_a_risk_06}"],
        "description": "Um identificador do usuário pode ser alterado para abusar do acesso.",
        "hints": [
            "A API parece confiar no valor de um parâmetro.",
            "Teste se alterar o identificador muda o resultado.",
            "Verifique se a autorização é realmente validada."
        ],
        "hint_deductions": [0, 5, 10, 15],
    },
    {
        "id": 7,
        "title": "Desafio 7",
        "name": "Busca indiscreta",
        "points": 15,
        "difficulty": "Médio",
        "flags": ["JACITEC{sql_injection_is_not_safe}"],
        "description": "Uma busca de usuários permite exploração por entrada descontrolada.",
        "hints": [
            "Observe os parâmetros enviados na busca.",
            "Substituir um valor por outra expressão pode mudar a resposta.",
            "Uma expressão lógica pode burlar a filtragem da consulta."
        ],
        "hint_deductions": [0, 5, 10, 15],
    },
    {
        "id": 8,
        "title": "Desafio 8",
        "name": "Camadas finais",
        "points": 15,
        "difficulty": "Médio/Difícil",
        "flags": ["JACITEC{final_layer_unlocked}"],
        "description": "Combine os conceitos anteriores para encontrar o último segredo.",
        "hints": [
            "Relembre os desafios anteriores e como cada um escondia uma pista.",
            "A resposta final combina observação do código e análise do comportamento.",
            "Uma sequência de pistas geralmente revela a chave final."
        ],
        "hint_deductions": [0, 5, 10, 15],
    },
]


def timestamp_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ctfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'AGUARDANDO',
            created_at TEXT NOT NULL,
            finished_at TEXT,
            max_duration_minutes INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ctf_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            entered_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY(ctf_id) REFERENCES ctfs(id)
        )
        """
    )
    ctf_columns = {row["name"] for row in conn.execute("PRAGMA table_info(ctfs)").fetchall()}
    if "max_duration_minutes" not in ctf_columns:
        conn.execute("ALTER TABLE ctfs ADD COLUMN max_duration_minutes INTEGER")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS participant_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            hints_used INTEGER DEFAULT 0,
            score_earned INTEGER DEFAULT 0,
            solved_at TEXT,
            skipped_at TEXT,
            UNIQUE(participant_id, challenge_id),
            FOREIGN KEY(participant_id) REFERENCES participants(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ctf_id INTEGER,
            participant_id INTEGER,
            event TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_event(ctf_id=None, participant_id=None, event="", detail=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO logs (ctf_id, participant_id, event, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (ctf_id, participant_id, event, detail, timestamp_now()),
    )
    conn.commit()
    conn.close()


def current_ctf():
    conn = get_db()
    row = conn.execute("SELECT * FROM ctfs WHERE status = 'ATIVO' ORDER BY created_at DESC LIMIT 1").fetchone()
    if row and row["max_duration_minutes"]:
        created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        expires_at = created_at.timestamp() + int(row["max_duration_minutes"]) * 60
        if datetime.now(timezone.utc).timestamp() >= expires_at:
            finished_at = timestamp_now()
            conn.execute("UPDATE ctfs SET status='FINALIZADO', finished_at=? WHERE id=? AND status='ATIVO'", (finished_at, row["id"]))
            conn.commit()
            row = None
    conn.close()
    return dict(row) if row else None


def ctf_remaining_seconds(ctf):
    if not ctf or not ctf.get("max_duration_minutes"):
        return None
    started = datetime.strptime(ctf["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return max(0, int(started.timestamp() + ctf["max_duration_minutes"] * 60 - datetime.now(timezone.utc).timestamp()))


def participant_is_active(participant_id, ctf=None):
    ctf = ctf or current_ctf()
    if not participant_id or not ctf:
        return False
    conn = get_db()
    row = conn.execute(
        "SELECT ctf_id, finished_at FROM participants WHERE id = ?",
        (participant_id,),
    ).fetchone()
    conn.close()
    return bool(row and row["ctf_id"] == ctf["id"] and not row["finished_at"])


def generate_ctf_code():
    alphabet = string.ascii_uppercase + string.digits
    return "JCTF-" + "".join(random.choice(alphabet) for _ in range(8))


def ensure_active_ctf_exists():
    ctf = current_ctf()
    if ctf is None:
        return None
    return ctf


def get_participant_stats(participant_id, ctf_id=None):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM participant_challenges WHERE participant_id = ?",
        (participant_id,),
    ).fetchall()
    conn.close()
    total = 0
    solved = 0
    skipped = 0
    for row in rows:
        if row["score_earned"]:
            total += row["score_earned"]
            solved += 1
        if row["status"] == "skipped":
            skipped += 1
    return {"total": total, "solved": solved, "skipped": skipped}


def challenge_record(participant_id, challenge_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM participant_challenges WHERE participant_id = ? AND challenge_id = ?",
        (participant_id, challenge_id),
    ).fetchone()
    conn.close()
    if row is None:
        conn = get_db()
        conn.execute(
            "INSERT INTO participant_challenges (participant_id, challenge_id, status, hints_used, score_earned) VALUES (?, ?, 'open', 0, 0)",
            (participant_id, challenge_id),
        )
        conn.commit()
        conn.close()
        return challenge_record(participant_id, challenge_id)
    return dict(row)


def challenge_points_for_hint(challenge, hints_used):
    deduction_index = min(hints_used, len(challenge["hint_deductions"]) - 1)
    deduced = challenge["hint_deductions"][deduction_index]
    score = max(0, challenge["points"] - deduced)
    if hints_used > 0:
        return max(1, score)
    return score


def last_ctf_for_display():
    current_ctf()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM ctfs WHERE status IN ('ATIVO', 'FINALIZADO') ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def ctf_history():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ctfs WHERE status = 'FINALIZADO' ORDER BY finished_at DESC, created_at DESC"
    ).fetchall()
    history = []
    for row in rows:
        ranking = participant_ranking(row["id"])
        history.append({
            "id": row["id"],
            "code": row["code"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
            "max_duration_minutes": row["max_duration_minutes"],
            "winner": ranking[0]["name"] if ranking else None,
            "winner_points": ranking[0]["points"] if ranking else 0,
            "participants": len(ranking),
            "ranking": ranking[:10],
        })
    conn.close()
    return history


def participant_ranking(ctf_id):
    conn = get_db()
    event = conn.execute("SELECT status, finished_at FROM ctfs WHERE id = ?", (ctf_id,)).fetchone()
    event_finished_at = event["finished_at"] if event else None
    participants = conn.execute(
        "SELECT p.id, p.name, p.entered_at, p.finished_at FROM participants p WHERE p.ctf_id = ? ORDER BY p.entered_at ASC",
        (ctf_id,),
    ).fetchall()
    data = []
    for participant in participants:
        rows = conn.execute(
            "SELECT SUM(score_earned) AS score FROM participant_challenges WHERE participant_id = ?",
            (participant["id"],),
        ).fetchone()
        score = rows["score"] if rows and rows["score"] else 0
        started_at = participant["entered_at"]
        elapsed = 0
        if started_at:
            ended = participant["finished_at"] or event_finished_at or timestamp_now()
            try:
                delta = datetime.strptime(ended, "%Y-%m-%d %H:%M:%S") - datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                elapsed = int(delta.total_seconds())
            except ValueError:
                elapsed = 0
        data.append({
            "id": participant["id"],
            "name": participant["name"],
            "points": int(score),
            "elapsed": elapsed,
            "finished_at": participant["finished_at"],
            "participation_status": (
                "Finalizou antes do encerramento" if participant["finished_at"]
                else "Em andamento"
            ),
            "entered_at": started_at,
        })
    conn.close()
    return sorted(data, key=lambda item: (-item["points"], item["elapsed"], item["name"].lower()))


def make_app_config():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "jacitec-secret")
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.globals["current_ctf"] = current_ctf
    app.jinja_env.globals["challenge_list"] = CHALLENGES
    app.jinja_env.filters["b64encode"] = lambda value: base64.b64encode(value.encode("utf-8")).decode("ascii")
    return app


def create_app(testing=False):
    app = make_app_config()
    init_db()

    @app.before_request
    def guard_lab_routes_after_ctf_end():
        if not request.path.startswith("/lab/"):
            return None
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        ctf = current_ctf()
        if not ctf:
            return redirect(url_for("public_ranking_page"))
        conn = get_db()
        participant = conn.execute("SELECT ctf_id, finished_at FROM participants WHERE id = ?", (participant_id,)).fetchone()
        conn.close()
        if not participant or participant["ctf_id"] != ctf["id"] or participant["finished_at"]:
            return redirect(url_for("public_ranking_page"))
        return None

    @app.get("/")
    def index():
        if participant_is_active(session.get("participant_id")):
            return redirect(url_for("participant_dashboard"))
        session.pop("participant_id", None)
        session.pop("participant_name", None)
        ctf = current_ctf()
        return render_template("index.html", ctf=ctf)

    @app.get("/inicio")
    def ctf_home():
        session.pop("participant_id", None)
        session.pop("participant_name", None)
        return render_template("index.html", ctf=current_ctf())

    @app.get("/desafios")
    def challenge_index():
        return redirect(url_for("participant_dashboard"))

    @app.get("/challenge/<int:challenge_id>")
    def challenge_detail(challenge_id):
        return redirect(url_for("participant_dashboard", challenge=challenge_id))

    @app.get("/lab/2/robots.txt")
    def lab_robots():
        return "User-agent: *\nDisallow: /lab/2/files/report\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/lab/2/arquivos/relatorio")
    def lab_hidden_report():
        return render_template("lab_hidden_report.html")

    @app.get("/lab/<int:challenge_id>")
    def lab_page(challenge_id):
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        ctf = current_ctf()
        if not ctf:
            return redirect(url_for("public_ranking_page"))
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return redirect(url_for("participant_dashboard"))
        response = make_response(render_template("lab_site.html", challenge=challenge, ctf=ctf, page="home"))
        if challenge_id == 5:
            response.headers["X-Campus-Notice"] = challenge["flags"][0]
        return response

    @app.get("/lab/<int:challenge_id>/<path:page>")
    def lab_subpage(challenge_id, page):
        if challenge_id == 2 and page == "robots.txt":
            return lab_robots()
        if challenge_id == 2 and page == "files/report":
            return render_template("lab_hidden_report.html")
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return redirect(url_for("participant_dashboard"))
        response = make_response(render_template("lab_site.html", challenge=challenge, ctf=current_ctf(), page=page))
        if challenge_id == 5:
            response.headers["X-Campus-Notice"] = challenge["flags"][0]
        return response

    @app.get("/lab/8/audit-log")
    def lab_booking_audit_log():
        return jsonify({
            "system": "ReservaFácil / exportação de auditoria",
            "entries": [
                {"event": "reserva.criada", "resource": "sala-reuniao-2"},
                {"event": "nota_migracao_legada", "reference": CHALLENGES[7]["flags"][0]},
            ],
        })

    @app.get("/lab/6/profile/<int:profile_id>")
    def lab_profile(profile_id):
        profiles = {
            101: {"id": 101, "name": "Ana Souza", "course": "Sistemas de Informação", "public": True},
            102: {"id": 102, "name": "Arquivo de pesquisa", "course": "Laboratório Web", "public": False, "note": CHALLENGES[5]["flags"][0]},
        }
        profile = profiles.get(profile_id)
        if not profile:
            return jsonify({"error": "Perfil não encontrado"}), 404
        return jsonify(profile)

    @app.get("/lab/7/search")
    def lab_search():
        query = request.args.get("q", "")
        if "'" in query and ("or" in query.lower() or "1=1" in query.replace(" ", "")):
            return jsonify({"results": [
                {"title": "Registro reservado", "owner": "Arquivo do campus", "note": CHALLENGES[6]["flags"][0]}
            ]})
        return jsonify({"results": [{"title": "Nenhum resultado", "owner": "", "note": "Tente outra busca."}]})

    @app.post("/join")
    def join_ctf():
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        ctf = current_ctf()
        if not ctf:
            return render_template("index.html", error="Nenhum CTF está ativo no momento. Aguarde o administrador iniciar a competição.")
        if not name:
            return render_template("index.html", error="Informe o seu nome para entrar no CTF.", ctf=ctf)
        if ctf["code"] != code:
            return render_template("index.html", error="Código do CTF inválido.", ctf=ctf)

        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM participants WHERE ctf_id = ? AND name = ? AND finished_at IS NULL ORDER BY id DESC LIMIT 1",
            (ctf["id"], name),
        ).fetchone()
        if existing:
            participant_id = existing["id"]
        else:
            now = timestamp_now()
            cursor = conn.execute(
                "INSERT INTO participants (ctf_id, name, entered_at) VALUES (?, ?, ?)",
                (ctf["id"], name, now),
            )
            participant_id = cursor.lastrowid
            for challenge in CHALLENGES:
                conn.execute(
                    "INSERT INTO participant_challenges (participant_id, challenge_id, status, hints_used, score_earned) VALUES (?, ?, 'open', 0, 0)",
                    (participant_id, challenge["id"]),
                )
        conn.commit()
        conn.close()
        log_event(ctf["id"], participant_id, "participant_joined", name)
        session["participant_id"] = participant_id
        session["participant_name"] = name
        return redirect(url_for("participant_dashboard"))

    @app.get("/dashboard")
    def participant_dashboard():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))

        active_ctf = current_ctf()
        if not active_ctf:
            return redirect(url_for("public_ranking_page"))

        conn = get_db()
        participant = conn.execute(
            "SELECT * FROM participants WHERE id = ?",
            (participant_id,),
        ).fetchone()
        if not participant:
            session.clear()
            return redirect(url_for("index"))
        if participant["ctf_id"] != active_ctf["id"] or participant["finished_at"]:
            return redirect(url_for("public_ranking_page"))
        ctf = conn.execute("SELECT * FROM ctfs WHERE id = ?", (participant["ctf_id"],)).fetchone()
        conn.close()

        challenge_status = []
        rows = []
        conn = get_db()
        for challenge in CHALLENGES:
            rec = challenge_record(participant_id, challenge["id"])
            rows.append({
                "challenge": challenge,
                "record": rec,
                "value_after_hints": challenge_points_for_hint(challenge, rec["hints_used"]),
            })
        conn.close()
        stats = get_participant_stats(participant_id)
        active_challenge_id = request.args.get("challenge", default=1, type=int)
        if active_challenge_id not in range(1, len(CHALLENGES) + 1):
            active_challenge_id = 1
        active_challenge = CHALLENGES[active_challenge_id - 1]
        active_record = next(row["record"] for row in rows if row["challenge"]["id"] == active_challenge_id)
        return render_template(
            "participant_dashboard.html",
            participant=participant,
            ctf=ctf,
            challenges=rows,
            stats=stats,
            active_challenge=active_challenge,
            active_record=active_record,
        )

    @app.get("/api/participant-state")
    def participant_state_api():
        participant_id = session.get("participant_id")
        ctf = current_ctf()
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        if not ctf:
            return jsonify({"status": "FINALIZADO", "redirect": url_for("public_ranking_page")}), 409

        conn = get_db()
        participant = conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,)).fetchone()
        conn.close()
        if not participant or participant["ctf_id"] != ctf["id"] or participant["finished_at"]:
            return jsonify({"status": "FINALIZADO", "redirect": url_for("public_ranking_page")}), 409

        stats = get_participant_stats(participant_id)
        challenge_states = []
        for challenge in CHALLENGES:
            record = challenge_record(participant_id, challenge["id"])
            challenge_states.append({
                "id": challenge["id"],
                "status": record["status"],
                "hints_used": record["hints_used"],
                "score_earned": record["score_earned"],
            })
        return jsonify({
            "status": "ATIVO",
            "points": stats["total"],
            "solved": stats["solved"],
            "remaining_seconds": ctf_remaining_seconds(ctf),
            "participant": participant["name"],
            "entered_at": participant["entered_at"],
            "challenges": challenge_states,
        })

    @app.post("/api/challenge/<int:challenge_id>/hint")
    def reveal_challenge_hint(challenge_id):
        participant_id = session.get("participant_id")
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        if not participant_is_active(participant_id):
            return jsonify({"status": "FINALIZADO", "redirect": url_for("public_ranking_page")}), 409
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return jsonify({"error": "Desafio não encontrado"}), 404
        record = challenge_record(participant_id, challenge_id)
        if record["status"] == "solved":
            return jsonify({"error": "Desafio já resolvido"}), 409
        hints_used = min(record["hints_used"] + 1, len(challenge["hints"]))
        conn = get_db()
        conn.execute(
            "UPDATE participant_challenges SET hints_used = ? WHERE participant_id = ? AND challenge_id = ?",
            (hints_used, participant_id, challenge_id),
        )
        conn.commit()
        conn.close()
        log_event(current_ctf()["id"], participant_id, "hint_used", f"challenge:{challenge_id}:{hints_used}")
        return jsonify({
            "hints_used": hints_used,
            "hint": challenge["hints"][hints_used - 1],
            "points_if_solved": challenge_points_for_hint(challenge, hints_used),
        })

    @app.post("/api/challenge/<int:challenge_id>/submit")
    def submit_challenge_flag_api(challenge_id):
        participant_id = session.get("participant_id")
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        if not participant_is_active(participant_id):
            return jsonify({"status": "FINALIZADO", "redirect": url_for("public_ranking_page")}), 409
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return jsonify({"error": "Desafio não encontrado"}), 404
        record = challenge_record(participant_id, challenge_id)
        if record["status"] == "solved":
            return jsonify({"solved": True, "points": record["score_earned"]})
        submitted = (request.get_json(silent=True) or {}).get("flag", "").strip()
        if submitted.upper() not in [flag.upper() for flag in challenge["flags"]]:
            log_event(current_ctf()["id"], participant_id, "flag_incorrect", f"challenge:{challenge_id}")
            return jsonify({"solved": False, "message": "Flag incorreta. Continue investigando o site."}), 400
        score = challenge_points_for_hint(challenge, record["hints_used"])
        conn = get_db()
        conn.execute(
            "UPDATE participant_challenges SET status='solved', score_earned=?, solved_at=? WHERE participant_id=? AND challenge_id=?",
            (score, timestamp_now(), participant_id, challenge_id),
        )
        conn.commit()
        conn.close()
        log_event(current_ctf()["id"], participant_id, "flag_correct", f"challenge:{challenge_id}:{score}")
        return jsonify({"solved": True, "points": score, "message": f"Correto! +{score} pontos."})

    @app.post("/dashboard/flag")
    def submit_flag():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        if not current_ctf():
            return redirect(url_for("public_ranking_page"))
        challenge_id = int(request.form.get("challenge_id", 0))
        submitted_values = []
        direct = (request.form.get("flag") or "").strip()
        if direct:
            submitted_values.append(direct)
        for index in range(1, 6):
            value = (request.form.get(f"flag_{index}") or "").strip()
            if value:
                submitted_values.append(value)
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return redirect(url_for("participant_dashboard"))
        rec = challenge_record(participant_id, challenge_id)
        if rec["status"] == "solved":
            return redirect(url_for("participant_dashboard"))
        if any(submitted.upper() in [flag.upper() for flag in challenge["flags"]] for submitted in submitted_values):
            score = challenge_points_for_hint(challenge, rec["hints_used"])
            conn = get_db()
            conn.execute(
                "UPDATE participant_challenges SET status='solved', score_earned=?, solved_at=? WHERE participant_id=? AND challenge_id=?",
                (score, timestamp_now(), participant_id, challenge_id),
            )
            conn.commit()
            conn.close()
            log_event(current_ctf()["id"], participant_id, "flag_correct", f"challenge:{challenge_id}:{score}")
            return redirect(url_for("participant_dashboard"))
        attempted = ";".join(submitted_values)
        log_event(current_ctf()["id"] if current_ctf() else None, participant_id, "flag_incorrect", f"challenge:{challenge_id}:{attempted}")
        return redirect(url_for("participant_dashboard"))

    @app.post("/dashboard/hint")
    def use_hint():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        if not current_ctf():
            return redirect(url_for("public_ranking_page"))
        challenge_id = int(request.form.get("challenge_id", 0))
        challenge = next((item for item in CHALLENGES if item["id"] == challenge_id), None)
        if not challenge:
            return redirect(url_for("participant_dashboard"))
        rec = challenge_record(participant_id, challenge_id)
        if rec["status"] == "solved":
            return redirect(url_for("participant_dashboard"))
        new_hints_used = min(rec["hints_used"] + 1, len(challenge["hints"]))
        conn = get_db()
        conn.execute(
            "UPDATE participant_challenges SET hints_used = ?, status = CASE WHEN status='open' THEN 'open' ELSE status END WHERE participant_id = ? AND challenge_id = ?",
            (new_hints_used, participant_id, challenge_id),
        )
        conn.commit()
        conn.close()
        log_event(current_ctf()["id"] if current_ctf() else None, participant_id, "hint_used", f"challenge:{challenge_id}:{new_hints_used}")
        return redirect(url_for("participant_dashboard"))

    @app.post("/dashboard/skip")
    def skip_challenge():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        if not current_ctf():
            return redirect(url_for("public_ranking_page"))
        challenge_id = int(request.form.get("challenge_id", 0))
        rec = challenge_record(participant_id, challenge_id)
        if rec["status"] == "solved":
            return redirect(url_for("participant_dashboard"))
        conn = get_db()
        conn.execute(
            "UPDATE participant_challenges SET status='skipped', score_earned=0, skipped_at=? WHERE participant_id=? AND challenge_id=?",
            (timestamp_now(), participant_id, challenge_id),
        )
        conn.commit()
        conn.close()
        log_event(current_ctf()["id"] if current_ctf() else None, participant_id, "challenge_skipped", f"challenge:{challenge_id}")
        return redirect(url_for("participant_dashboard"))

    @app.post("/dashboard/finish")
    def finish_participation():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        ctf = current_ctf()
        if not ctf:
            return redirect(url_for("public_ranking_page"))
        conn = get_db()
        participant = conn.execute("SELECT ctf_id FROM participants WHERE id = ?", (participant_id,)).fetchone()
        if not participant or participant["ctf_id"] != ctf["id"]:
            conn.close()
            return redirect(url_for("public_ranking_page"))
        conn.execute(
            "UPDATE participants SET finished_at = ? WHERE id = ?",
            (timestamp_now(), participant_id),
        )
        conn.commit()
        conn.close()
        log_event(ctf["id"], participant_id, "participant_finished", "finished")
        return redirect(url_for("public_ranking_page"))

    @app.get("/ranking")
    def public_ranking_page():
        ctf = last_ctf_for_display()
        history = ctf_history()
        return render_template("ranking.html", ctf=ctf, history=history)

    @app.get("/api/ranking")
    def api_ranking():
        ctf = last_ctf_for_display()
        if not ctf:
            return jsonify({"status": "AGUARDANDO", "ranking": []})
        ranking = participant_ranking(ctf["id"])
        ranked = []
        for idx, item in enumerate(ranking, start=1):
            ranked.append({
                "position": idx,
                "id": item["id"],
                "name": item["name"],
                "points": item["points"],
                "time": item["elapsed"],
                "finished_at": item["finished_at"],
                "participation_status": "Finalizou antes do encerramento" if item["finished_at"] else "Em andamento" if ctf["status"] == "ATIVO" else "Encerrado pelo administrador/tempo limite",
            })
        return jsonify({"status": ctf["status"], "ranking": ranked})

    @app.get("/ctf/<int:ctf_id>/archive")
    def ctf_archive_page(ctf_id):
        conn = get_db()
        ctf_row = conn.execute("SELECT * FROM ctfs WHERE id = ?", (ctf_id,)).fetchone()
        conn.close()
        if not ctf_row:
            return redirect(url_for("public_ranking_page"))
        ctf = dict(ctf_row)
        if ctf["status"] == "ATIVO":
            current_ctf()
            conn = get_db()
            ctf_row = conn.execute("SELECT * FROM ctfs WHERE id = ?", (ctf_id,)).fetchone()
            conn.close()
            ctf = dict(ctf_row)
        ranking = participant_ranking(ctf_id)
        for item in ranking:
            item["participation_status"] = (
                "Finalizou antes do encerramento" if item["finished_at"]
                else "Em andamento" if ctf["status"] == "ATIVO"
                else "Encerrado pelo administrador/tempo limite"
            )
            item["challenge_count"] = get_participant_stats(item["id"])["solved"]
            conn = get_db()
            saved_results = conn.execute(
                "SELECT challenge_id, status, hints_used, score_earned, solved_at FROM participant_challenges WHERE participant_id = ? ORDER BY challenge_id",
                (item["id"],),
            ).fetchall()
            conn.close()
            item["challenge_results"] = [
                {
                    "name": CHALLENGES[result["challenge_id"] - 1]["name"],
                    "status": result["status"],
                    "hints_used": result["hints_used"],
                    "score_earned": result["score_earned"],
                    "solved_at": result["solved_at"],
                }
                for result in saved_results
                if 1 <= result["challenge_id"] <= len(CHALLENGES)
            ]
        return render_template("ctf_archive.html", ctf=ctf, ranking=ranking)

    @app.get("/api/ctf-history")
    def api_ctf_history():
        return jsonify({"ctfs": ctf_history()})

    @app.get("/api/ctf-status")
    def ctf_status_api():
        ctf = current_ctf()
        if ctf:
            return jsonify({"status": "ATIVO", "code": ctf["code"], "max_duration_minutes": ctf["max_duration_minutes"], "remaining_seconds": ctf_remaining_seconds(ctf)})
        return jsonify({"status": "AGUARDANDO", "code": None})

    @app.get("/admin/login")
    def admin_login_page():
        return render_template("admin_login.html")

    @app.post("/admin/login")
    def admin_login():
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if username == os.getenv("ADMIN_USERNAME", "admin") and password == os.getenv("ADMIN_PASSWORD", "adm2026"):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Credenciais inválidas.")

    @app.get("/admin")
    def admin_dashboard():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        ctf = current_ctf()
        admin_notice = session.pop("admin_notice", None)
        history = []
        conn = get_db()
        history_rows = conn.execute("SELECT * FROM ctfs ORDER BY created_at DESC").fetchall()
        for item in history_rows:
            item_conn = get_db()
            participant_count = item_conn.execute("SELECT COUNT(*) as total FROM participants WHERE ctf_id = ?", (item["id"],)).fetchone()["total"]
            item_conn.close()
            history.append({
                "ctf": dict(item),
                "participants": participant_count,
            })
        conn.close()
        if ctf:
            ranking = participant_ranking(ctf["id"])
            participant_count = len(ranking)
            active_count = sum(1 for row in ranking if not row["finished_at"])
            finished_count = sum(1 for row in ranking if row["finished_at"])
        else:
            ranking = []
            participant_count = 0
            active_count = 0
            finished_count = 0
        return render_template(
            "admin_dashboard.html",
            ctf=ctf,
            ranking=ranking,
            history=history,
            participant_count=participant_count,
            active_count=active_count,
            finished_count=finished_count,
            admin_notice=admin_notice,
        )

    @app.post("/admin/generate")
    def generate_ctf():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        raw_duration = (request.form.get("max_duration_minutes") or "").strip()
        try:
            max_duration_minutes = int(raw_duration) if raw_duration else None
        except ValueError:
            max_duration_minutes = 0
        if max_duration_minutes is not None and not 1 <= max_duration_minutes <= 1440:
            session["admin_notice"] = "Informe a duração máxima em minutos, entre 1 e 1440."
            return redirect(url_for("admin_dashboard"))
        conn = get_db()
        conn.execute("UPDATE ctfs SET status='FINALIZADO', finished_at=? WHERE status='ATIVO'", (timestamp_now(),))
        code = generate_ctf_code()
        now = timestamp_now()
        conn.execute("INSERT INTO ctfs (code, status, created_at, max_duration_minutes) VALUES (?, 'ATIVO', ?, ?)", (code, now, max_duration_minutes))
        conn.commit()
        ctf_id = conn.execute("SELECT id FROM ctfs WHERE code = ? ORDER BY id DESC LIMIT 1", (code,)).fetchone()["id"]
        conn.close()
        log_event(ctf_id, None, "ctf_started", code)
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/finalize")
    def finalize_ctf():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        ctf = current_ctf()
        if not ctf:
            return redirect(url_for("admin_dashboard"))
        conn = get_db()
        conn.execute("UPDATE ctfs SET status='FINALIZADO', finished_at=? WHERE id = ?", (timestamp_now(), ctf["id"]))
        conn.commit()
        conn.close()
        log_event(ctf["id"], None, "ctf_finished", ctf["code"])
        return redirect(url_for("admin_dashboard"))

    @app.get("/admin/logout")
    def admin_logout():
        session.pop("admin_logged_in", None)
        return redirect(url_for("admin_login_page"))

    return app


__all__ = ["create_app", "CHALLENGES"]
