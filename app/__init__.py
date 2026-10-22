import os
import random
import re
import sqlite3
import string
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

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
        "flags": ["JACITEC{map_the_hidden_routes}"],
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
        "difficulty": "Difícil",
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
]

# Cada lista é uma edição fechada: 5 fáceis, 2 médios e 1 difícil. Um desafio
# pertence a uma única lista e tem dificuldade fixa.
for _challenge_id, _mechanism, _difficulty in (
    (1, "source", "Fácil"), (2, "sitemap", "Fácil"), (3, "base64", "Fácil"), (4, "js", "Fácil"),
    (5, "header", "Fácil"), (6, "idor", "Difícil"), (7, "search", "Médio"),
):
    CHALLENGES[_challenge_id - 1].update({"list_id": "lista-1", "mechanism": _mechanism, "difficulty": _difficulty})

# (id, lista, dificuldade, mecanismo, nome, descrição — esta só aparece para a organização)
# Lista 1 = edição CTF 1 (ids 1-7 no literal acima + o 17 aqui).
# Lista 2 = edição CTF 2, com temas e mecanismos novos.
_EXTRA_CHALLENGES = [
    (17, "lista-1", "Médio", "redirect", "Cadeia de redirecionamento", "Siga as respostas HTTP para encontrar a evidência correta."),

    (18, "lista-2", "Fácil", "caesar", "Convite cifrado", "O convite do clube vem com as letras deslocadas; a própria página diz quanto."),
    (19, "lista-2", "Fácil", "backup", "Cópia esquecida", "A rotina de backup da oficina deixou uma cópia do catálogo acessível."),
    (20, "lista-2", "Fácil", "cookie", "Lembrete do balcão", "A padaria guarda a preferência do cliente em um cookie."),
    (21, "lista-2", "Fácil", "svg", "Assinatura do ateliê", "O logo é um SVG e carrega uma anotação da ilustradora no código."),
    (22, "lista-2", "Fácil", "debug", "Modo de diagnóstico", "O painel da transportadora abre um diagnóstico quando recebe o parâmetro certo."),
    (23, "lista-2", "Médio", "login_sqli", "Entrada de serviço", "O login do balcão monta a consulta concatenando o que o usuário digita."),
    (24, "lista-2", "Médio", "token", "Crachá digital", "O crachá do coworking é um token legível que o próprio visitante pode reescrever."),
    (25, "lista-2", "Difícil", "recovery", "Central de recuperação", "Uma rota não divulgada expõe a regra usada para gerar tokens de recuperação."),
]

HINTS_BY_MECHANISM = {
    # --- Lista 1 (edicao CTF 1) ---
    "source": [
        "Ferramenta necessaria: o codigo-fonte da pagina (botao direito -> \"Ver/Exibir codigo-fonte\", ou Ctrl+U).",
        "Nem tudo que existe no HTML aparece renderizado na tela - procure por comentarios e trechos ocultos.",
        "Percorra o documento inteiro, incluindo o que vem antes do <body> e depois do </body>.",
    ],
    "sitemap": [
        "Procure no site um mapa com a lista de paginas e rotas disponiveis.",
        "Um mapa do site pode mostrar paginas que nao aparecem na navegacao principal.",
        "Acesse uma das rotas auxiliares listadas no mapa.",
    ],
    "base64": [
        "Ferramenta necessaria: um decodificador Base64 (no terminal, `base64 -d`; ou o CyberChef no navegador).",
        "O texto codificado nao e criptografia - qualquer decodificador Base64 revela o conteudo original.",
        "Copie exatamente a string codificada, sem espacos extras, antes de decodificar.",
    ],
    "js": [
        "Ferramenta necessaria: DevTools do navegador (abas Console e Sources) para inspecionar o JavaScript carregado.",
        "Variaveis globais definidas em scripts ficam acessiveis digitando o nome delas no Console.",
        "Procure pelo script carregado pela pagina e leia o conteudo na aba Sources.",
    ],
    "header": [
        "Ferramenta necessaria: `curl -i` no terminal (ou DevTools -> Network) para ver os cabecalhos completos da resposta HTTP.",
        "A interface visual nao mostra tudo - os metadados podem estar apenas no cabecalho da resposta.",
        "Repita a requisicao da pagina principal e leia cada cabecalho de resposta, um por um.",
    ],
    "idor": [
        "Ferramenta necessaria: `curl` no terminal, porque e preciso reenviar a requisicao com um cabecalho a mais - o DevTools sozinho nao faz isso. (Burp Suite tambem serve, se voce tiver.)",
        "Depois de ver a requisicao original, tente trocar o identificador do recurso e observe a resposta.",
        "A autorizacao pode depender de um cabecalho que a primeira resposta ja revelou - reenvie a requisicao incluindo-o com `curl -H`.",
    ],
    "search": [
        "Ferramenta necessaria: o proprio formulario de busca, ou `curl` para repetir a requisicao com outro valor.",
        "A busca normal so retorna registros publicos cujo titulo contem o termo pesquisado - procurar palavras do senso comum nao revela nada escondido.",
        "O filtro quebra diante de uma condicao sempre verdadeira dentro de um valor com aspas (fechar a aspa e encadear um OR com algo que sempre bate), nao apenas pela palavra \"or\" estar na busca.",
    ],
    "redirect": [
        "Ferramenta necessaria: `curl` no terminal - e preciso repetir uma das etapas com um cabecalho a mais, e o DevTools nao permite isso. Se for digitar o `curl` do zero, lembre que a requisicao precisa levar o cookie da sua sessao; o atalho e copiar a requisicao no DevTools (botao direito -> \"Copy as cURL\").",
        "Clicar e seguir a cadeia normalmente (302 -> 302 -> 200) nunca mostra a flag, nem olhando o Network: a primeira etapa so devolve um token num cabecalho, que precisa ser usado em outra requisicao.",
        "Reenvie a segunda etapa manualmente com `curl -i -H`, incluindo o token obtido na primeira resposta - so assim a flag aparece.",
    ],

    # --- Lista 2 (edicao CTF 2) ---
    "caesar": [
        "Ferramenta necessaria: nenhuma alem de paciencia - ou um decodificador de cifra de Cesar na internet.",
        "As letras do codigo foram deslocadas no alfabeto. A propria pagina diz de quanto foi o deslocamento; procure um numero que pareca fora de lugar.",
        "Volte cada letra o numero de casas indicado. Numeros e pontuacao nao mudam, so as letras.",
    ],
    "backup": [
        "Ferramenta necessaria: o navegador ou `curl` para abrir um arquivo direto pela URL.",
        "A pagina explica como a oficina nomeia as copias de seguranca dos arquivos. Repare na extensao que a rotina acrescenta.",
        "Pegue o endereco do arquivo que ja esta publicado e peca a copia dele acrescentando essa extensao no fim da URL.",
    ],
    "cookie": [
        "Ferramenta necessaria: `curl -i` no terminal, ou DevTools -> aba Application/Armazenamento -> Cookies.",
        "Ao abrir a pagina, o servidor pede ao navegador para guardar uma preferencia. Isso viaja num cabecalho Set-Cookie.",
        "Leia o valor do cookie que a pagina inicial grava - a flag esta ali, nao na tela.",
    ],
    "svg": [
        "Ferramenta necessaria: o navegador ou `curl` para abrir o arquivo da imagem direto pela URL.",
        "O logo nao e uma foto: e um SVG, que por dentro e texto. Descubra o endereco do arquivo no HTML da pagina.",
        "Abra o .svg pela URL e leia o codigo dele - ha uma anotacao escrita entre as formas do desenho.",
    ],
    "debug": [
        "Ferramenta necessaria: `curl` no terminal, ou a barra de endereco do navegador.",
        "A pagina avisa que tem um modo de diagnostico ligado por um parametro na URL. Veja no texto como ele se chama.",
        "Adicione esse parametro a URL (por exemplo ?debug=1) e leia a resposta: o diagnostico imprime dados internos, flag inclusa.",
    ],
    "login_sqli": [
        "Ferramenta necessaria: o proprio formulario de login, ou `curl` para enviar os campos.",
        "O servidor monta a consulta juntando texto com o que voce digita no usuario e na senha, sem tratar aspas.",
        "Encerre a parte do usuario com uma aspa e faca a condicao de senha sempre verdadeira comentando o resto - um classico `' OR '1'='1' --`.",
    ],
    "token": [
        "Ferramenta necessaria: um decodificador Base64 e `curl` para reenviar o cookie alterado (ou DevTools -> Application -> Cookies para edita-lo).",
        "O cracha e um cookie em Base64. Decodifique e veja que por dentro ha um texto legivel com o seu papel (role).",
        "Troque o papel para o de administrador, recodifique em Base64 e reenvie o cookie: a area restrita passa a mostrar a flag.",
    ],
    "recovery": [
        "Ferramenta necessaria: `curl` no terminal. Nenhum Burp e necessario - tudo se resolve lendo respostas e refazendo pedidos.",
        "Ha uma rota de diagnostico nao divulgada (o robots.txt ou um comentario aponta para ela) que revela como o token de recuperacao e formado.",
        "O token nao e aleatorio: ele vem de um dado publico do usuario passado por um processo simples. Reproduza esse processo para o usuario-alvo e use o token na rota de redefinicao.",
    ],
}


def _hints_for(mechanism):
    return list(HINTS_BY_MECHANISM.get(mechanism, [
        "Comece observando o comportamento normal da aplicação.",
        "Use a ferramenta indicada no enunciado para comparar a resposta.",
        "A pista está no mecanismo técnico do laboratório, não na interface visível.",
    ]))


for _challenge in CHALLENGES:
    _challenge["hints"] = _hints_for(_challenge["mechanism"])

CHALLENGE_HINTS = {
    1: [
        "Como o laboratório abre dentro de um iframe, use F12 e o seletor de elementos; clique dentro do site para inspecionar o documento dele na aba Elements.",
        "Na árvore de elementos do laboratório, examine os comentários HTML, não o código-fonte da página externa do CTF.",
        "O comentário que contém a flag está logo no início do documento do laboratório.",
    ],
    2: [
        "Abra \"Guias de viagem\" no menu do Wayfarer e procure o link para o mapa do portal.",
        "O mapa do site lista páginas auxiliares que não aparecem na navegação principal.",
        "O mapa revela a rota /lab/2/files/report. Abra-a: a referência no relatório é JACITEC{map_the_hidden_routes}.",
    ],
    3: [
        "Abra a documentação pelo botão \"Ler documentação da API\" na página inicial do Devdesk.",
        "Na seção \"Campo de token legado\", o bloco de código contém uma sequência em Base64. Converta-a em texto legível com um decodificador; não é uma senha para testar no site.",
        "A decodificação revela diretamente a flag: JACITEC{base64_is_not_a_secret}.",
    ],
    4: [
        "Use F12 e inspecione o documento do laboratório Pixel Arcade dentro do iframe.",
        "Na aba Sources, localize o script inline no fim do documento da página inicial.",
        "Leia o valor atribuído à constante arcadeReleaseNote; não é necessário clicar em \"Verificar atualização\".",
    ],
    5: [
        "Abra o DevTools na aba Network e selecione a requisição GET da página inicial do laboratório Second Story.",
        "Consulte os cabeçalhos de resposta (Response Headers) dessa requisição.",
        "O valor do cabeçalho X-Campus-Notice é a flag; não é um cookie.",
    ],
}
for _challenge in CHALLENGES:
    if _challenge["id"] in CHALLENGE_HINTS:
        _challenge["hints"] = CHALLENGE_HINTS[_challenge["id"]]

for _id, _list_id, _difficulty, _mechanism, _name, _description in _EXTRA_CHALLENGES:
    CHALLENGES.append({
        "id": _id, "title": f"Desafio {_id}", "name": _name,
        "difficulty": _difficulty, "list_id": _list_id, "mechanism": _mechanism,
        "flags": [f"JACITEC{{catalog_{_id}_{_mechanism}}}"], "description": _description,
        "hints": _hints_for(_mechanism),
    })

# Peso-base por dificuldade (antes da normalização para 1.000 pontos por
# edição) e identificador legível de cada desafio: L<lista>-<F|M|D><nº>,
# ex.: L2-M03 = lista 2, terceiro desafio médio.
DIFFICULTY_LETTERS = {"Fácil": "F", "Médio": "M", "Difícil": "D"}
_ordinals = {}
for _challenge in sorted(CHALLENGES, key=lambda item: item["id"]):
    _challenge["points"] = {"Fácil": 5, "Médio": 8, "Difícil": 10}[_challenge["difficulty"]]
    _challenge["hint_deductions"] = [0, 1, 2, 3]
    _key = (_challenge["list_id"], _challenge["difficulty"])
    _ordinals[_key] = _ordinals.get(_key, 0) + 1
    _challenge["list_number"] = int(_challenge["list_id"].split("-")[1])
    _challenge["code"] = f"L{_challenge['list_number']}-{DIFFICULTY_LETTERS[_challenge['difficulty']]}{_ordinals[_key]:02d}"

EDITION_SHAPE = {"F": 5, "M": 2, "D": 1}
assert all(
    count == EDITION_SHAPE[DIFFICULTY_LETTERS[difficulty]]
    for (_, difficulty), count in _ordinals.items()
) and len(_ordinals) == 3 * len({list_id for list_id, _ in _ordinals}), \
    "Cada lista deve ter exatamente 5 fáceis, 2 médios e 1 difícil."

# Os oito laboratórios originais (id 1-8) têm cada um seu próprio site
# artesanal em lab_site.html. Os 46 laboratórios extra reaproveitam essas
# mesmas paletas/CSS já com bom contraste, alternando marca e nome para dar
# variedade visual sem repetir o layout genérico único que causava textos e
# botões praticamente invisíveis (texto claro sobre fundo claro).
SITE_THEMES = [
    {"n": 1, "header": "blog-header", "content": "blog-layout", "button": "scenario-cta",
     "brands": [("PAPEL", "VIVO"), ("ARCHIVO", "EDITORIAL"), ("FOLHA", "ABERTA")]},
    {"n": 2, "header": "trail-header", "content": "trail-content", "button": "scenario-cta",
     "brands": [("ROTA", "LIVRE"), ("HORIZONTE", "TRAVEL"), ("CAMINHO", "ABERTO")]},
    {"n": 3, "header": "dev-header", "content": "dev-content", "button": "dev-button",
     "brands": [("BYTE", "DESK"), ("STACK", "FORGE"), ("CODE", "HAVEN")]},
    {"n": 4, "header": "arcade-header", "content": "arcade-content", "button": "arcade-button",
     "brands": [("RETRO", "CIRCUIT"), ("NEON", "QUEST"), ("PIXEL", "FORGE")]},
    {"n": 5, "header": "market-header", "content": "market-content", "button": "market-button",
     "brands": [("MERCADO", "VERDE"), ("OFICINA", "NOVA"), ("BAZAR", "CIRCULAR")]},
    {"n": 6, "header": "cloud-header", "content": "cloud-content", "button": "cloud-button",
     "brands": [("DATA", "HIVE"), ("NUVEM", "SEGURA"), ("ARQUIVO", "X")]},
    {"n": 7, "header": "ticket-header", "content": "ticket-content", "button": "ticket-button",
     "brands": [("CITY", "PULSE"), ("AFTER", "HOURS"), ("LUZ", "NOTURNA")]},
    {"n": 8, "header": "booking-header", "content": "booking-content", "button": "booking-button",
     "brands": [("ESPAÇO", "ÁGIL"), ("SALA", "CERTA"), ("WORK", "HUB")]},
]
# Cópia de apoio por skin visual (tom/ambientação), independente da marca
# sorteada — dá a cada um dos 46 laboratórios extras um site com hero, guia,
# status e equipe coerentes com a paleta, em vez do único template genérico
# reaproveitado para todos eles.
THEME_COPY = {
    1: {"kicker": "ESTÚDIO EDITORIAL INDEPENDENTE", "hero": "Boas histórias também escondem bons detalhes.",
        "body": "Publicamos ensaios, notas de bastidor e pequenos projetos experimentais.",
        "guide_title": "Sobre a publicação", "guide_body": "Um pequeno time editorial que também cuida do próprio código — às vezes com mais cuidado do lado do texto do que do lado técnico.",
        "status_title": "Estado da publicação", "team_title": "Quem escreve por aqui",
        "team_body": "Uma equipe enxuta de editores e desenvolvedores dividindo a mesma redação."},
    2: {"kicker": "AGÊNCIA DE VIAGENS INDEPENDENTE", "hero": "Todo bom roteiro tem uma nota de rodapé.",
        "body": "Guias de viagem, roteiros autorais e recomendações de quem já foi.",
        "guide_title": "Como organizamos os roteiros", "guide_body": "Nossos guias combinam recomendações locais com informações práticas — nem sempre tudo cabe na página principal.",
        "status_title": "Status da operação", "team_title": "Nossos guias locais",
        "team_body": "Viajantes experientes que testam cada roteiro antes de publicar."},
    3: {"kicker": "PLATAFORMA PARA TIMES DE PRODUTO", "hero": "Ferramentas internas, sem complicação.",
        "body": "Uma API simples para equipes pequenas automatizarem tarefas repetitivas.",
        "guide_title": "Documentação rápida", "guide_body": "A maior parte da integração é direta, mas alguns detalhes de implantação só aparecem inspecionando o ambiente.",
        "status_title": "Status da plataforma", "team_title": "Equipe de engenharia",
        "team_body": "Um time pequeno mantendo uma base de código enxuta."},
    4: {"kicker": "ARCADE DIGITAL RETRÔ", "hero": "Toda boa pontuação tem uma história por trás.",
        "body": "Uma coleção de jogos independentes com estética retrô e comunidade ativa.",
        "guide_title": "Como funciona a plataforma", "guide_body": "Progresso, conquistas e configurações do jogador ficam sincronizados — nem tudo aparece na tela principal.",
        "status_title": "Status dos servidores", "team_title": "Time de desenvolvimento",
        "team_body": "Uma equipe indie apaixonada por jogos old-school."},
    5: {"kicker": "LOJA DE ITENS SEMINOVOS", "hero": "Boas peças merecem uma segunda história.",
        "body": "Curadoria de itens vintage, restaurados e conferidos um a um.",
        "guide_title": "Como cuidamos de cada peça", "guide_body": "Cada item passa por uma checagem antes de entrar no catálogo — o processo é mais detalhado do que parece na vitrine.",
        "status_title": "Status da operação", "team_title": "Equipe da oficina",
        "team_body": "Curadores e restauradores cuidando de cada peça."},
    6: {"kicker": "ARMAZENAMENTO EM NUVEM", "hero": "Seus arquivos, sempre ao alcance.",
        "body": "Compartilhamento simples de arquivos para pessoas e pequenas equipes.",
        "guide_title": "Segurança e acesso", "guide_body": "O controle de acesso a arquivos compartilhados depende de mais validações do que a interface mostra diretamente.",
        "status_title": "Status do serviço", "team_title": "Equipe de infraestrutura",
        "team_body": "Um time pequeno cuidando de armazenamento e sincronização."},
    7: {"kicker": "INGRESSOS PARA EVENTOS LOCAIS", "hero": "Sua próxima noite começa com uma boa busca.",
        "body": "Descubra shows, exposições e eventos independentes perto de você.",
        "guide_title": "Como funciona a busca", "guide_body": "O catálogo de eventos é maior do que o que aparece na home — a busca é o caminho para o resto do acervo.",
        "status_title": "Status da bilheteria", "team_title": "Equipe de curadoria",
        "team_body": "Curadores locais selecionando os melhores eventos."},
    8: {"kicker": "RESERVA DE ESPAÇOS DE TRABALHO", "hero": "Espaço certo, sem fricção.",
        "body": "Reserva simples de salas e espaços para equipes híbridas.",
        "guide_title": "Como gerenciamos reservas", "guide_body": "O sistema clássico de reservas ainda mantém alguns registros operacionais visíveis para quem sabe onde procurar.",
        "status_title": "Status da agenda", "team_title": "Equipe de operações",
        "team_body": "Um time pequeno cuidando da disponibilidade dos espaços."},
}
for _challenge in CHALLENGES:
    if _challenge["id"] <= 8:
        continue
    _theme = SITE_THEMES[(_challenge["id"] - 9) % len(SITE_THEMES)]
    _brand_main, _brand_accent = _theme["brands"][((_challenge["id"] - 9) // len(SITE_THEMES)) % len(_theme["brands"])]
    _challenge["site"] = {
        "theme": _theme["n"], "header": _theme["header"], "content": _theme["content"], "button": _theme["button"],
        "brand_main": _brand_main, "brand_accent": _brand_accent,
        **THEME_COPY[_theme["n"]],
    }

CHALLENGE_BY_ID = {challenge["id"]: challenge for challenge in CHALLENGES}

def _caesar_shift(text, shift):
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)


# Sites dedicados da lista 2. O conteúdo de cada site mora no template
# (lab_site.html); aqui ficam só o tema de cor, a marca e o que é calculado.
_CAESAR_SHIFT = 5
SITE2 = {
    18: {"theme": "club", "brand_main": "FESTA", "brand_accent": "MEIA-NOITE",
         "caesar": _caesar_shift("JACITEC{catalog_18_caesar}", _CAESAR_SHIFT), "shift": _CAESAR_SHIFT},
    19: {"theme": "wood", "brand_main": "MARCENARIA", "brand_accent": "RAIZ"},
    20: {"theme": "bakery", "brand_main": "PÃO", "brand_accent": "GRÃO"},
    21: {"theme": "atelier", "brand_main": "ATELIÊ", "brand_accent": "LUMEN"},
    22: {"theme": "freight", "brand_main": "ROTA", "brand_accent": "LOG"},
    23: {"theme": "desk", "brand_main": "BALCÃO", "brand_accent": "INTERNO"},
    24: {"theme": "cowork", "brand_main": "NÚCLEO", "brand_accent": "HUB"},
    25: {"theme": "central", "brand_main": "CENTRAL", "brand_accent": "ID"},
}
for _cid, _data in SITE2.items():
    CHALLENGE_BY_ID[_cid]["site2"] = _data

# Só a seleção fixa fica disponível para gerar eventos. O catálogo completo
# (lista-1/2/3) continua existindo por trás, porque os desafios são
# referenciados por id nos eventos já realizados.
CHALLENGE_LISTS = {
    "ctf-1": {"label": "CTF 1", "description": "Seleção fixa: 5 fáceis, 2 médios e 1 difícil."},
    "ctf-2": {"label": "CTF 2", "description": "Seleção fixa: 5 fáceis, 2 médios e 1 difícil."},
}
FIXED_CHALLENGE_LISTS = {
    "ctf-1": (1, 2, 3, 4, 5, 6, 7, 17),
    "ctf-2": (18, 19, 20, 21, 22, 23, 24, 25),
}
DEFAULT_CHALLENGE_LIST = "ctf-2"

# Versão da plataforma (semver). Suba a cada entrega: patch para correções,
# minor para funcionalidades novas, major para mudanças incompatíveis.
APP_VERSION = "1.1.2"


def timestamp_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# O admin preenche a agenda no horário local do evento; o banco guarda tudo em
# UTC, como o resto do app, para a comparação com timestamp_now() bater.
EVENT_TIMEZONE = ZoneInfo(os.getenv("EVENT_TIMEZONE", "America/Sao_Paulo"))


def local_to_utc(date_value, time_value, fallback_time="00:00"):
    """'2026-11-14' + '19:30' (horário local) -> '2026-11-14 22:30:00' em UTC."""
    date_value = (date_value or "").strip()
    if not date_value:
        return None
    time_value = (time_value or "").strip() or fallback_time
    try:
        local = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return local.replace(tzinfo=EVENT_TIMEZONE).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def utc_to_local(stamp):
    """Datetime local (aware) a partir de um timestamp UTC do banco."""
    if not stamp:
        return None
    try:
        parsed = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).astimezone(EVENT_TIMEZONE)


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
    if "challenge_list_id" not in ctf_columns:
        conn.execute("ALTER TABLE ctfs ADD COLUMN challenge_list_id TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ctf_challenges (
            ctf_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            base_points INTEGER,
            hint_penalty INTEGER,
            PRIMARY KEY (ctf_id, challenge_id),
            UNIQUE (ctf_id, position),
            FOREIGN KEY(ctf_id) REFERENCES ctfs(id)
        )
        """
    )
    ctf_challenge_columns = {row["name"] for row in conn.execute("PRAGMA table_info(ctf_challenges)").fetchall()}
    if "base_points" not in ctf_challenge_columns:
        conn.execute("ALTER TABLE ctf_challenges ADD COLUMN base_points INTEGER")
    if "hint_penalty" not in ctf_challenge_columns:
        conn.execute("ALTER TABLE ctf_challenges ADD COLUMN hint_penalty INTEGER")
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
        CREATE TABLE IF NOT EXISTS participant_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ctf_id INTEGER NOT NULL,
            participant_id INTEGER,
            name TEXT NOT NULL,
            turma TEXT,
            difficulty TEXT,
            clarity TEXT,
            favorite_part TEXT,
            time_enough TEXT,
            organization_rating INTEGER,
            improvements TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(participant_id),
            FOREIGN KEY(ctf_id) REFERENCES ctfs(id)
        )
        """
    )
    feedback_columns = {row["name"] for row in conn.execute("PRAGMA table_info(participant_feedback)").fetchall()}
    if "favorite_part_other" not in feedback_columns:
        conn.execute("ALTER TABLE participant_feedback ADD COLUMN favorite_part_other TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT,
            details TEXT,
            starts_at TEXT NOT NULL,
            ends_at TEXT,
            banner_starts_at TEXT NOT NULL,
            banner_ends_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    schedule_columns = {row["name"] for row in conn.execute("PRAGMA table_info(scheduled_events)").fetchall()}
    if "signup_url" not in schedule_columns:
        conn.execute("ALTER TABLE scheduled_events ADD COLUMN signup_url TEXT")
    # Listas liberadas para treino livre: a presença da linha já significa
    # "disponível em /treino".
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS training_lists (
            list_id TEXT PRIMARY KEY,
            enabled_at TEXT NOT NULL
        )
        """
    )
    # Uma "edição" junta uma ou mais rodadas de CTF num resultado final único,
    # montado à mão pelo admin.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS editions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            summary TEXT,
            status TEXT NOT NULL DEFAULT 'rascunho',
            show_challenges INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            published_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_ctfs (
            edition_id INTEGER NOT NULL,
            ctf_id INTEGER NOT NULL,
            PRIMARY KEY (edition_id, ctf_id),
            FOREIGN KEY(edition_id) REFERENCES editions(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_feedback (
            edition_id INTEGER NOT NULL,
            feedback_id INTEGER NOT NULL,
            PRIMARY KEY (edition_id, feedback_id),
            FOREIGN KEY(edition_id) REFERENCES editions(id)
        )
        """
    )
    # Uma fusão vira um participante NOVO e editável; as participações de
    # origem continuam intactas no banco, só saem da classificação final.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_merges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edition_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            challenge_ids TEXT NOT NULL,
            points INTEGER NOT NULL,
            elapsed INTEGER NOT NULL,
            hidden INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(edition_id) REFERENCES editions(id)
        )
        """
    )
    merge_columns = {row["name"] for row in conn.execute("PRAGMA table_info(edition_merges)").fetchall()}
    if "challenge_points" not in merge_columns:
        conn.execute("ALTER TABLE edition_merges ADD COLUMN challenge_points TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_merge_sources (
            merge_id INTEGER NOT NULL,
            participant_id INTEGER NOT NULL,
            PRIMARY KEY (merge_id, participant_id),
            FOREIGN KEY(merge_id) REFERENCES edition_merges(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_participants (
            edition_id INTEGER NOT NULL,
            participant_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            included INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (edition_id, participant_id),
            FOREIGN KEY(edition_id) REFERENCES editions(id)
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


def challenges_for_ctf(ctf_id):
    """Return the immutable, ordered challenge selection for one CTF.

    Older databases/events did not store selections; their legacy eight are kept
    available as a safe migration fallback.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT challenge_id, base_points, hint_penalty FROM ctf_challenges WHERE ctf_id = ? ORDER BY position", (ctf_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return CHALLENGES[:8]
    selected = []
    for row in rows:
        challenge = CHALLENGE_BY_ID.get(row["challenge_id"])
        if challenge:
            challenge = dict(challenge)
            if row["base_points"] is not None:
                challenge["event_points"] = row["base_points"]
                challenge["event_hint_penalty"] = row["hint_penalty"] or 0
            selected.append(challenge)
    return selected


def active_challenges():
    ctf = current_ctf()
    return challenges_for_ctf(ctf["id"]) if ctf else []


def challenge_for_ctf(ctf_id, challenge_id):
    return next((item for item in challenges_for_ctf(ctf_id) if item["id"] == challenge_id), None)


def challenge_pool(list_id, difficulty):
    """The full catalog for one list/difficulty: always 10 fáceis, 5 médios e
    3 difíceis per list. Editions freely reuse challenges across events — the
    catalog is meant to be drawn from repeatedly, not exhausted."""
    if list_id in FIXED_CHALLENGE_LISTS:
        challenge_ids = FIXED_CHALLENGE_LISTS[list_id]
        return [
            item for item in CHALLENGES
            if item["id"] in challenge_ids and item["difficulty"] == difficulty
        ]
    return [item for item in CHALLENGES if item["list_id"] == list_id and item["difficulty"] == difficulty]


def normalize_event_scores(challenges):
    """Allocate exactly 1,000 maximum points using the 5/8/10 difficulty weights."""
    weights = [challenge["points"] for challenge in challenges]
    total_weight = sum(weights)
    raw = [1000 * weight / total_weight for weight in weights]
    bases = [int(value) for value in raw]
    for index in sorted(range(len(raw)), key=lambda item: raw[item] - bases[item], reverse=True)[:1000 - sum(bases)]:
        bases[index] += 1
    return [(base, max(1, round(base / weight))) for base, weight in zip(bases, weights)]


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


def participant_event_summary(participant_id):
    if not participant_id:
        return None
    conn = get_db()
    participant = conn.execute(
        "SELECT id, ctf_id, finished_at FROM participants WHERE id = ?",
        (participant_id,),
    ).fetchone()
    if not participant:
        conn.close()
        return None
    ctf = conn.execute("SELECT id, code, status FROM ctfs WHERE id = ?", (participant["ctf_id"],)).fetchone()
    conn.close()
    if not ctf:
        return None
    return {
        "ctf_id": ctf["id"],
        "code": ctf["code"],
        "ctf_status": ctf["status"],
        "participant_finished": bool(participant["finished_at"]),
    }


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


# Faixas Unicode de emojis/símbolos gráficos — usadas para barrar nomes com
# emoji ou spam de símbolos, mantendo acentos e letras normais permitidos.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F0FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "\U0000200D"
    "]"
)


def validate_participant_name(raw_name):
    """Valida o nome informado ao entrar no CTF.

    Retorna (nome_limpo, None) se válido, ou (None, mensagem_de_erro) caso
    contrário. Bloqueia nomes vazios, muito longos, com emoji ou com
    repetição excessiva de um mesmo caractere (spam).
    """
    name = " ".join((raw_name or "").split())
    if not name:
        return None, "Informe o seu nome para entrar no CTF."
    if len(name) > 30:
        return None, "O nome deve ter no máximo 30 caracteres."
    if _EMOJI_PATTERN.search(name):
        return None, "O nome não pode conter emojis."
    if re.search(r"(.)\1{3,}", name):
        return None, "Escolha um nome sem repetições excessivas do mesmo caractere."
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name):
        return None, "O nome deve conter ao menos uma letra."
    return name, None


# Perguntas do feedback pós-participação. Só o nome é obrigatório; qualquer
# resposta pode ficar em branco, e o participante pode pular a tela inteira.
FEEDBACK_QUESTIONS = (
    {"field": "difficulty", "label": "Como você avalia a dificuldade dos desafios?",
     "options": ("Muito fácil", "Fácil", "Ideal", "Difícil", "Muito difícil")},
    {"field": "clarity", "label": "Os enunciados dos desafios foram claros?",
     "options": ("Sim", "Parcialmente", "Não")},
    {"field": "favorite_part", "label": "Qual parte do CTF você mais gostou?",
     "options": ("Desafios web", "Desafios de terminal", "Ranking e competição", "Dicas e suporte da organização", "Outro"),
     "multi": True, "hint": "Pode marcar mais de uma.",
     "other_option": "Outro", "other_field": "favorite_part_other"},
    {"field": "time_enough", "label": "O tempo do CTF foi suficiente?",
     "options": ("Sim", "Parcialmente", "Não")},
)
# Respostas de múltipla escolha moram em uma coluna só, unidas por "; " (nenhuma
# das opções contém esse separador).
FEEDBACK_MULTI_SEPARATOR = "; "
FEEDBACK_OTHER_MAX = 120
FEEDBACK_RATING_LABEL = "Como você avalia a organização do evento?"
FEEDBACK_IMPROVEMENTS_LABEL = "O que podemos melhorar nas próximas edições?"
FEEDBACK_IMPROVEMENTS_MAX = 1000


def clean_feedback_payload(form):
    """Normaliza o formulário de feedback, descartando valores fora das opções.

    Devolve (dados, erro_de_nome): só o nome é validado de verdade; o resto é
    opcional e vira None quando em branco ou inválido.
    """
    name, name_error = validate_participant_name(form.get("name"))
    if name_error:
        return None, name_error
    data = {"name": name, "turma": " ".join((form.get("turma") or "").split())[:40] or None}
    for question in FEEDBACK_QUESTIONS:
        if question.get("multi"):
            chosen = [value for value in form.getlist(question["field"]) if value in question["options"]]
            data[question["field"]] = FEEDBACK_MULTI_SEPARATOR.join(chosen) or None
        else:
            value = (form.get(question["field"]) or "").strip()
            chosen = [value] if value in question["options"] else []
            data[question["field"]] = chosen[0] if chosen else None
        # O texto livre de "Outro" só é guardado se a opção foi mesmo marcada.
        if question.get("other_field"):
            text = (form.get(question["other_field"]) or "").strip()[:FEEDBACK_OTHER_MAX]
            data[question["other_field"]] = text if text and question["other_option"] in chosen else None
    try:
        rating = int((form.get("organization_rating") or "").strip())
    except ValueError:
        rating = None
    data["organization_rating"] = rating if rating in (1, 2, 3, 4, 5) else None
    improvements = (form.get("improvements") or "").strip()
    data["improvements"] = improvements[:FEEDBACK_IMPROVEMENTS_MAX] or None
    return data, None


def feedback_answers(entry, question):
    """Respostas de uma pergunta como lista (1 item, ou várias no multi)."""
    raw = entry.get(question["field"])
    if not raw:
        return []
    return raw.split(FEEDBACK_MULTI_SEPARATOR) if question.get("multi") else [raw]


def feedback_for_ctf(ctf_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM participant_feedback WHERE ctf_id = ? ORDER BY created_at DESC, id DESC",
        (ctf_id,),
    ).fetchall()
    conn.close()
    entries = []
    for row in rows:
        entry = dict(row)
        entry["answers"] = {
            question["field"]: feedback_answers(entry, question) for question in FEEDBACK_QUESTIONS
        }
        entries.append(entry)
    return entries


def feedback_summary(entries):
    """Contagem por opção e média da nota, para a visão geral do admin."""
    questions = []
    for question in FEEDBACK_QUESTIONS:
        counts = {}
        for entry in entries:
            for value in entry["answers"][question["field"]]:
                counts[value] = counts.get(value, 0) + 1
        answered = sum(1 for entry in entries if entry["answers"][question["field"]])
        questions.append({
            "label": question["label"],
            "answered": answered,
            "multi": bool(question.get("multi")),
            "counts": [
                {"option": option, "total": counts[option], "percent": round(counts[option] * 100 / answered) if answered else 0}
                for option in question["options"] if counts.get(option)
            ],
            "others": [entry[question["other_field"]] for entry in entries if question.get("other_field") and entry.get(question["other_field"])],
        })
    ratings = [entry["organization_rating"] for entry in entries if entry["organization_rating"]]
    return {
        "questions": questions,
        "rating_average": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "rating_count": len(ratings),
        "comments": [entry for entry in entries if entry["improvements"]],
    }


EDITION_NAME_MAX = 80
EDITION_SUMMARY_MAX = 400


def edition_row(edition_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM editions WHERE id = ?", (edition_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def edition_ctf_ids(edition_id):
    conn = get_db()
    rows = conn.execute("SELECT ctf_id FROM edition_ctfs WHERE edition_id = ?", (edition_id,)).fetchall()
    conn.close()
    return [row["ctf_id"] for row in rows]


def edition_entries(edition_id):
    """Participações da edição, com o nome de exibição escolhido pelo admin."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ep.participant_id, ep.display_name, ep.included,
                  p.name AS original_name, p.ctf_id, p.entered_at, p.finished_at, c.code AS ctf_code
           FROM edition_participants ep
           JOIN participants p ON p.id = ep.participant_id
           JOIN ctfs c ON c.id = p.ctf_id
           WHERE ep.edition_id = ?
           ORDER BY p.ctf_id, p.entered_at""",
        (edition_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _participant_elapsed(entry, event_finished_at):
    if not entry["entered_at"]:
        return 0
    ended = entry["finished_at"] or event_finished_at or timestamp_now()
    try:
        delta = datetime.strptime(ended, "%Y-%m-%d %H:%M:%S") - datetime.strptime(entry["entered_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    return max(0, int(delta.total_seconds()))


def participation_stats(participant_id, event_finished_at=None):
    """Desafios resolvidos, pontos e tempo de uma participação."""
    conn = get_db()
    participant = conn.execute(
        "SELECT id, name, ctf_id, entered_at, finished_at FROM participants WHERE id = ?",
        (participant_id,),
    ).fetchone()
    if not participant:
        conn.close()
        return None
    rows = conn.execute(
        """SELECT challenge_id, score_earned, hints_used FROM participant_challenges
           WHERE participant_id = ? AND status = 'solved'""",
        (participant_id,),
    ).fetchall()
    event = conn.execute("SELECT code, finished_at FROM ctfs WHERE id = ?", (participant["ctf_id"],)).fetchone()
    ctf_code = event["code"] if event else "—"
    if event_finished_at is None:
        event_finished_at = event["finished_at"] if event else None
    conn.close()
    challenges = []
    for row in rows:
        catalog = CHALLENGE_BY_ID.get(row["challenge_id"])
        challenges.append({
            "id": row["challenge_id"],
            "name": catalog["name"] if catalog else f"Desafio {row['challenge_id']}",
            "difficulty": catalog["difficulty"] if catalog else "—",
            "points": row["score_earned"] or 0,
            "hints_used": row["hints_used"] or 0,
        })
    challenges.sort(key=lambda item: -item["points"])
    return {
        "participant_id": participant["id"],
        "name": participant["name"],
        "ctf_id": participant["ctf_id"],
        "ctf_code": ctf_code,
        "entered_at": participant["entered_at"],
        "ended_at": participant["finished_at"] or event_finished_at,
        "challenges": challenges,
        "points": sum(item["points"] for item in challenges),
        "solved": len(challenges),
        "elapsed": _participant_elapsed(dict(participant), event_finished_at),
    }


def edition_round_rankings(edition_id):
    """Classificação de cada rodada, exatamente como ela aconteceu."""
    entries = [entry for entry in edition_entries(edition_id) if entry["included"]]
    by_round = {}
    for entry in entries:
        stats = participation_stats(entry["participant_id"])
        if not stats:
            continue
        group = by_round.setdefault(entry["ctf_code"], [])
        group.append({
            "name": entry["original_name"],
            "points": stats["points"],
            "solved": stats["solved"],
            "elapsed": stats["elapsed"],
            "entered_at": stats["entered_at"],
            "ended_at": stats["ended_at"],
            "challenges": stats["challenges"],
        })
    rounds = []
    for code in sorted(by_round):
        rows = sorted(by_round[code], key=lambda item: (-item["points"], item["elapsed"], item["name"].lower()))
        for position, row in enumerate(rows, start=1):
            row["position"] = position
        rounds.append({"ctf_code": code, "rows": rows})
    return rounds


def edition_merge_rows(edition_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM edition_merges WHERE edition_id = ? ORDER BY id", (edition_id,)
    ).fetchall()
    merges = []
    for row in rows:
        sources = conn.execute(
            """SELECT ems.participant_id, p.name AS original_name, c.code AS ctf_code
               FROM edition_merge_sources ems
               JOIN participants p ON p.id = ems.participant_id
               JOIN ctfs c ON c.id = p.ctf_id
               WHERE ems.merge_id = ?""",
            (row["id"],),
        ).fetchall()
        merge = dict(row)
        merge["challenge_ids"] = json.loads(merge["challenge_ids"])
        merge["challenge_points"] = json.loads(merge["challenge_points"] or "{}")
        merge["sources"] = [dict(item) for item in sources]
        merges.append(merge)
    conn.close()
    return merges


def merge_preview(participant_ids):
    """Números propostos ao fundir participações: desafios, pontos e tempo.

    Desafio repetido entre participações entra uma vez só, valendo a MENOR
    pontuação obtida — se a pessoa resolveu o mesmo desafio duas vezes, conta
    a tentativa mais cara (a que usou mais dicas). O tempo soma entre rodadas
    diferentes e, na mesma rodada, vale só a maior das entradas.
    """
    chosen, origins, elapsed_by_ctf, sources = {}, {}, {}, []
    for participant_id in participant_ids:
        stats = participation_stats(participant_id)
        if not stats:
            continue
        for challenge in stats["challenges"]:
            current = chosen.get(challenge["id"])
            if not current or challenge["points"] < current["points"]:
                chosen[challenge["id"]] = dict(challenge)
            origins.setdefault(challenge["id"], []).append({
                "name": stats["name"], "points": challenge["points"],
            })
        previous = elapsed_by_ctf.get(stats["ctf_id"], 0)
        elapsed_by_ctf[stats["ctf_id"]] = max(previous, stats["elapsed"])
        sources.append({
            "participant_id": participant_id, "name": stats["name"], "ctf_id": stats["ctf_id"],
            "ctf_code": stats["ctf_code"], "entered_at": stats["entered_at"],
            "ended_at": stats["ended_at"], "elapsed": stats["elapsed"],
            "counted": True, "points": stats["points"], "solved": stats["solved"],
        })
    # Numa mesma rodada só o maior tempo entra na conta: marca quais contaram.
    for ctf_id, total in elapsed_by_ctf.items():
        same_round = [item for item in sources if item["ctf_id"] == ctf_id]
        winner = max(same_round, key=lambda item: item["elapsed"])
        for item in same_round:
            item["counted"] = item is winner
    challenges = sorted(chosen.values(), key=lambda item: -item["points"])
    for challenge in challenges:
        challenge["origins"] = origins.get(challenge["id"], [])
        challenge["duplicated"] = len(challenge["origins"]) > 1
    return {
        "challenges": challenges,
        "points": sum(item["points"] for item in challenges),
        "elapsed": sum(elapsed_by_ctf.values()),
        "suggested_name": sources[0]["name"] if sources else "",
        "sources": sources,
    }


def edition_final_ranking(edition_id):
    """Classificação final: participações avulsas + participantes fundidos."""
    merges = edition_merge_rows(edition_id)
    merged_ids = {source["participant_id"] for merge in merges for source in merge["sources"]}
    rows = []
    for entry in edition_entries(edition_id):
        if not entry["included"] or entry["participant_id"] in merged_ids:
            continue
        stats = participation_stats(entry["participant_id"])
        if not stats:
            continue
        rows.append({
            "kind": "single", "key": entry["participant_id"], "name": entry["original_name"],
            "points": stats["points"], "solved": stats["solved"], "elapsed": stats["elapsed"],
            "challenges": stats["challenges"],
            "sources": [{"original_name": entry["original_name"], "ctf_code": entry["ctf_code"]}],
        })
    for merge in merges:
        if merge["hidden"]:
            continue
        chosen = [CHALLENGE_BY_ID.get(cid) for cid in merge["challenge_ids"]]
        rows.append({
            "kind": "merge", "key": merge["id"], "name": merge["display_name"],
            "points": merge["points"], "solved": len(merge["challenge_ids"]), "elapsed": merge["elapsed"],
            "challenges": [
                {"id": item["id"], "name": item["name"], "difficulty": item["difficulty"],
                 "points": merge["challenge_points"].get(str(item["id"]), 0)}
                for item in chosen if item
            ],
            "sources": merge["sources"],
        })
    rows.sort(key=lambda item: (-item["points"], item["elapsed"], item["name"].lower()))
    for position, row in enumerate(rows, start=1):
        row["position"] = position
    return rows


def edition_feedback_entries(edition_id):
    conn = get_db()
    rows = conn.execute(
        """SELECT f.* FROM edition_feedback ef
           JOIN participant_feedback f ON f.id = ef.feedback_id
           WHERE ef.edition_id = ?
           ORDER BY f.created_at DESC, f.id DESC""",
        (edition_id,),
    ).fetchall()
    conn.close()
    entries = []
    for row in rows:
        entry = dict(row)
        entry["answers"] = {q["field"]: feedback_answers(entry, q) for q in FEEDBACK_QUESTIONS}
        entries.append(entry)
    return entries


def edition_feedback_candidates(edition_id):
    """Todos os feedbacks das rodadas da edição, marcando quais estão incluídos."""
    conn = get_db()
    rows = conn.execute(
        """SELECT f.*, c.code AS ctf_code,
                  EXISTS(SELECT 1 FROM edition_feedback ef
                         WHERE ef.edition_id = ? AND ef.feedback_id = f.id) AS included
           FROM participant_feedback f
           JOIN ctfs c ON c.id = f.ctf_id
           WHERE f.ctf_id IN (SELECT ctf_id FROM edition_ctfs WHERE edition_id = ?)
           ORDER BY f.created_at DESC, f.id DESC""",
        (edition_id, edition_id),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def edition_challenges(edition_id):
    """Desafios usados na edição, sem repetir entre as rodadas."""
    challenges, seen = [], set()
    for ctf_id in edition_ctf_ids(edition_id):
        for challenge in challenges_for_ctf(ctf_id):
            if challenge["id"] not in seen:
                seen.add(challenge["id"])
                challenges.append(challenge)
    challenges.sort(key=lambda item: (DIFFICULTY_ORDER.index(item["difficulty"]), item["id"]))
    return challenges


def sync_edition_sources(edition_id, ctf_ids):
    """Casa participantes e feedbacks da edição com as rodadas escolhidas.

    Mantém o que o admin já ajustou (nome de exibição, inclusão) e só adiciona
    o que entrou ou remove o que saiu junto com a rodada.
    """
    conn = get_db()
    conn.execute("DELETE FROM edition_ctfs WHERE edition_id = ?", (edition_id,))
    conn.executemany(
        "INSERT INTO edition_ctfs (edition_id, ctf_id) VALUES (?, ?)",
        [(edition_id, ctf_id) for ctf_id in ctf_ids],
    )
    if ctf_ids:
        placeholders = ",".join("?" * len(ctf_ids))
        conn.execute(
            f"""DELETE FROM edition_participants WHERE edition_id = ? AND participant_id NOT IN
                (SELECT id FROM participants WHERE ctf_id IN ({placeholders}))""",
            (edition_id, *ctf_ids),
        )
        conn.execute(
            f"""DELETE FROM edition_feedback WHERE edition_id = ? AND feedback_id NOT IN
                (SELECT id FROM participant_feedback WHERE ctf_id IN ({placeholders}))""",
            (edition_id, *ctf_ids),
        )
        conn.execute(
            f"""INSERT OR IGNORE INTO edition_participants (edition_id, participant_id, display_name)
                SELECT ?, id, name FROM participants WHERE ctf_id IN ({placeholders})""",
            (edition_id, *ctf_ids),
        )
        conn.execute(
            f"""INSERT OR IGNORE INTO edition_feedback (edition_id, feedback_id)
                SELECT ?, id FROM participant_feedback WHERE ctf_id IN ({placeholders})""",
            (edition_id, *ctf_ids),
        )
    else:
        conn.execute("DELETE FROM edition_participants WHERE edition_id = ?", (edition_id,))
        conn.execute("DELETE FROM edition_feedback WHERE edition_id = ?", (edition_id,))
    conn.commit()
    conn.close()


def published_editions():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM editions WHERE status = 'publicada' ORDER BY published_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


SCHEDULED_TITLE_MAX = 70
SCHEDULED_LOCATION_MAX = 90
SCHEDULED_DETAILS_MAX = 220


def scheduled_event_rows():
    conn = get_db()
    rows = conn.execute("SELECT * FROM scheduled_events ORDER BY starts_at ASC, id ASC").fetchall()
    conn.close()
    now = timestamp_now()
    events = []
    for row in rows:
        event = dict(row)
        event["local_starts_at"] = utc_to_local(event["starts_at"])
        event["local_ends_at"] = utc_to_local(event["ends_at"])
        event["local_banner_starts_at"] = utc_to_local(event["banner_starts_at"])
        event["local_banner_ends_at"] = utc_to_local(event["banner_ends_at"])
        event["banner_live"] = event["banner_starts_at"] <= now <= event["banner_ends_at"]
        event["banner_waiting"] = now < event["banner_starts_at"]
        event["banner_expired"] = now > event["banner_ends_at"]
        events.append(event)
    return events


def active_announcement():
    """Agendamento cujo banner está dentro da janela configurada, se houver."""
    now = timestamp_now()
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM scheduled_events
           WHERE banner_starts_at <= ? AND banner_ends_at >= ?
           ORDER BY starts_at ASC, id ASC LIMIT 1""",
        (now, now),
    ).fetchone()
    conn.close()
    if not row:
        return None
    event = dict(row)
    event["local_starts_at"] = utc_to_local(event["starts_at"])
    event["local_ends_at"] = utc_to_local(event["ends_at"])
    return event


def clean_scheduled_event(form):
    """Valida o formulário da agenda. Retorna (dados, erro)."""
    title = " ".join((form.get("title") or "").split())
    if not title:
        return None, "Informe o nome do evento."
    if len(title) > SCHEDULED_TITLE_MAX:
        return None, f"O nome do evento deve ter no máximo {SCHEDULED_TITLE_MAX} caracteres."

    starts_at = local_to_utc(form.get("event_date"), form.get("event_time"))
    if not starts_at:
        return None, "Informe uma data válida para o evento."
    ends_at = local_to_utc(form.get("event_date"), form.get("event_end_time")) if (form.get("event_end_time") or "").strip() else None
    if ends_at and ends_at <= starts_at:
        return None, "O horário de término do evento deve ser depois do horário de início."

    banner_starts_at = local_to_utc(form.get("banner_start_date"), form.get("banner_start_time"), fallback_time="00:00")
    banner_ends_at = local_to_utc(form.get("banner_end_date"), form.get("banner_end_time"), fallback_time="23:59")
    if not banner_starts_at or not banner_ends_at:
        return None, "Informe o período em que o banner deve aparecer na página inicial."
    if banner_ends_at <= banner_starts_at:
        return None, "O fim da exibição do banner deve ser depois do início."

    # Só http(s): um "javascript:" colado aqui viraria um link executável na
    # página pública.
    signup_url = (form.get("signup_url") or "").strip()
    if signup_url and urlparse(signup_url).scheme not in ("http", "https"):
        return None, "O link de inscrição deve começar com http:// ou https://."

    return {
        "title": title,
        "signup_url": signup_url[:500] or None,
        "location": " ".join((form.get("location") or "").split())[:SCHEDULED_LOCATION_MAX] or None,
        "details": " ".join((form.get("details") or "").split())[:SCHEDULED_DETAILS_MAX] or None,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "banner_starts_at": banner_starts_at,
        "banner_ends_at": banner_ends_at,
    }, None


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
    if "event_points" in challenge:
        score = max(0, challenge["event_points"] - challenge.get("event_hint_penalty", 0) * hints_used)
        if hints_used > 0:
            return max(1, score)
        return score
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


DIFFICULTY_ORDER = ["Fácil", "Médio", "Difícil"]


def score_breakdown(participant_id):
    """Per-difficulty score summary used by the score-breakdown modal.

    Always relative to the specific 1,000-point event the participant played,
    since the same difficulty can be worth different base points across events
    depending on the composition the admin chose (see normalize_event_scores).
    """
    conn = get_db()
    participant = conn.execute(
        "SELECT id, name, ctf_id FROM participants WHERE id = ?", (participant_id,)
    ).fetchone()
    if not participant:
        conn.close()
        return None
    rows = conn.execute(
        "SELECT challenge_id, status, hints_used, score_earned FROM participant_challenges WHERE participant_id = ?",
        (participant_id,),
    ).fetchall()
    conn.close()

    event_challenges = {item["id"]: item for item in challenges_for_ctf(participant["ctf_id"])}
    buckets = {
        difficulty: {"label": difficulty, "solved": 0, "total": 0, "earned": 0, "max": 0, "hint_penalty": 0}
        for difficulty in DIFFICULTY_ORDER
    }
    for challenge in event_challenges.values():
        difficulty = challenge["difficulty"] if challenge["difficulty"] in buckets else "Difícil"
        buckets[difficulty]["total"] += 1
        buckets[difficulty]["max"] += challenge.get("event_points", challenge["points"])

    hints_used_total = 0
    for row in rows:
        challenge = event_challenges.get(row["challenge_id"])
        if not challenge:
            continue
        difficulty = challenge["difficulty"] if challenge["difficulty"] in buckets else "Difícil"
        hints_used_total += row["hints_used"] or 0
        if row["status"] == "solved":
            max_points = challenge.get("event_points", challenge["points"])
            earned = row["score_earned"] or 0
            buckets[difficulty]["solved"] += 1
            buckets[difficulty]["earned"] += earned
            buckets[difficulty]["hint_penalty"] += max(0, max_points - earned)

    total_earned = sum(bucket["earned"] for bucket in buckets.values())
    total_max = sum(bucket["max"] for bucket in buckets.values())
    return {
        "id": participant["id"],
        "name": participant["name"],
        "by_difficulty": [buckets[difficulty] for difficulty in DIFFICULTY_ORDER],
        "total_earned": total_earned,
        "total_max": total_max,
        "hints_used": hints_used_total,
    }


# Solução guiada de cada mecanismo, só para a tela de administração. Cada passo
# usa {root} = /lab/<id>. Para os 8 laboratórios originais (endpoints próprios)
# há sobrescritas por id em _WALKTHROUGH_OVERRIDES.
_WALKTHROUGH_BY_MECHANISM = {
    # --- Lista 1 ---
    "source": {"tool": "Codigo-fonte da pagina (Ctrl+U)", "where": "Comentario HTML oculto na pagina inicial.",
        "steps": ["Abra {root}.", "Veja o codigo-fonte da pagina (Ctrl+U).", "Procure por um comentario HTML (<!-- ... -->): a flag esta nele."]},
    "sitemap": {"tool": "Navegador (sitemap XML)", "where": "Rota auxiliar listada no mapa do site.",
        "steps": ["Abra o site e encontre o link para o mapa do portal.", "No sitemap, localize a URL auxiliar.", "Acesse essa rota; a flag esta no conteudo."]},
    "base64": {"tool": "Decodificador Base64 (`base64 -d` ou CyberChef)", "where": "Token codificado exibido na propria pagina.",
        "steps": ["Abra {root} e localize o token em destaque.", "Decodifique de Base64 (`echo '<token>' | base64 -d`).", "O texto decodificado e a flag."]},
    "js": {"tool": "DevTools -> Console/Sources", "where": "Variavel global no JavaScript da pagina.",
        "steps": ["Abra {root} e o DevTools (F12).", "No Console, digite a constante exposta no script.", "O valor retornado e a flag."]},
    "header": {"tool": "`curl -i` ou DevTools -> Network", "where": "Cabecalho de resposta X-Campus-Notice.",
        "steps": ["Faca uma requisicao a {root} (`curl -i http://<host>{root}`).", "Leia os cabecalhos da resposta.", "A flag esta no cabecalho 'X-Campus-Notice'."]},
    "idor": {"tool": "`curl` (ou Burp) - o DevTools nao adiciona cabecalhos a uma requisicao", "where": "Registro 701 autorizado pelo cabecalho vindo do 700.",
        "steps": ["Requisite {root}/api/record/700 e anote o cabecalho 'X-Lab-Delegation'.", "Requisite {root}/api/record/701 incluindo-o (`curl -H 'X-Lab-Delegation: <valor>' http://<host>{root}/api/record/701`).", "A flag vem no campo 'reference'."]},
    "search": {"tool": "Formulario de busca ou `curl`", "where": "Resposta da busca com tautologia que burla o filtro.",
        "steps": ["Use a busca de {root} e observe a requisicao a {root}/api/search?q=...", "Reenvie com uma tautologia real: {root}/api/search?q=' OR '1'='1", "O registro restrito aparece com a flag no campo 'nota'."]},
    "redirect": {"tool": "`curl` (sem Burp) - repita uma etapa com um cabecalho novo", "where": "Cabecalho X-Delivery-Receipt no 2o salto, so com o token de /start.",
        "steps": [
            "No DevTools -> Network, botao direito na requisicao de {root}/delivery/start -> 'Copy as cURL' (inclui o cookie da sessao).",
            "Rode esse comando; a resposta 302 traz o cabecalho 'X-Delivery-Token'.",
            "Repita em {root}/delivery/processing com `-H 'X-Delivery-Token: <valor>'`; so assim vem 'X-Delivery-Receipt' com a flag.",
        ]},

    # --- Lista 2 ---
    "caesar": {"tool": "Decodificador de cifra de Cesar (ou papel)", "where": "Endereco da festa cifrado na pagina 'Como chegar'; o deslocamento esta escrito na propria pagina.",
        "steps": ["Navegue pelo site da festa ate a secao do endereco/como chegar.", "O endereco aparece embaralhado, e a pagina diz quantas casas o alfabeto girou.", "Gire cada letra de volta esse tanto (ex.: CyberChef -> ROT, ou a mao). O endereco decifrado e a flag."]},
    "backup": {"tool": "Navegador (Network) ou `curl`", "where": "Copia .bak do catalogo em JSON que a pagina carrega.",
        "steps": ["No {root}, a pagina de catalogo carrega os itens de um JSON — veja {root}/catalogo.json na aba Network.", "O codigo da pagina comenta que o backup de cada arquivo recebe o sufixo .bak.", "Peca a copia: `curl http://<host>{root}/catalogo.json.bak`. O backup traz um campo interno com a flag."]},
    "cookie": {"tool": "`curl -i` (ou DevTools -> Application -> Cookies)", "where": "Cookie 'preferencia_padaria' gravado na resposta da pagina inicial.",
        "steps": ["Requisite a home: `curl -i http://<host>{root}`.", "Leia o cabecalho 'Set-Cookie' da resposta.", "O valor de 'preferencia_padaria' e a flag (nao aparece na tela)."]},
    "svg": {"tool": "Navegador ou `curl`", "where": "Comentario dentro de um dos SVGs da galeria.",
        "steps": ["A galeria mostra varias ilustracoes; todas sao arquivos .svg (vetor = texto).", "Abra cada SVG pela URL (ex.: `curl http://<host>{root}/assets/cobre.svg`) e leia o codigo.", "Uma das artes tem um comentario <!-- ... --> com a assinatura da artista: essa e a flag."]},
    "debug": {"tool": "`curl` ou barra de endereco", "where": "Campo interno da resposta de rastreio, so com o modo de diagnostico ligado.",
        "steps": ["O rastreio consulta {root}/rastreio. Um comentario esquecido no codigo da pagina cita um parametro interno de diagnostico.", "Chame `curl 'http://<host>{root}/rastreio?debug=1'`.", "A resposta ganha o bloco 'interno' com 'chave_operacao' — a flag."]},
    "login_sqli": {"tool": "Formulario de login ou `curl`", "where": "Bypass de autenticacao por SQL injection no login.",
        "steps": ["A consulta e: SELECT ... WHERE usuario='<u>' AND senha='<p>' (concatenada).", "No usuario, feche a aspa e torne a condicao sempre verdadeira, comentando o resto: `' OR '1'='1' --`. Senha: qualquer coisa.", "Ex.: `curl -d \"user=' OR '1'='1' --&password=x\" http://<host>{root}/entrar`. A resposta logada traz 'mural_interno' com a flag."]},
    "token": {"tool": "`curl` + Base64 (ou DevTools -> Application -> Cookies)", "where": "Cookie 'cracha' em Base64 com o campo papel.",
        "steps": [
            "Pegue o cookie: `curl -i http://<host>{root}` -> copie o valor de 'cracha'.",
            "Decodifique: `echo '<cracha>' | base64 -d` -> algo como 'uid=8821|nome=Visitante|papel=visitante'.",
            "Troque papel=visitante por papel=admin e recodifique: `echo -n 'uid=8821|nome=Visitante|papel=admin' | base64`.",
            "Reenvie com o cookie forjado: `curl -b 'cracha=<novo-base64>' http://<host>{root}/restrito`. A resposta traz 'chave_mestra' com a flag.",
        ]},
    "recovery": {"tool": "`curl` + Base64 (sem Burp)", "where": "Token de recuperacao deduzivel do e-mail publico do usuario.",
        "steps": [
            "O {root}/robots.txt revela uma rota fora da navegacao: {root}/interno/gerador-token.",
            "Essa rota explica o algoritmo: token = base64(email do usuario).",
            "Os e-mails estao na pagina de equipe ({root}/equipe.json). Monte o token do alvo: `echo -n 'ana.prado@central.local' | base64`.",
            "Chame `curl 'http://<host>{root}/redefinir?user=ana.prado@central.local&token=<base64>'`. A resposta traz 'codigo_confirmacao' com a flag.",
        ]},
}
_WALKTHROUGH_OVERRIDES = {
    2: {"tool": "Navegador (sitemap XML)", "where": "Mapa do site do portal → página auxiliar de relatório.",
        "steps": ["Abra Guias de viagem no site Wayfarer e clique em Mapa do site do portal.", "No sitemap XML, localize a URL da página auxiliar.", "Acesse /lab/2/files/report; a flag está no conteúdo da página."]},
    6: {"tool": "Burp Suite (ou `curl`) — o DevTools não permite adicionar cabeçalhos a uma requisição", "where": "Perfil 102 autorizado pelo cabeçalho vindo do perfil 101.",
        "steps": ["Requisite /lab/6/profile/101 e anote o cabeçalho 'X-Workspace-Access'.", "Requisite /lab/6/profile/102 incluindo esse cabeçalho.", "A flag vem no campo 'note'."]},
    7: {"tool": "DevTools → Network ou Burp Suite (manipular o parâmetro de busca)", "where": "Resposta da busca com uma tautologia que burla o filtro de eventos públicos.",
        "steps": ["Use a busca de /lab/7 e observe /lab/7/search?q=...", "Reenvie com um payload de tautologia real, ex.: /lab/7/search?q=' OR '1'='1", "O evento restrito da Night Owl aparece junto dos demais, com a flag no campo 'nota'."]},
}


def challenge_walkthrough(challenge):
    """Solução passo a passo de um desafio, para a tela de administração."""
    guide = _WALKTHROUGH_OVERRIDES.get(challenge["id"]) or _WALKTHROUGH_BY_MECHANISM.get(
        challenge["mechanism"],
        {"tool": "DevTools", "where": "Investigue o comportamento técnico do laboratório.", "steps": ["Abra {root}.", "Analise requisições, código e cabeçalhos.", "A flag aparece no recurso técnico do laboratório."]},
    )
    root = f"/lab/{challenge['id']}"
    return {
        "tool": guide["tool"],
        "where": guide["where"],
        "steps": [step.format(root=root) for step in guide["steps"]],
        "root": root,
    }


# Discreet line-art eye icon (matches the site's plain, monochrome icon
# glyphs like the panel's ⌖ reset button) used everywhere a "ver detalhes"
# action needs an icon, instead of a colorful emoji.
EYE_ICON_SVG = (
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
    'focusable="false"><path d="M1.5 12S5.5 5 12 5s10.5 7 10.5 7-4 7-10.5 7S1.5 12 1.5 12Z"/>'
    '<circle cx="12" cy="12" r="3"/></svg>'
)


# --- Ambiente de teste do administrador (sandbox do gabarito) ---------------
# O administrador pode "jogar" todos os desafios de uma lista exatamente como um
# participante, usando a mesma tela e os mesmos laboratórios. O progresso fica
# só na sessão do admin (não cria CTF, não entra em ranking). Sandbox e CTF real
# são mutuamente exclusivos: não se abre a sandbox com um CTF ativo, e não se
# inicia um CTF enquanto a sandbox está aberta nesta sessão.
def admin_sandbox():
    if not session.get("admin_logged_in"):
        return None
    return session.get("admin_sandbox")


def sandbox_record(sandbox, challenge_id):
    key = str(challenge_id)
    record = sandbox["progress"].get(key)
    if record is None:
        record = {"hints_used": 0, "status": "open", "score": 0}
        sandbox["progress"][key] = record
        session.modified = True
    return record


def sandbox_challenge(challenge_id, mechanism=None):
    sandbox = admin_sandbox()
    if not sandbox or challenge_id not in sandbox.get("challenge_ids", []):
        return None
    challenge = CHALLENGE_BY_ID.get(challenge_id)
    if not challenge or (mechanism and challenge.get("mechanism") != mechanism):
        return None
    return challenge


def training_list_ids():
    conn = get_db()
    rows = conn.execute("SELECT list_id FROM training_lists").fetchall()
    conn.close()
    return {row["list_id"] for row in rows}


def training_challenges(list_id):
    """Desafios de uma lista liberada para treino, em ordem de dificuldade."""
    if list_id not in training_list_ids():
        return []
    challenges = []
    for difficulty in DIFFICULTY_ORDER:
        challenges.extend(sorted(challenge_pool(list_id, difficulty), key=lambda item: item["code"]))
    return challenges


def training_challenge(challenge_id, mechanism=None):
    challenge = CHALLENGE_BY_ID.get(challenge_id)
    if not challenge or (mechanism and challenge.get("mechanism") != mechanism):
        return None
    enabled = training_list_ids()
    for list_id in enabled:
        if any(item["id"] == challenge_id for item in challenge_pool(list_id, challenge["difficulty"])):
            return challenge
    return None


def open_challenge(challenge_id, mechanism=None):
    """Desafio aberto ao público: treino livre ou edição com gabarito liberado.

    Quando o admin publica os gabaritos de uma edição a flag já é pública, então
    deixar o laboratório aberto para visitar não esconde mais nada — e é o que
    permite "tentar antes de ver a resposta".
    """
    challenge = training_challenge(challenge_id, mechanism)
    if challenge:
        return challenge
    candidate = CHALLENGE_BY_ID.get(challenge_id)
    if not candidate or (mechanism and candidate.get("mechanism") != mechanism):
        return None
    conn = get_db()
    row = conn.execute(
        """SELECT 1 FROM editions e
           JOIN edition_ctfs ec ON ec.edition_id = e.id
           JOIN ctf_challenges cc ON cc.ctf_id = ec.ctf_id
           WHERE e.status = 'publicada' AND e.show_challenges = 1 AND cc.challenge_id = ?
           LIMIT 1""",
        (challenge_id,),
    ).fetchone()
    conn.close()
    return candidate if row else None


def playable_challenge(challenge_id, mechanism=None):
    """Desafio jogável agora: sandbox do admin, CTF ativo ou acesso público."""
    challenge = sandbox_challenge(challenge_id, mechanism)
    if challenge:
        return challenge
    ctf = current_ctf()
    challenge = challenge_for_ctf(ctf["id"], challenge_id) if ctf else None
    if challenge and (not mechanism or challenge.get("mechanism") == mechanism):
        return challenge
    return open_challenge(challenge_id, mechanism)


# Detecta um bypass de SQLi por tautologia de verdade: precisa de uma aspa
# fechando um literal, seguida de OR/|| e de uma comparação sempre verdadeira
# (string=string, número=número ou TRUE), opcionalmente encerrada por um
# marcador de comentário. Isso rejeita buscas que só contenham "or" como
# palavra comum (ex.: "jazz or blues") e exige a forma real de um payload de
# tautologia, em vez do antigo "'" in query and "or" in query.lower()`.
_SQLI_TAUTOLOGY_RE = re.compile(
    r"""['"]\s*(?:or|\|\|)\s*(?:'[^']*'\s*=\s*'[^']*'?|"[^"]*"\s*=\s*"[^"]*"?|\d+\s*=\s*\d+|true)\s*(?:--|#|;|['"])?""",
    re.IGNORECASE,
)


def sql_injection_bypasses_filter(query):
    return bool(_SQLI_TAUTOLOGY_RE.search(query or ""))


# Arquivo de eventos da Night Owl (desafio 7): os registros públicos batem com
# as sugestões de busca já mostradas na página ("música", "cinema", "galeria")
# e o registro restrito só aparece de verdade quando o filtro é burlado.
NIGHT_OWL_ARCHIVE = [
    {"title": "Noite de jazz no Porão 7", "local": "Porão 7", "public": True},
    {"title": "Cinema ao relento: clássicos de verão", "local": "Praça das Artes", "public": True},
    {"title": "Vernissage coletiva de fotografia", "local": "Galeria Lumen", "public": True},
    {"title": "Reunião de prestação de contas com patrocinadores", "local": "Arquivo do campus", "public": False},
]

# Mesma lógica para os desafios genéricos do catálogo que usam o mecanismo
# "search" (sem o tema específico da Night Owl).
CATALOG_SEARCH_ARCHIVE = [
    {"title": "Guia de primeiros passos", "categoria": "Documentação pública", "public": True},
    {"title": "Registro de manutenção preventiva", "categoria": "Operações", "public": True},
    {"title": "Ata de auditoria interna", "categoria": "Restrito", "public": False},
]


def run_mock_search(dataset, query, flag):
    if sql_injection_bypasses_filter(query):
        records = dataset
    else:
        needle = (query or "").strip().lower()
        if not needle:
            return []
        records = [record for record in dataset if record["public"] and needle in record["title"].lower()]
    results = []
    for record in records:
        entry = {key: value for key, value in record.items() if key != "public"}
        if not record["public"]:
            entry["nota"] = f"Registro de uso interno — {flag}"
        results.append(entry)
    return results


def make_app_config():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "jacitec-secret")
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.globals["current_ctf"] = current_ctf
    app.jinja_env.globals["challenge_list"] = CHALLENGES
    app.jinja_env.globals["eye_icon_svg"] = EYE_ICON_SVG
    app.jinja_env.globals["app_version"] = APP_VERSION
    app.jinja_env.filters["b64encode"] = lambda value: base64.b64encode(value.encode("utf-8")).decode("ascii")
    return app


def create_app(testing=False):
    app = make_app_config()
    init_db()

    @app.before_request
    def guard_lab_routes_after_ctf_end():
        if not request.path.startswith("/lab/"):
            return None
        # O admin no ambiente de teste acessa os laboratórios; cada rota /lab
        # valida o acesso via playable_challenge.
        if admin_sandbox():
            return None
        # Laboratórios liberados para treino são públicos: cada rota /lab ainda
        # valida o acesso via playable_challenge. O id vem do caminho porque
        # algumas rotas (ex.: /lab/7/search) fixam o desafio na própria URL.
        path_match = re.match(r"/lab/(\d+)", request.path)
        if path_match and open_challenge(int(path_match.group(1))):
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
        return render_template("index.html", ctf=ctf, announcement=active_announcement())

    @app.get("/inicio")
    def ctf_home():
        session.pop("participant_id", None)
        session.pop("participant_name", None)
        return render_template("index.html", ctf=current_ctf(), announcement=active_announcement())

    @app.get("/participar")
    def participation_page():
        return render_template("participate.html", ctf=current_ctf())

    @app.get("/regras")
    def rules_page():
        return render_template("rules.html")

    @app.get("/lab/2/sitemap.xml")
    def lab_sitemap():
        if not playable_challenge(2, "sitemap"):
            return redirect(lab_redirect_target())
        report_url = request.url_root.rstrip("/") + url_for(
            "lab_subpage", challenge_id=2, page="files/report"
        )
        sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{report_url}</loc></url>"
            "</urlset>"
        )
        return sitemap, 200, {"Content-Type": "application/xml; charset=utf-8"}

    @app.get("/lab/<int:challenge_id>/robots.txt")
    def catalog_robots(challenge_id):
        challenge = playable_challenge(challenge_id, "robots")
        if not challenge:
            return "", 404
        return f"User-agent: *\nDisallow: /lab/{challenge_id}/operations/audit\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/lab/<int:challenge_id>/operations/audit")
    def catalog_audit(challenge_id):
        challenge = playable_challenge(challenge_id)
        if not challenge:
            return jsonify({"error": "Atividade indisponível"}), 404
        return jsonify({"audit": "laboratório", "reference": challenge["flags"][0]})

    def selected_catalog_challenge(challenge_id, mechanism=None):
        return playable_challenge(challenge_id, mechanism)

    @app.get("/lab/<int:challenge_id>/app.webmanifest")
    def catalog_manifest(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "manifest")
        if not challenge:
            return jsonify({"error": "Recurso indisponível"}), 404
        return jsonify({"name": "JACITEC Lab", "maintenance_note": challenge["flags"][0]})

    @app.get("/lab/<int:challenge_id>/asset-preview")
    def catalog_asset_preview(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "metadata")
        if not challenge:
            return "", 404
        return "preview", 200, {"X-Image-Description": challenge["flags"][0], "Content-Type": "text/plain"}

    @app.get("/lab/<int:challenge_id>/receipt")
    def catalog_receipt(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "receipt")
        if not challenge:
            return "", 404
        return "Recibo de atendimento disponível.", 200, {
            "Content-Type": "text/plain; charset=utf-8",
            "X-Receipt-Note": challenge["flags"][0],
        }

    @app.get("/lab/<int:challenge_id>/api/record/<int:record_id>")
    def catalog_record(challenge_id, record_id):
        challenge = selected_catalog_challenge(challenge_id, "idor")
        if not challenge:
            return jsonify({"error": "Recurso indisponível"}), 404
        if record_id == 700:
            return jsonify({"id": 700, "owner": "participante", "status": "disponível"}), 200, {"X-Lab-Delegation": f"delegate-{challenge_id}"}
        if record_id == 701 and request.headers.get("X-Lab-Delegation") == f"delegate-{challenge_id}":
            return jsonify({"id": 701, "owner": "arquivo de treinamento", "reference": challenge["flags"][0]})
        return jsonify({"error": "Autorização delegada necessária", "required": "X-Lab-Delegation"}), 403

    @app.get("/lab/<int:challenge_id>/api/search")
    def catalog_search(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "search")
        if not challenge:
            return jsonify({"error": "Recurso indisponível"}), 404
        query = request.args.get("q", "")
        results = run_mock_search(CATALOG_SEARCH_ARCHIVE, query, challenge["flags"][0])
        if not results:
            return jsonify({"results": [], "message": "Nenhum resultado para a busca informada."})
        return jsonify({"results": results})

    @app.get("/lab/<int:challenge_id>/operations/ping")
    def catalog_audit_ping(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "audit")
        if not challenge:
            return "", 404
        return jsonify({"status": "ok"}), 200, {"X-Audit-Path": f"/lab/{challenge_id}/operations/audit"}

    # Cadeia de redirecionamento com 3 saltos (start → processing → receipt) e
    # um token repassado manualmente, para que um clique normal (o navegador
    # segue os 302 sozinho, sem reenviar cabeçalhos customizados) nunca exponha
    # a flag, mesmo abrindo o Network: /start só devolve um token no cabeçalho;
    # a flag só sai no cabeçalho de /processing se a requisição a /processing
    # for refeita manualmente (curl/Burp) incluindo esse token — é preciso
    # capturar e repetir a requisição, não só acompanhar a navegação.
    @app.get("/lab/<int:challenge_id>/delivery/start")
    def catalog_delivery_start(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "redirect")
        if not challenge:
            return "", 404
        response = redirect(url_for("catalog_delivery_processing", challenge_id=challenge_id), code=302)
        response.headers["X-Delivery-Stage"] = "1/3 · solicitação registrada"
        response.headers["X-Delivery-Token"] = f"dl-token-{challenge_id}"
        return response

    @app.get("/lab/<int:challenge_id>/delivery/processing")
    def catalog_delivery_processing(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "redirect")
        if not challenge:
            return "", 404
        response = redirect(url_for("catalog_delivery_receipt", challenge_id=challenge_id), code=302)
        response.headers["X-Delivery-Stage"] = "2/3 · em processamento"
        if request.headers.get("X-Delivery-Token") == f"dl-token-{challenge_id}":
            response.headers["X-Delivery-Receipt"] = challenge["flags"][0]
        return response

    @app.get("/lab/<int:challenge_id>/delivery/receipt")
    def catalog_delivery_receipt(challenge_id):
        challenge = selected_catalog_challenge(challenge_id, "redirect")
        if not challenge:
            return "", 404
        return "Entrega concluída.", 200, {"X-Delivery-Stage": "3/3 · concluído"}

    def lab_redirect_target():
        # Para onde mandar quando um laboratório não está acessível no contexto.
        if admin_sandbox():
            return url_for("admin_sandbox_dashboard")
        if not session.get("participant_id"):
            return url_for("index")
        if not current_ctf():
            return url_for("public_ranking_page")
        return url_for("participant_dashboard")

    @app.get("/lab/<int:challenge_id>")
    def lab_page(challenge_id):
        challenge = playable_challenge(challenge_id)
        if not challenge:
            return redirect(lab_redirect_target())
        response = make_response(render_template("lab_site.html", challenge=challenge, ctf=current_ctf(), page="home"))
        if challenge.get("mechanism") == "header":
            response.headers["X-Campus-Notice"] = challenge["flags"][0]
        elif challenge.get("mechanism") == "cookie":
            # A preferência do balcão é gravada num cookie — a flag viaja no
            # cabeçalho Set-Cookie. path=/lab/20 evita que o cookie seja
            # reenviado para os outros laboratórios e confunda quem inspeciona.
            response.set_cookie("preferencia_padaria", challenge["flags"][0], path=f"/lab/{challenge_id}")
        elif challenge.get("mechanism") == "token":
            # O crachá é um cookie em Base64 com o papel do visitante; trocar o
            # papel para admin desbloqueia a área restrita.
            visitor = base64.b64encode(b"uid=8821|nome=Visitante|papel=visitante").decode("ascii")
            response.set_cookie("cracha", visitor, path=f"/lab/{challenge_id}")
        return response

    @app.get("/lab/<int:challenge_id>/<path:page>")
    def lab_subpage(challenge_id, page):
        if challenge_id == 2 and page == "files/report":
            challenge = playable_challenge(2)
            if not challenge:
                return redirect(lab_redirect_target())
            return render_template("lab_site.html", challenge=CHALLENGES[1], ctf=current_ctf(), page=page)
        if challenge_id == 8 and page == "audit-log":
            if not playable_challenge(8):
                return redirect(lab_redirect_target())
            return jsonify({
                "system": "ReservaFácil / exportação de auditoria",
                "entries": [
                    {"event": "reserva.criada", "resource": "sala-reuniao-2"},
                    {"event": "nota_migracao_legada", "reference": CHALLENGES[7]["flags"][0]},
                ],
            })
        challenge = playable_challenge(challenge_id)
        if not challenge:
            return redirect(lab_redirect_target())
        response = make_response(render_template("lab_site.html", challenge=challenge, ctf=current_ctf(), page=page))
        if challenge.get("mechanism") == "header":
            response.headers["X-Campus-Notice"] = challenge["flags"][0]
        return response

    @app.get("/lab/6/profile/<int:profile_id>")
    def lab_profile(profile_id):
        if not playable_challenge(6):
            return jsonify({"error": "Atividade indisponível"}), 404
        profiles = {
            101: {"id": 101, "name": "Ana Souza", "course": "Sistemas de Informação", "public": True},
            102: {"id": 102, "name": "Arquivo de pesquisa", "course": "Laboratório Web", "public": False},
        }
        profile = profiles.get(profile_id)
        if not profile:
            return jsonify({"error": "Perfil não encontrado"}), 404
        response = jsonify(profile)
        if profile_id == 101:
            # A chave só é observável no tráfego HTTP.  O participante precisa
            # usar DevTools/Network, curl ou um repetidor para fazer a requisição
            # autorizada ao recurso de outro perfil.
            response.headers["X-Workspace-Access"] = "cv-training-06"
        elif request.headers.get("X-Workspace-Access") == "cv-training-06":
            profile["note"] = CHALLENGE_BY_ID[6]["flags"][0]
            response = jsonify(profile)
        else:
            return jsonify({"error": "Acesso adicional necessário", "required": "X-Workspace-Access"}), 403
        return response

    @app.get("/lab/7/search")
    def lab_search():
        if not playable_challenge(7):
            return jsonify({"error": "Atividade indisponível"}), 404
        query = request.args.get("q", "")
        results = run_mock_search(NIGHT_OWL_ARCHIVE, query, CHALLENGES[6]["flags"][0])
        if not results:
            return jsonify({"results": [], "message": "Nenhum evento encontrado no arquivo."})
        return jsonify({"results": results})



    # ----- Lista 2 (CTF 2) -----

    # 19 backup: o catalogo publico e carregado por JS; a copia .bak (convencao
    # citada num comentario no codigo) guarda um rascunho interno.
    _MARCENARIA_ITENS = [
        {"sku": "CE-18", "nome": "Mesa de jantar Cedro", "madeira": "Cedro", "preco": 2480},
        {"sku": "CA-07", "nome": "Estante Carvalho", "madeira": "Carvalho", "preco": 1890},
        {"sku": "FR-02", "nome": "Banco Freijo", "madeira": "Freijo", "preco": 640},
        {"sku": "IM-11", "nome": "Aparador Imbuia", "madeira": "Imbuia", "preco": 1320},
    ]

    @app.get("/lab/19/catalogo.json")
    def lab19_catalogo():
        if not playable_challenge(19):
            return jsonify({"error": "Indisponivel"}), 404
        return jsonify({"oficina": "Marcenaria Raiz", "atualizado": "2026-02-10", "itens": _MARCENARIA_ITENS})

    @app.get("/lab/19/catalogo.json.bak")
    def lab19_catalogo_bak():
        if not playable_challenge(19):
            return jsonify({"error": "Indisponivel"}), 404
        return jsonify({"oficina": "Marcenaria Raiz", "atualizado": "2026-02-09",
                        "itens": _MARCENARIA_ITENS,
                        "_nota_marceneiro": CHALLENGE_BY_ID[19]["flags"][0]})

    # 21 svg: galeria com varias ilustracoes vetoriais; uma delas esconde a
    # assinatura da artista (a flag) entre as formas.
    _ATELIE_ARTES = [
        ("alvorada", "#f6b45f", "Alvorada", False),
        ("mare", "#5fd3ff", "Maré", False),
        ("bosque", "#6fcf7f", "Bosque", False),
        ("cobre", "#e07a5f", "Cobre", True),
        ("violeta", "#c879ff", "Violeta", False),
        ("carvao", "#8a94a6", "Carvão", False),
    ]

    @app.get("/lab/21/assets/<name>.svg")
    def lab21_art(name):
        if not playable_challenge(21):
            return "", 404
        art = next((a for a in _ATELIE_ARTES if a[0] == name), None)
        if not art:
            return "", 404
        _, color, title, has_flag = art
        signature = f"<!-- {CHALLENGE_BY_ID[21]['flags'][0]} -->" if has_flag else "<!-- Ateliê Lumen -->"
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 220'>"
            f"<rect width='300' height='220' fill='#11121a'/>"
            f"<circle cx='150' cy='110' r='70' fill='{color}' opacity='0.85'/>"
            f"<path d='M40 180 Q150 60 260 180' stroke='{color}' stroke-width='6' fill='none'/>"
            f"<text x='20' y='34' fill='#e8ecf3' font-size='18' font-family='sans-serif'>{title}</text>"
            f"{signature}"
            "</svg>"
        )
        return svg, 200, {"Content-Type": "image/svg+xml; charset=utf-8"}

    # 22 debug: o painel de rastreio tem um modo interno (descoberto por um
    # comentario esquecido no codigo da pagina).
    @app.get("/lab/22/rastreio")
    def lab22_rastreio():
        if not playable_challenge(22):
            return jsonify({"error": "Indisponivel"}), 404
        base = {"codigo": "RL-20268841", "status": "em transito", "etapas": [
            {"em": "2026-02-08 09:12", "evento": "Objeto postado"},
            {"em": "2026-02-09 14:40", "evento": "Em trânsito para o centro de distribuição"},
        ]}
        if request.args.get("debug") == "1":
            base["interno"] = {"no": "cd-sudeste-3", "build": "2026.2", "chave_operacao": CHALLENGE_BY_ID[22]["flags"][0]}
        return jsonify(base)

    # 23 login_sqli: login de verdade. A consulta e montada concatenando a
    # entrada e executada num banco em memoria (dados ficticios e isolados),
    # entao uma injecao real derruba a autenticacao e credenciais erradas
    # ou campos vazios falham naturalmente, com mensagens proprias.
    @app.post("/lab/23/entrar")
    @app.get("/lab/23/entrar")
    def lab23_entrar():
        if not playable_challenge(23):
            return jsonify({"error": "Indisponivel"}), 404
        source = request.form if request.method == "POST" else request.args
        user = (source.get("user") or "").strip()
        password = source.get("password") or ""
        if not user or not password:
            return jsonify({"ok": False, "erro": "Preencha usuário e senha."}), 400
        mem = sqlite3.connect(":memory:")
        mem.execute("CREATE TABLE operadores (usuario TEXT, senha TEXT, setor TEXT)")
        mem.executemany("INSERT INTO operadores VALUES (?,?,?)", [
            ("mariana", "cafe-2024", "atendimento"),
            ("joel", "balcao!77", "estoque"),
        ])
        # Consulta vulnavel de proposito (concatena a entrada sem tratar aspas).
        query = f"SELECT usuario, setor FROM operadores WHERE usuario = '{user}' AND senha = '{password}'"
        try:
            row = mem.execute(query).fetchone()
        except sqlite3.Error:
            mem.close()
            return jsonify({"ok": False, "erro": "Erro ao validar o acesso. Tente novamente."}), 400
        mem.close()
        if not row:
            return jsonify({"ok": False, "erro": "Usuário ou senha inválidos."}), 401
        return jsonify({"ok": True, "operador": row[0], "setor": row[1],
                        "mural_interno": CHALLENGE_BY_ID[23]["flags"][0]})

    # 24 token: o cracha e um cookie Base64 com o papel do visitante.
    @app.get("/lab/24/restrito")
    def lab24_restrito():
        if not playable_challenge(24):
            return jsonify({"error": "Indisponivel"}), 404
        raw = request.cookies.get("cracha", "")
        try:
            decoded = base64.b64decode(raw).decode("utf-8", "ignore")
        except Exception:
            decoded = ""
        campos = dict(part.split("=", 1) for part in decoded.split("|") if "=" in part)
        if campos.get("papel") == "admin":
            return jsonify({"acesso": "administrador", "painel": "Reservas e chaves mestras",
                            "chave_mestra": CHALLENGE_BY_ID[24]["flags"][0]})
        return jsonify({"acesso": campos.get("papel", "desconhecido"),
                        "aviso": "Esta área é exclusiva da administração do prédio."})

    # 25 recovery (dificil, sem Burp): o token de recuperacao e deduzivel de um
    # dado publico do usuario. A rota de diagnostico fica fora da navegacao
    # (aparece so no robots.txt); os e-mails vem da pagina de equipe.
    @app.get("/lab/25/robots.txt")
    def lab25_robots():
        if not playable_challenge(25):
            return "", 404
        body = "User-agent: *\nDisallow: /lab/25/interno/gerador-token\n"
        return body, 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/lab/25/equipe.json")
    def lab25_equipe():
        if not playable_challenge(25):
            return jsonify({"error": "Indisponivel"}), 404
        return jsonify({"equipe": [
            {"nome": "Ana Prado", "cargo": "Coordenação", "email": "ana.prado@central.local"},
            {"nome": "Beto Lima", "cargo": "Suporte", "email": "beto.lima@central.local"},
        ]})

    @app.get("/lab/25/interno/gerador-token")
    def lab25_gerador():
        if not playable_challenge(25):
            return jsonify({"error": "Indisponivel"}), 404
        return jsonify({
            "servico": "gerador de token de recuperação (interno)",
            "algoritmo": "token = base64(email_do_usuario)",
            "endpoint": "/lab/25/redefinir?user=<email>&token=<token>",
        })

    @app.get("/lab/25/redefinir")
    def lab25_redefinir():
        if not playable_challenge(25):
            return jsonify({"error": "Indisponivel"}), 404
        user = request.args.get("user", "")
        token = request.args.get("token", "")
        expected = base64.b64encode(user.encode("utf-8")).decode("ascii") if user else None
        if user and token and token == expected:
            return jsonify({"ok": True, "mensagem": f"Senha de {user} redefinida.",
                            "codigo_confirmacao": CHALLENGE_BY_ID[25]["flags"][0]})
        return jsonify({"ok": False, "erro": "Token inválido para este usuário."}), 403

    @app.post("/join")
    def join_ctf():
        ctf = current_ctf()
        if not ctf:
            return render_template("participate.html", ctf=ctf, error="Nenhum CTF está ativo no momento. Aguarde o administrador iniciar a competição.")
        name, name_error = validate_participant_name(request.form.get("name"))
        if name_error:
            return render_template("participate.html", error=name_error, ctf=ctf)
        code = (request.form.get("code") or "").strip().upper()
        if ctf["code"] != code:
            return render_template("participate.html", error="Token de entrada inválido.", ctf=ctf)

        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM participants WHERE ctf_id = ? AND LOWER(name) = LOWER(?) AND finished_at IS NULL ORDER BY id DESC LIMIT 1",
            (ctf["id"], name),
        ).fetchone()
        if existing and existing["id"] != session.get("participant_id"):
            conn.close()
            return render_template("participate.html", error="Esse nome já está em uso por um participante ativo neste CTF. Escolha outro nome.", ctf=ctf)
        if existing:
            participant_id = existing["id"]
        else:
            now = timestamp_now()
            cursor = conn.execute(
                "INSERT INTO participants (ctf_id, name, entered_at) VALUES (?, ?, ?)",
                (ctf["id"], name, now),
            )
            participant_id = cursor.lastrowid
            for challenge in challenges_for_ctf(ctf["id"]):
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
            # Evento encerrado (pelo tempo ou pelo admin): o feedback vem antes
            # da classificação para quem ainda não respondeu.
            return redirect(url_for("feedback_page") if finished_participant() else url_for("public_ranking_page"))

        conn = get_db()
        participant = conn.execute(
            "SELECT * FROM participants WHERE id = ?",
            (participant_id,),
        ).fetchone()
        if not participant:
            session.clear()
            return redirect(url_for("index"))
        if participant["ctf_id"] != active_ctf["id"] or participant["finished_at"]:
            return redirect(url_for("feedback_page") if finished_participant() else url_for("public_ranking_page"))
        ctf = conn.execute("SELECT * FROM ctfs WHERE id = ?", (participant["ctf_id"],)).fetchone()
        conn.close()

        challenge_status = []
        rows = []
        conn = get_db()
        event_challenges = challenges_for_ctf(ctf["id"])
        for challenge in event_challenges:
            rec = challenge_record(participant_id, challenge["id"])
            rows.append({
                "challenge": challenge,
                "record": rec,
                "value_after_hints": challenge_points_for_hint(challenge, rec["hints_used"]),
            })
        conn.close()
        stats = get_participant_stats(participant_id)
        active_challenge_id = request.args.get("challenge", default=event_challenges[0]["id"], type=int)
        if active_challenge_id not in {item["id"] for item in event_challenges}:
            active_challenge_id = event_challenges[0]["id"]
        active_challenge = CHALLENGE_BY_ID[active_challenge_id]
        active_index = next(index for index, item in enumerate(event_challenges) if item["id"] == active_challenge_id)
        active_record = next(row["record"] for row in rows if row["challenge"]["id"] == active_challenge_id)
        return render_template(
            "participant_dashboard.html",
            participant=participant,
            ctf=ctf,
            challenges=rows,
            stats=stats,
            active_challenge=active_challenge,
            active_record=active_record,
            active_position=active_index + 1,
            next_challenge=event_challenges[active_index + 1] if active_index + 1 < len(event_challenges) else None,
            remaining_seconds=ctf_remaining_seconds(dict(ctf)),
        )

    @app.get("/api/participant-state")
    def participant_state_api():
        sandbox = admin_sandbox()
        if sandbox:
            challenge_states = []
            total = 0
            solved = 0
            for cid in sandbox["challenge_ids"]:
                record = sandbox_record(sandbox, cid)
                if record["status"] == "solved":
                    total += record["score"]
                    solved += 1
                challenge_states.append({
                    "id": cid,
                    "status": record["status"],
                    "hints_used": record["hints_used"],
                    "score_earned": record["score"],
                })
            return jsonify({
                "status": "ATIVO",
                "points": total,
                "solved": solved,
                "remaining_seconds": None,
                "participant": "Administrador (teste)",
                "entered_at": sandbox["started_at"],
                "challenges": challenge_states,
            })
        participant_id = session.get("participant_id")
        ctf = current_ctf()
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        event = participant_event_summary(participant_id)
        if not event:
            return jsonify({"error": "Participação não encontrada"}), 404
        if not ctf or event["ctf_id"] != ctf["id"] or event["participant_finished"]:
            return jsonify({
                "status": "FINALIZADO",
                "code": event["code"],
                "ranking_url": url_for("ctf_archive_page", ctf_id=event["ctf_id"]),
                "home_url": url_for("ctf_home"),
                "feedback_url": url_for("feedback_page") if finished_participant() else None,
            }), 409

        conn = get_db()
        participant = conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,)).fetchone()
        conn.close()

        stats = get_participant_stats(participant_id)
        challenge_states = []
        for challenge in challenges_for_ctf(ctf["id"]):
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
        sandbox = admin_sandbox()
        if sandbox:
            challenge = sandbox_challenge(challenge_id)
            if not challenge:
                return jsonify({"error": "Desafio não encontrado"}), 404
            record = sandbox_record(sandbox, challenge_id)
            if record["status"] == "solved":
                return jsonify({"error": "Desafio já resolvido"}), 409
            hints_used = min(record["hints_used"] + 1, len(challenge["hints"]))
            record["hints_used"] = hints_used
            session.modified = True
            return jsonify({
                "hints_used": hints_used,
                "hint": challenge["hints"][hints_used - 1],
                "points_if_solved": challenge_points_for_hint(challenge, hints_used),
            })
        participant_id = session.get("participant_id")
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        if not participant_is_active(participant_id):
            event = participant_event_summary(participant_id)
            if not event:
                return jsonify({"error": "Participação não encontrada"}), 404
            return jsonify({"status": "FINALIZADO", "code": event["code"], "ranking_url": url_for("ctf_archive_page", ctf_id=event["ctf_id"]), "home_url": url_for("ctf_home"), "feedback_url": url_for("feedback_page") if finished_participant() else None}), 409
        ctf = current_ctf()
        challenge = challenge_for_ctf(ctf["id"], challenge_id) if ctf else None
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

    @app.get("/api/challenge/<int:challenge_id>/revealed-hints")
    def revealed_challenge_hints(challenge_id):
        # Devolve apenas as dicas que o participante já pagou. As dicas não
        # reveladas nunca são enviadas ao cliente, então não dá para lê-las no
        # HTML/JS sem gastar pontos.
        sandbox = admin_sandbox()
        if sandbox:
            challenge = sandbox_challenge(challenge_id)
            if not challenge:
                return jsonify({"error": "Desafio não encontrado"}), 404
            record = sandbox_record(sandbox, challenge_id)
            hints_used = min(record["hints_used"], len(challenge["hints"]))
            return jsonify({
                "hints_used": hints_used,
                "total": len(challenge["hints"]),
                "hints": challenge["hints"][:hints_used],
            })
        participant_id = session.get("participant_id")
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        ctf = current_ctf()
        challenge = challenge_for_ctf(ctf["id"], challenge_id) if ctf else None
        if not challenge:
            return jsonify({"error": "Desafio não encontrado"}), 404
        record = challenge_record(participant_id, challenge_id)
        hints_used = min(record["hints_used"], len(challenge["hints"]))
        return jsonify({
            "hints_used": hints_used,
            "total": len(challenge["hints"]),
            "hints": challenge["hints"][:hints_used],
        })

    @app.post("/api/challenge/<int:challenge_id>/submit")
    def submit_challenge_flag_api(challenge_id):
        sandbox = admin_sandbox()
        if sandbox:
            challenge = sandbox_challenge(challenge_id)
            if not challenge:
                return jsonify({"error": "Desafio não encontrado"}), 404
            record = sandbox_record(sandbox, challenge_id)
            if record["status"] == "solved":
                return jsonify({"solved": True, "points": record["score"]})
            submitted = (request.get_json(silent=True) or {}).get("flag", "").strip()
            if submitted.upper() not in [flag.upper() for flag in challenge["flags"]]:
                return jsonify({"solved": False, "message": "Flag incorreta. Continue investigando o site."}), 400
            score = challenge_points_for_hint(challenge, record["hints_used"])
            record["status"] = "solved"
            record["score"] = score
            session.modified = True
            return jsonify({"solved": True, "points": score, "message": f"Correto! +{score} pontos."})
        participant_id = session.get("participant_id")
        if not participant_id:
            return jsonify({"error": "Sessão expirada"}), 401
        if not participant_is_active(participant_id):
            event = participant_event_summary(participant_id)
            if not event:
                return jsonify({"error": "Participação não encontrada"}), 404
            return jsonify({"status": "FINALIZADO", "code": event["code"], "ranking_url": url_for("ctf_archive_page", ctf_id=event["ctf_id"]), "home_url": url_for("ctf_home"), "feedback_url": url_for("feedback_page") if finished_participant() else None}), 409
        ctf = current_ctf()
        challenge = challenge_for_ctf(ctf["id"], challenge_id) if ctf else None
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

    @app.post("/dashboard/finish")
    def finish_participation():
        participant_id = session.get("participant_id")
        if not participant_id:
            return redirect(url_for("index"))
        ctf = current_ctf()
        if not ctf or not participant_is_active(participant_id, ctf):
            return redirect(url_for("public_ranking_page"))
        conn = get_db()
        conn.execute(
            "UPDATE participants SET finished_at = ? WHERE id = ? AND ctf_id = ?",
            (timestamp_now(), participant_id, ctf["id"]),
        )
        conn.commit()
        conn.close()
        log_event(ctf["id"], participant_id, "participant_finished", "finished")
        return redirect(url_for("feedback_page"))

    def finished_participant():
        """Participante que já encerrou a participação e ainda não deu feedback.

        Vale para dois caminhos: quem clicou em "finalizar" (finished_at
        preenchido) e quem foi pego pelo fim do tempo — nesse caso o
        finished_at fica vazio, mas o evento já está encerrado, e a pessoa
        também precisa ver a tela de feedback.
        """
        participant_id = session.get("participant_id")
        if not participant_id:
            return None
        current_ctf()  # encerra na hora um evento cujo tempo já estourou
        conn = get_db()
        participant = conn.execute(
            """SELECT p.id, p.ctf_id, p.name, p.finished_at, c.status AS ctf_status
               FROM participants p JOIN ctfs c ON c.id = p.ctf_id WHERE p.id = ?""",
            (participant_id,),
        ).fetchone()
        already_sent = conn.execute(
            "SELECT 1 FROM participant_feedback WHERE participant_id = ?", (participant_id,)
        ).fetchone()
        conn.close()
        if not participant or already_sent:
            return None
        if not participant["finished_at"] and participant["ctf_status"] == "ATIVO":
            return None
        return dict(participant)

    @app.get("/feedback")
    def feedback_page():
        participant = finished_participant()
        if not participant:
            return redirect(url_for("public_ranking_page"))
        return render_template(
            "feedback.html",
            participant=participant,
            questions=FEEDBACK_QUESTIONS,
            rating_label=FEEDBACK_RATING_LABEL,
            improvements_label=FEEDBACK_IMPROVEMENTS_LABEL,
            improvements_max=FEEDBACK_IMPROVEMENTS_MAX,
            error=None,
        )

    @app.post("/feedback")
    def submit_feedback():
        participant = finished_participant()
        if not participant:
            return redirect(url_for("public_ranking_page"))
        data, name_error = clean_feedback_payload(request.form)
        if name_error:
            return render_template(
                "feedback.html",
                participant=participant,
                questions=FEEDBACK_QUESTIONS,
                rating_label=FEEDBACK_RATING_LABEL,
                improvements_label=FEEDBACK_IMPROVEMENTS_LABEL,
                improvements_max=FEEDBACK_IMPROVEMENTS_MAX,
                error=name_error,
            ), 400
        conn = get_db()
        conn.execute(
            """
            INSERT INTO participant_feedback
                (ctf_id, participant_id, name, turma, difficulty, clarity, favorite_part,
                 favorite_part_other, time_enough, organization_rating, improvements, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                participant["ctf_id"], participant["id"], data["name"], data["turma"],
                data["difficulty"], data["clarity"], data["favorite_part"], data["favorite_part_other"],
                data["time_enough"], data["organization_rating"], data["improvements"], timestamp_now(),
            ),
        )
        conn.commit()
        conn.close()
        log_event(participant["ctf_id"], participant["id"], "feedback_sent", "feedback")
        session["feedback_thanks"] = True
        return redirect(url_for("public_ranking_page"))

    @app.get("/ranking")
    def public_ranking_page():
        # Without a live CTF the page is an archive index, not a misleading
        # "current" ranking for the most recent past edition.
        ctf = current_ctf()
        history = ctf_history()
        return render_template("ranking.html", ctf=ctf, history=history, feedback_thanks=session.pop("feedback_thanks", False))

    @app.get("/api/ranking")
    def api_ranking():
        ctf = current_ctf()
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

    @app.get("/api/score-breakdown/<int:participant_id>")
    def score_breakdown_api(participant_id):
        breakdown = score_breakdown(participant_id)
        if breakdown is None:
            return jsonify({"error": "Participante não encontrado"}), 404
        return jsonify(breakdown)

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
        event_challenges = challenges_for_ctf(ctf_id)
        event_order = {challenge["id"]: position for position, challenge in enumerate(event_challenges)}
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
                    "name": CHALLENGE_BY_ID[result["challenge_id"]]["name"],
                    "code": CHALLENGE_BY_ID[result["challenge_id"]]["code"],
                    "difficulty": CHALLENGE_BY_ID[result["challenge_id"]]["difficulty"],
                    "status": result["status"],
                    "hints_used": result["hints_used"],
                    "score_earned": result["score_earned"],
                    "solved_at": result["solved_at"],
                }
                for result in sorted(saved_results, key=lambda row: event_order.get(row["challenge_id"], len(event_order)))
                if result["challenge_id"] in CHALLENGE_BY_ID
            ]
        return render_template("ctf_archive.html", ctf=ctf, ranking=ranking, challenge_count=len(event_challenges))

    @app.post("/admin/ctf/<int:ctf_id>/delete")
    def delete_ctf_archive(ctf_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        conn = get_db()
        ctf = conn.execute("SELECT status FROM ctfs WHERE id = ?", (ctf_id,)).fetchone()
        if not ctf:
            conn.close()
            session["admin_notice"] = "Esse CTF não existe ou já foi excluído."
            return redirect(url_for("admin_dashboard"))
        if ctf["status"] == "ATIVO":
            conn.close()
            session["admin_notice"] = "Não é possível excluir um CTF ativo. Finalize o evento primeiro."
            return redirect(url_for("admin_dashboard"))
        participant_ids = conn.execute("SELECT id FROM participants WHERE ctf_id = ?", (ctf_id,)).fetchall()
        ids = [row["id"] for row in participant_ids]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM participant_challenges WHERE participant_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM logs WHERE participant_id IN ({placeholders})", ids)
        conn.execute("DELETE FROM logs WHERE ctf_id = ?", (ctf_id,))
        conn.execute("DELETE FROM participants WHERE ctf_id = ?", (ctf_id,))
        conn.execute("DELETE FROM ctfs WHERE id = ?", (ctf_id,))
        conn.commit()
        conn.close()
        session["admin_notice"] = "Dashboard arquivado e dados do CTF excluídos."
        return redirect(url_for("admin_dashboard"))

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
        # Sair para o painel encerra qualquer ambiente de teste aberto.
        session.pop("admin_sandbox", None)
        ctf = current_ctf()
        admin_notice = session.pop("admin_notice", None)
        conn = get_db()
        history_rows = conn.execute("SELECT * FROM ctfs ORDER BY created_at DESC, id DESC").fetchall()
        history = []
        for item in history_rows:
            participant_count = conn.execute(
                "SELECT COUNT(*) AS total FROM participants WHERE ctf_id = ?",
                (item["id"],),
            ).fetchone()["total"]
            history.append({"ctf": dict(item), "participants": participant_count})
        conn.close()
        # O feedback pertence a um evento: mostramos o do CTF ativo ou, fora de
        # um evento, o da edição mais recente que tenha respostas.
        feedback_event = ctf or next((item["ctf"] for item in history if feedback_for_ctf(item["ctf"]["id"])), None)
        feedback_entries = feedback_for_ctf(feedback_event["id"]) if feedback_event else []
        ranking = participant_ranking(ctf["id"]) if ctf else []
        participant_count = len(ranking)
        active_count = sum(1 for row in ranking if not row["finished_at"])
        finished_count = sum(1 for row in ranking if row["finished_at"])
        return render_template(
            "admin_dashboard.html",
            ctf=ctf,
            ranking=ranking,
            history=history,
            participant_count=participant_count,
            active_count=active_count,
            finished_count=finished_count,
            admin_notice=admin_notice,
            challenge_lists=CHALLENGE_LISTS,
            default_challenge_list=DEFAULT_CHALLENGE_LIST,
            feedback_entries=feedback_entries,
            feedback_event=feedback_event,
            feedback_questions=FEEDBACK_QUESTIONS,
            announcement_live=active_announcement(),
            remaining_seconds=ctf_remaining_seconds(ctf) if ctf else None,
        )

    @app.post("/admin/generate")
    def generate_ctf():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        if session.get("admin_sandbox"):
            session["admin_notice"] = "Encerre o ambiente de teste do gabarito antes de iniciar um CTF."
            return redirect(url_for("admin_challenges_index"))
        raw_duration = (request.form.get("max_duration_minutes") or "").strip()
        try:
            max_duration_minutes = int(raw_duration) if raw_duration else None
        except ValueError:
            max_duration_minutes = 0
        if max_duration_minutes is not None and not 1 <= max_duration_minutes <= 1440:
            session["admin_notice"] = "Informe a duração máxima em minutos, entre 1 e 1440."
            return redirect(url_for("admin_dashboard"))
        list_id = request.form.get("challenge_list", DEFAULT_CHALLENGE_LIST)
        if list_id not in CHALLENGE_LISTS:
            session["admin_notice"] = "Escolha uma lista de desafios válida."
            return redirect(url_for("admin_dashboard"))
        selected = sorted(
            (CHALLENGE_BY_ID[challenge_id] for challenge_id in FIXED_CHALLENGE_LISTS[list_id]),
            key=lambda challenge: (DIFFICULTY_ORDER.index(challenge["difficulty"]), challenge["id"]),
        )
        # A pontuação máxima de qualquer edição é sempre 1.000 pontos, não
        # importa quantos desafios fáceis/médios/difíceis o administrador
        # escolher: o peso de cada dificuldade é redistribuído proporcionalmente.
        normalized_scores = normalize_event_scores(selected)
        conn = get_db()
        conn.execute("UPDATE ctfs SET status='FINALIZADO', finished_at=? WHERE status='ATIVO'", (timestamp_now(),))
        code = generate_ctf_code()
        now = timestamp_now()
        conn.execute("INSERT INTO ctfs (code, status, created_at, max_duration_minutes, challenge_list_id) VALUES (?, 'ATIVO', ?, ?, ?)", (code, now, max_duration_minutes, list_id))
        conn.commit()
        ctf_id = conn.execute("SELECT id FROM ctfs WHERE code = ? ORDER BY id DESC LIMIT 1", (code,)).fetchone()["id"]
        conn.executemany(
            "INSERT INTO ctf_challenges (ctf_id, challenge_id, position, base_points, hint_penalty) VALUES (?, ?, ?, ?, ?)",
            [
                (ctf_id, challenge["id"], position, base_points, hint_penalty)
                for position, (challenge, (base_points, hint_penalty)) in enumerate(zip(selected, normalized_scores), start=1)
            ],
        )
        conn.commit()
        conn.close()
        log_event(ctf_id, None, "ctf_started", code)
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/tempo-extra")
    def extend_ctf():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        # current_ctf() já encerra um evento cujo tempo acabou: depois disso não
        # há mais o que prorrogar.
        ctf = current_ctf()
        if not ctf:
            session["admin_notice"] = "Nenhum CTF em andamento para prorrogar."
            return redirect(url_for("admin_dashboard"))
        if not ctf["max_duration_minutes"]:
            session["admin_notice"] = "Este CTF não tem tempo limite — ele só termina quando você encerrar."
            return redirect(url_for("admin_dashboard"))
        extra = request.form.get("extra_minutes", type=int) or 0
        if not 1 <= extra <= 240:
            session["admin_notice"] = "Informe de 1 a 240 minutos de tempo extra."
            return redirect(url_for("admin_dashboard"))
        total = min(1440, ctf["max_duration_minutes"] + extra)
        conn = get_db()
        conn.execute("UPDATE ctfs SET max_duration_minutes = ? WHERE id = ? AND status = 'ATIVO'", (total, ctf["id"]))
        conn.commit()
        conn.close()
        log_event(ctf["id"], None, "ctf_extended", f"+{extra}min")
        session["admin_notice"] = f"+{extra} min no CTF {ctf['code']}. Novo limite: {total} minutos."
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

    def feedback_editions():
        """Edições que já receberam feedback, da mais recente para a mais antiga."""
        conn = get_db()
        event_rows = conn.execute("SELECT * FROM ctfs ORDER BY created_at DESC, id DESC").fetchall()
        conn.close()
        editions = []
        for row in event_rows:
            entries = feedback_for_ctf(row["id"])
            if entries:
                editions.append({"ctf": dict(row), "entries": entries})
        return editions

    @app.get("/admin/edicoes")
    def admin_editions_page():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        conn = get_db()
        rows = conn.execute("SELECT * FROM editions ORDER BY created_at DESC, id DESC").fetchall()
        conn.close()
        editions = []
        for row in rows:
            edition = dict(row)
            edition["ctf_count"] = len(edition_ctf_ids(edition["id"]))
            edition["ranking_size"] = len(edition_final_ranking(edition["id"]))
            edition["feedback_count"] = len(edition_feedback_entries(edition["id"]))
            editions.append(edition)
        return render_template(
            "admin_editions.html",
            editions=editions,
            notice=session.pop("edition_notice", None),
            error=session.pop("edition_error", None),
        )

    @app.post("/admin/edicoes")
    def admin_edition_create():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        name = " ".join((request.form.get("name") or "").split())[:EDITION_NAME_MAX]
        if not name:
            session["edition_error"] = "Dê um nome para a edição."
            return redirect(url_for("admin_editions_page"))
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO editions (name, summary, status, show_challenges, created_at) VALUES (?, NULL, 'rascunho', 0, ?)",
            (name, timestamp_now()),
        )
        edition_id = cur.lastrowid
        conn.commit()
        conn.close()
        session["edition_notice"] = f"Edição “{name}” criada. Agora escolha as rodadas que entram nela."
        return redirect(url_for("admin_edition_detail", edition_id=edition_id))

    @app.get("/admin/edicoes/<int:edition_id>")
    def admin_edition_detail(edition_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        edition = edition_row(edition_id)
        if not edition:
            return redirect(url_for("admin_editions_page"))
        conn = get_db()
        ctf_rows = conn.execute("SELECT * FROM ctfs ORDER BY created_at DESC, id DESC").fetchall()
        conn.close()
        selected_ids = set(edition_ctf_ids(edition_id))
        available = []
        for row in ctf_rows:
            item = dict(row)
            item["selected"] = item["id"] in selected_ids
            item["participants"] = len(participant_ranking(item["id"]))
            available.append(item)
        return render_template(
            "admin_edition_detail.html",
            edition=edition,
            available_ctfs=available,
            entries=edition_entries(edition_id),
            ranking=edition_final_ranking(edition_id),
            feedback_entries=edition_feedback_candidates(edition_id),
            challenges=edition_challenges(edition_id),
            questions=FEEDBACK_QUESTIONS,
            notice=session.pop("edition_notice", None),
            error=session.pop("edition_error", None),
        )

    @app.post("/admin/edicoes/<int:edition_id>")
    def admin_edition_save(edition_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        if not edition_row(edition_id):
            return redirect(url_for("admin_editions_page"))
        name = " ".join((request.form.get("name") or "").split())[:EDITION_NAME_MAX]
        if not name:
            session["edition_error"] = "A edição precisa de um nome."
            return redirect(url_for("admin_edition_detail", edition_id=edition_id))
        conn = get_db()
        conn.execute(
            "UPDATE editions SET name = ?, summary = ?, show_challenges = ? WHERE id = ?",
            (name, (request.form.get("summary") or "").strip()[:EDITION_SUMMARY_MAX] or None,
             1 if request.form.get("show_challenges") else 0, edition_id),
        )
        conn.commit()
        conn.close()
        session["edition_notice"] = "Dados da edição salvos."
        return redirect(url_for("admin_edition_detail", edition_id=edition_id))

    def edition_state_payload(edition_id):
        """Estado que a tela de montagem redesenha depois de cada mudança."""
        entries = edition_entries(edition_id)
        merged_ids = sorted({
            source["participant_id"] for merge in edition_merge_rows(edition_id) for source in merge["sources"]
        })
        return jsonify({
            "ranking": edition_final_ranking(edition_id),
            "round_rankings": edition_round_rankings(edition_id),
            "merged_participant_ids": merged_ids,
            "entries": entries,
            "rounds": sorted({entry["ctf_code"] for entry in entries}),
            "feedbacks": [
                {"id": item["id"], "name": item["name"], "turma": item["turma"],
                 "ctf_code": item["ctf_code"], "included": bool(item["included"]),
                 "improvements": item["improvements"]}
                for item in edition_feedback_candidates(edition_id)
            ],
        })

    def edition_guard(edition_id):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Sessão administrativa necessária"}), 401
        if not edition_row(edition_id):
            return jsonify({"error": "Edição não encontrada"}), 404
        return None

    @app.get("/admin/edicoes/<int:edition_id>/estado")
    def admin_edition_state(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/rodadas")
    def admin_edition_rounds(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        current = set(edition_ctf_ids(edition_id))
        ctf_id = payload.get("ctf_id")
        if ctf_id is None:
            return jsonify({"error": "Informe a rodada"}), 400
        current.add(int(ctf_id)) if payload.get("included") else current.discard(int(ctf_id))
        sync_edition_sources(edition_id, sorted(current))
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/participantes")
    def admin_edition_participants(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        ids = [int(value) for value in payload.get("participant_ids", [])]
        if not ids:
            return jsonify({"error": "Nenhuma participação informada"}), 400
        conn = get_db()
        for participant_id in ids:
            conn.execute(
                "UPDATE edition_participants SET included = ? WHERE edition_id = ? AND participant_id = ?",
                (1 if payload.get("included") else 0, edition_id, participant_id),
            )
        conn.commit()
        conn.close()
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/fusao/previa")
    def admin_edition_merge_preview(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        allowed = {entry["participant_id"] for entry in edition_entries(edition_id) if entry["included"]}
        ids = [int(value) for value in payload.get("participant_ids", []) if int(value) in allowed]
        if len(ids) < 2:
            return jsonify({"error": "Escolha ao menos duas participações da classificação."}), 400
        return jsonify(merge_preview(ids))

    @app.post("/admin/edicoes/<int:edition_id>/fusao")
    def admin_edition_merge_create(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        allowed = {entry["participant_id"] for entry in edition_entries(edition_id) if entry["included"]}
        already_merged = {source["participant_id"] for merge in edition_merge_rows(edition_id) for source in merge["sources"]}
        ids = [int(value) for value in payload.get("participant_ids", []) if int(value) in allowed - already_merged]
        if len(ids) < 2:
            return jsonify({"error": "Escolha ao menos duas participações ainda não fundidas."}), 400
        name = " ".join((payload.get("display_name") or "").split())[:30]
        if not name:
            return jsonify({"error": "Dê um nome ao participante fundido."}), 400
        preview = merge_preview(ids)
        by_id = {item["id"]: item for item in preview["challenges"]}
        chosen = [int(value) for value in payload.get("challenge_ids", []) if int(value) in by_id]
        challenge_points = {str(cid): by_id[cid]["points"] for cid in chosen}
        try:
            points = max(0, int(payload.get("points")))
            elapsed = max(0, int(payload.get("elapsed")))
        except (TypeError, ValueError):
            return jsonify({"error": "Pontuação e tempo precisam ser números."}), 400
        conn = get_db()
        cur = conn.execute(
            """INSERT INTO edition_merges
               (edition_id, display_name, challenge_ids, challenge_points, points, elapsed, hidden, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
            (edition_id, name, json.dumps(chosen), json.dumps(challenge_points), points, elapsed, timestamp_now()),
        )
        conn.executemany(
            "INSERT INTO edition_merge_sources (merge_id, participant_id) VALUES (?, ?)",
            [(cur.lastrowid, participant_id) for participant_id in ids],
        )
        conn.commit()
        conn.close()
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/entrada")
    def admin_edition_entry_update(edition_id):
        """Esconde uma entrada da classificação final ou apaga uma fusão."""
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        kind, key, action = payload.get("kind"), payload.get("key"), payload.get("action")
        conn = get_db()
        if kind == "merge":
            merge = conn.execute(
                "SELECT id FROM edition_merges WHERE id = ? AND edition_id = ?", (key, edition_id)
            ).fetchone()
            if not merge:
                conn.close()
                return jsonify({"error": "Fusão não encontrada"}), 404
            if action == "remover":
                conn.execute("DELETE FROM edition_merge_sources WHERE merge_id = ?", (key,))
                conn.execute("DELETE FROM edition_merges WHERE id = ?", (key,))
            else:
                conn.execute("UPDATE edition_merges SET hidden = ? WHERE id = ?", (1 if payload.get("hidden") else 0, key))
        elif kind == "single":
            # Participações reais nunca são apagadas, só saem da classificação.
            conn.execute(
                "UPDATE edition_participants SET included = ? WHERE edition_id = ? AND participant_id = ?",
                (0 if payload.get("hidden") else 1, edition_id, key),
            )
        else:
            conn.close()
            return jsonify({"error": "Entrada inválida"}), 400
        conn.commit()
        conn.close()
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/feedbacks")
    def admin_edition_feedbacks(edition_id):
        blocked = edition_guard(edition_id)
        if blocked:
            return blocked
        payload = request.get_json(silent=True) or {}
        feedback_id = payload.get("feedback_id")
        if feedback_id is None:
            return jsonify({"error": "Informe o feedback"}), 400
        conn = get_db()
        if payload.get("included"):
            conn.execute(
                """INSERT OR IGNORE INTO edition_feedback (edition_id, feedback_id)
                   SELECT ?, id FROM participant_feedback
                   WHERE id = ? AND ctf_id IN (SELECT ctf_id FROM edition_ctfs WHERE edition_id = ?)""",
                (edition_id, int(feedback_id), edition_id),
            )
        else:
            conn.execute(
                "DELETE FROM edition_feedback WHERE edition_id = ? AND feedback_id = ?",
                (edition_id, int(feedback_id)),
            )
        conn.commit()
        conn.close()
        return edition_state_payload(edition_id)

    @app.post("/admin/edicoes/<int:edition_id>/publicar")
    def admin_edition_publish(edition_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        edition = edition_row(edition_id)
        if not edition:
            return redirect(url_for("admin_editions_page"))
        publishing = edition["status"] != "publicada"
        if publishing and not edition_final_ranking(edition_id):
            session["edition_error"] = "Inclua ao menos uma rodada com participantes antes de publicar."
            return redirect(url_for("admin_edition_detail", edition_id=edition_id))
        conn = get_db()
        conn.execute(
            "UPDATE editions SET status = ?, published_at = ? WHERE id = ?",
            ("publicada" if publishing else "rascunho", timestamp_now() if publishing else None, edition_id),
        )
        conn.commit()
        conn.close()
        session["edition_notice"] = "Edição publicada no site." if publishing else "Edição voltou para rascunho."
        return redirect(url_for("admin_edition_detail", edition_id=edition_id))

    @app.post("/admin/edicoes/<int:edition_id>/remover")
    def admin_edition_delete(edition_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        conn = get_db()
        for table in ("edition_participants", "edition_feedback", "edition_ctfs"):
            conn.execute(f"DELETE FROM {table} WHERE edition_id = ?", (edition_id,))
        conn.execute("DELETE FROM editions WHERE id = ?", (edition_id,))
        conn.commit()
        conn.close()
        session["edition_notice"] = "Edição removida. As rodadas e os feedbacks originais continuam no arquivo."
        return redirect(url_for("admin_editions_page"))

    @app.post("/admin/desafios/treino")
    def admin_toggle_training():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        list_id = request.form.get("list_id")
        if list_id not in CHALLENGE_LISTS:
            session["admin_notice"] = "Lista inválida para treino."
            return redirect(url_for("admin_challenges_index"))
        conn = get_db()
        if list_id in training_list_ids():
            conn.execute("DELETE FROM training_lists WHERE list_id = ?", (list_id,))
            session["admin_notice"] = f"{CHALLENGE_LISTS[list_id]['label']} saiu do treino livre."
        else:
            conn.execute("INSERT INTO training_lists (list_id, enabled_at) VALUES (?, ?)", (list_id, timestamp_now()))
            session["admin_notice"] = f"{CHALLENGE_LISTS[list_id]['label']} liberada em /treino."
        conn.commit()
        conn.close()
        return redirect(url_for("admin_challenges_index"))

    @app.get("/treino")
    def training_index():
        enabled = training_list_ids()
        lists = [
            {"id": list_id, "label": meta["label"], "description": meta["description"],
             "challenges": training_challenges(list_id)}
            for list_id, meta in CHALLENGE_LISTS.items() if list_id in enabled
        ]
        return render_template("training.html", lists=lists)

    @app.get("/treino/<list_id>")
    def training_list_page(list_id):
        challenges = training_challenges(list_id)
        if not challenges:
            return redirect(url_for("training_index"))
        return render_template(
            "training_list.html",
            list_id=list_id,
            meta=CHALLENGE_LISTS[list_id],
            challenges=challenges,
        )

    @app.post("/treino/flag")
    def training_check_flag():
        """Confere a flag no treino, sem gravar pontuação nem tempo."""
        payload = request.get_json(silent=True) or {}
        challenge = training_challenge(payload.get("challenge_id"))
        if not challenge:
            return jsonify({"error": "Desafio indisponível para treino"}), 404
        attempt = (payload.get("flag") or "").strip()
        correct = any(attempt.lower() == flag.lower() for flag in challenge["flags"])
        return jsonify({"correct": correct})

    @app.get("/edicoes")
    def public_editions_page():
        return render_template("editions.html", editions=published_editions())

    @app.get("/edicoes/<int:edition_id>")
    def public_edition_page(edition_id):
        edition = edition_row(edition_id)
        if not edition or edition["status"] != "publicada":
            return redirect(url_for("public_editions_page"))
        return render_template(
            "edition_detail.html",
            edition=edition,
            ranking=edition_final_ranking(edition_id),
            round_rankings=edition_round_rankings(edition_id),
            challenges=edition_challenges(edition_id) if edition["show_challenges"] else [],
            walkthroughs={item["id"]: challenge_walkthrough(item) for item in edition_challenges(edition_id)} if edition["show_challenges"] else {},
        )

    @app.get("/admin/agenda")
    def admin_schedule_page():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        events = scheduled_event_rows()
        editing = next((item for item in events if item["id"] == request.args.get("editar", type=int)), None)
        return render_template(
            "admin_schedule.html",
            events=events,
            editing=editing,
            error=session.pop("schedule_error", None),
            notice=session.pop("schedule_notice", None),
            today=datetime.now(EVENT_TIMEZONE).strftime("%Y-%m-%d"),
            timezone_label=str(EVENT_TIMEZONE),
        )

    @app.post("/admin/agenda")
    def admin_schedule_save():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        event_id = request.form.get("event_id", type=int)
        data, error = clean_scheduled_event(request.form)
        if error:
            session["schedule_error"] = error
            return redirect(url_for("admin_schedule_page", editar=event_id) if event_id else url_for("admin_schedule_page"))
        conn = get_db()
        if event_id:
            conn.execute(
                """UPDATE scheduled_events SET title=?, signup_url=?, location=?, details=?, starts_at=?,
                   ends_at=?, banner_starts_at=?, banner_ends_at=? WHERE id=?""",
                (data["title"], data["signup_url"], data["location"], data["details"], data["starts_at"],
                 data["ends_at"], data["banner_starts_at"], data["banner_ends_at"], event_id),
            )
            session["schedule_notice"] = f"Agendamento de “{data['title']}” atualizado."
        else:
            conn.execute(
                """INSERT INTO scheduled_events
                   (title, signup_url, location, details, starts_at, ends_at, banner_starts_at, banner_ends_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["title"], data["signup_url"], data["location"], data["details"], data["starts_at"],
                 data["ends_at"], data["banner_starts_at"], data["banner_ends_at"], timestamp_now()),
            )
            session["schedule_notice"] = f"“{data['title']}” agendado."
        conn.commit()
        conn.close()
        return redirect(url_for("admin_schedule_page"))

    @app.post("/admin/agenda/<int:event_id>/remover")
    def admin_schedule_delete(event_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        conn = get_db()
        conn.execute("DELETE FROM scheduled_events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
        session["schedule_notice"] = "Agendamento removido."
        return redirect(url_for("admin_schedule_page"))

    @app.get("/admin/feedbacks")
    def admin_feedbacks_page():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        editions = feedback_editions()
        # Uma edição por vez: a escolhida na URL, ou a mais recente com respostas.
        requested = request.args.get("ctf", type=int)
        selected = next((item for item in editions if item["ctf"]["id"] == requested), None) or (editions[0] if editions else None)
        return render_template(
            "admin_feedbacks.html",
            editions=editions,
            selected=selected,
            summary=feedback_summary(selected["entries"]) if selected else None,
            total=sum(len(item["entries"]) for item in editions),
            questions=FEEDBACK_QUESTIONS,
            rating_label=FEEDBACK_RATING_LABEL,
            improvements_label=FEEDBACK_IMPROVEMENTS_LABEL,
        )

    @app.get("/admin/feedbacks/<int:feedback_id>")
    def admin_feedback_detail(feedback_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        conn = get_db()
        row = conn.execute("SELECT ctf_id FROM participant_feedback WHERE id = ?", (feedback_id,)).fetchone()
        event_row = conn.execute("SELECT * FROM ctfs WHERE id = ?", (row["ctf_id"],)).fetchone() if row else None
        conn.close()
        if not row:
            return redirect(url_for("admin_feedbacks_page"))
        # Navegar "um por um" segue a mesma ordem da listagem da edição.
        entries = feedback_for_ctf(row["ctf_id"])
        position = next(index for index, item in enumerate(entries) if item["id"] == feedback_id)
        entry = entries[position]
        ranking = participant_ranking(row["ctf_id"])
        performance = next((item for item in ranking if item["id"] == entry["participant_id"]), None)
        if performance:
            performance = dict(performance, position=ranking.index(performance) + 1, total=len(ranking))
        return render_template(
            "admin_feedback_detail.html",
            entry=entry,
            ctf=dict(event_row),
            questions=FEEDBACK_QUESTIONS,
            rating_label=FEEDBACK_RATING_LABEL,
            improvements_label=FEEDBACK_IMPROVEMENTS_LABEL,
            performance=performance,
            breakdown=score_breakdown(entry["participant_id"]) if entry["participant_id"] else None,
            position=position + 1,
            count=len(entries),
            previous_entry=entries[position - 1] if position > 0 else None,
            next_entry=entries[position + 1] if position + 1 < len(entries) else None,
        )

    @app.get("/admin/desafios")
    def admin_challenges_index():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        # Voltar à biblioteca encerra qualquer ambiente de teste aberto.
        session.pop("admin_sandbox", None)
        admin_notice = session.pop("admin_notice", None)
        lists = {}
        for list_id, meta in CHALLENGE_LISTS.items():
            by_difficulty = {
                difficulty: sorted(challenge_pool(list_id, difficulty), key=lambda item: item["code"])
                for difficulty in DIFFICULTY_ORDER
            }
            lists[list_id] = {"label": meta["label"], "description": meta["description"], "by_difficulty": by_difficulty, "runnable": True}
        enabled_training = training_list_ids()
        for list_id, data in lists.items():
            data["training"] = list_id in enabled_training
        return render_template(
            "admin_challenges.html",
            lists=lists,
            total=len(CHALLENGES),
            ctf_active=bool(current_ctf()),
            admin_notice=admin_notice,
        )

    @app.post("/admin/desafios/executar")
    def admin_sandbox_start():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        if current_ctf():
            session["admin_notice"] = "Não é possível abrir o ambiente de teste enquanto um CTF está ativo."
            return redirect(url_for("admin_challenges_index"))
        list_id = request.form.get("list_id")
        if list_id not in CHALLENGE_LISTS:
            session["admin_notice"] = "Escolha uma lista de desafios válida."
            return redirect(url_for("admin_challenges_index"))
        # Todos os desafios da lista, em ordem fácil → médio → difícil.
        challenge_ids = []
        for difficulty in DIFFICULTY_ORDER:
            pool = sorted(challenge_pool(list_id, difficulty), key=lambda item: item["code"])
            challenge_ids.extend(item["id"] for item in pool)
        session["admin_sandbox"] = {
            "list_id": list_id,
            "challenge_ids": challenge_ids,
            "started_at": timestamp_now(),
            "progress": {},
        }
        return redirect(url_for("admin_sandbox_dashboard"))

    @app.get("/admin/sandbox")
    def admin_sandbox_dashboard():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        sandbox = session.get("admin_sandbox")
        if not sandbox:
            session["admin_notice"] = "Abra o ambiente de teste a partir de uma lista de desafios."
            return redirect(url_for("admin_challenges_index"))
        if current_ctf():
            # Guarda defensiva: se um CTF ficou ativo, encerra o teste.
            session.pop("admin_sandbox", None)
            session["admin_notice"] = "O ambiente de teste foi encerrado porque um CTF está ativo."
            return redirect(url_for("admin_challenges_index"))
        challenge_ids = sandbox["challenge_ids"]
        rows = []
        for cid in challenge_ids:
            challenge = CHALLENGE_BY_ID[cid]
            record = sandbox_record(sandbox, cid)
            rows.append({
                "challenge": challenge,
                "record": {
                    "status": record["status"],
                    "hints_used": record["hints_used"],
                    "score_earned": record["score"],
                },
                "value_after_hints": challenge_points_for_hint(challenge, record["hints_used"]),
            })
        total = sum(row["record"]["score_earned"] for row in rows if row["record"]["status"] == "solved")
        solved = sum(1 for row in rows if row["record"]["status"] == "solved")
        stats = {"total": total, "solved": solved, "skipped": 0}
        active_challenge_id = request.args.get("challenge", default=challenge_ids[0], type=int)
        if active_challenge_id not in challenge_ids:
            active_challenge_id = challenge_ids[0]
        active_challenge = CHALLENGE_BY_ID[active_challenge_id]
        active_index = challenge_ids.index(active_challenge_id)
        active_record = next(row["record"] for row in rows if row["challenge"]["id"] == active_challenge_id)
        list_meta = CHALLENGE_LISTS.get(sandbox["list_id"], {"label": "Teste"})
        return render_template(
            "participant_dashboard.html",
            participant={"id": 0, "name": "Administrador (teste)", "entered_at": sandbox["started_at"]},
            ctf={"code": list_meta["label"].upper() + " · TESTE", "max_duration_minutes": None},
            challenges=rows,
            stats=stats,
            active_challenge=active_challenge,
            active_record=active_record,
            active_position=active_index + 1,
            next_challenge=CHALLENGE_BY_ID[challenge_ids[active_index + 1]] if active_index + 1 < len(challenge_ids) else None,
            remaining_seconds=None,
            sandbox=True,
            dashboard_endpoint="admin_sandbox_dashboard",
            finish_action=url_for("admin_sandbox_finish"),
            home_url=url_for("admin_challenges_index"),
        )

    @app.post("/admin/sandbox/finish")
    def admin_sandbox_finish():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        session.pop("admin_sandbox", None)
        return redirect(url_for("admin_challenges_index"))

    @app.get("/admin/desafios/<int:challenge_id>")
    def admin_challenge_detail(challenge_id):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        challenge = CHALLENGE_BY_ID.get(challenge_id)
        if not challenge:
            session["admin_notice"] = "Desafio não encontrado."
            return redirect(url_for("admin_challenges_index"))
        encoded_token = base64.b64encode(challenge["flags"][0].encode("utf-8")).decode("ascii") if challenge["mechanism"] == "base64" else None
        return render_template(
            "admin_challenge_detail.html",
            challenge=challenge,
            walkthrough=challenge_walkthrough(challenge),
            encoded_token=encoded_token,
        )

    @app.get("/admin/logout")
    def admin_logout():
        session.pop("admin_logged_in", None)
        return redirect(url_for("admin_login_page"))

    return app


__all__ = ["create_app", "CHALLENGES"]
