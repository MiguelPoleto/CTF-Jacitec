import os
import random
import re
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

# Três listas independentes, cada uma com exatamente 10 fáceis, 5 médios e 3
# difíceis (18 por lista, 54 no total). Cada desafio pertence a uma única lista
# e tem dificuldade fixa — nada é reatribuído depois por faixa de id.
# Os oito laboratórios originais (id 1-8) ficam na lista 1.
for _challenge_id, _mechanism, _difficulty in (
    (1, "source", "Fácil"), (2, "sitemap", "Fácil"), (3, "base64", "Fácil"), (4, "js", "Fácil"),
    (5, "header", "Fácil"), (6, "idor", "Difícil"), (7, "search", "Médio"), (8, "audit", "Difícil"),
):
    CHALLENGES[_challenge_id - 1].update({"list_id": "lista-1", "mechanism": _mechanism, "difficulty": _difficulty})

# (id, lista, dificuldade, mecanismo, nome, descrição — esta só aparece para a organização)
_EXTRA_CHALLENGES = [
    # Lista 1 — completa os 8 originais
    (9, "lista-1", "Fácil", "manifest", "Manifesto público", "Um arquivo de configuração do navegador contém uma pista."),
    (10, "lista-1", "Fácil", "metadata", "Metadados da galeria", "A ficha de uma imagem tem mais dados que a tela mostra."),
    (11, "lista-1", "Fácil", "source", "Rascunho esquecido", "O portal editorial deixou um rascunho no HTML."),
    (12, "lista-1", "Fácil", "receipt", "Recibo de atendimento", "O recibo da solicitação contém uma nota técnica nos cabeçalhos HTTP."),
    (13, "lista-1", "Fácil", "base64", "Texto transportado", "Uma mensagem foi codificada, mas não protegida."),
    (14, "lista-1", "Médio", "search", "Filtro de inventário", "A busca foi implementada sem tratar corretamente a entrada."),
    (15, "lista-1", "Médio", "header", "Resposta temporária", "Um serviço devolve uma pista apenas nos cabeçalhos HTTP."),
    (16, "lista-1", "Médio", "js", "Console de manutenção", "O painel frontend carrega uma configuração que não deveria ser pública."),
    (17, "lista-1", "Médio", "redirect", "Cadeia de redirecionamento", "Siga as respostas HTTP para encontrar a evidência correta."),
    (18, "lista-1", "Difícil", "idor", "Documento com acesso cruzado", "A validação de acesso depende de mais que trocar um número."),
    # Lista 2
    (19, "lista-2", "Fácil", "source", "Comentário de implantação", "Uma página institucional publicou uma nota interna."),
    (20, "lista-2", "Fácil", "robots", "Descoberta responsável", "Leia os arquivos de descoberta antes de enumerar caminhos."),
    (21, "lista-2", "Fácil", "base64", "Token de migração", "Uma aplicação antiga ainda publica um token codificado."),
    (22, "lista-2", "Fácil", "js", "Versão em cache", "O bundle do frontend contém uma anotação útil."),
    (23, "lista-2", "Fácil", "header", "Cookie de ambiente", "A resposta possui um metadado que o HTML não revela."),
    (24, "lista-2", "Fácil", "manifest", "Preferências públicas", "As preferências web expõem uma pista de configuração."),
    (25, "lista-2", "Fácil", "metadata", "Biblioteca de imagens", "Uma imagem de acervo foi entregue com metadados úteis."),
    (26, "lista-2", "Fácil", "source", "Fonte da newsletter", "O código-fonte de uma newsletter tem uma observação interna."),
    (27, "lista-2", "Fácil", "robots", "Backup previsível", "Um arquivo de descoberta aponta para material esquecido."),
    (28, "lista-2", "Fácil", "base64", "Mensagem serializada", "Uma sequência codificada precisa ser decifrada."),
    (29, "lista-2", "Médio", "search", "Pesquisa de acervo", "A busca deve ser analisada com um interceptador ou DevTools."),
    (30, "lista-2", "Médio", "header", "Cabeçalho de diagnóstico", "Use as ferramentas HTTP para enxergar a resposta inteira."),
    (31, "lista-2", "Médio", "js", "Bundle de homologação", "Uma variável de ambiente ficou publicada no JavaScript."),
    (32, "lista-2", "Médio", "metadata", "Ficha técnica da foto", "Os metadados de uma prévia trazem mais do que a legenda."),
    (33, "lista-2", "Médio", "search", "Catálogo interno", "Observe e repita a requisição antes de alterar a entrada."),
    (34, "lista-2", "Difícil", "idor", "Consulta de pedidos", "Um recurso sequencial exige testar autorização, não adivinhação."),
    (35, "lista-2", "Difícil", "audit", "Relatório de incidente", "Correlacione uma rota descoberta e o retorno estruturado."),
    (36, "lista-2", "Difícil", "redirect", "Entrega contínua", "Inspecione cada etapa de uma resposta redirecionada."),
    # Lista 3
    (37, "lista-3", "Fácil", "source", "Rascunho editorial", "Uma página de conteúdo manteve uma anotação fora da interface."),
    (38, "lista-3", "Fácil", "robots", "Serviço de catálogo", "Um arquivo de descoberta lista uma rota que não está no menu."),
    (39, "lista-3", "Fácil", "base64", "Registro legível", "Uma mensagem codificada precisa ser interpretada."),
    (40, "lista-3", "Fácil", "js", "Relatório de interface", "O frontend ainda traz uma variável de manutenção."),
    (41, "lista-3", "Fácil", "header", "Canal de suporte", "A resposta técnica contém uma informação fora do corpo HTML."),
    (42, "lista-3", "Fácil", "manifest", "Nota de navegador", "A configuração do navegador aponta para uma pista publicada."),
    (43, "lista-3", "Fácil", "metadata", "Acervo fotográfico", "Uma foto do acervo foi entregue com metadados extras."),
    (44, "lista-3", "Fácil", "source", "Página institucional", "Uma página institucional guarda uma anotação no HTML."),
    (45, "lista-3", "Fácil", "js", "Variável esquecida", "Uma variável de depuração ficou no JavaScript publicado."),
    (46, "lista-3", "Fácil", "robots", "Rotas fora do menu", "O arquivo de descoberta revela um caminho não divulgado."),
    (47, "lista-3", "Médio", "search", "Busca avançada", "A evidência aparece somente após manipular a requisição de busca."),
    (48, "lista-3", "Médio", "search", "Consulta composta", "Use uma ferramenta de repetição de requisições para validar a hipótese."),
    (49, "lista-3", "Médio", "header", "Dupla verificação", "A informação está em uma resposta que exige inspecionar HTTP."),
    (50, "lista-3", "Médio", "manifest", "Arquivo de manutenção", "Uma configuração exposta aponta para uma rota operacional."),
    (51, "lista-3", "Médio", "metadata", "Prévia silenciosa", "Uma prévia carregada em segundo plano tem metadados úteis."),
    (52, "lista-3", "Difícil", "audit", "Trilha de auditoria", "O endpoint é intencionalmente pouco visível, mas está no fluxo."),
    (53, "lista-3", "Difícil", "idor", "Perfil de fornecedor", "Teste a autorização do recurso, em vez de somente o endereço."),
    (54, "lista-3", "Difícil", "redirect", "Protocolo de entrega", "Os cabeçalhos e códigos de status formam a pista final."),
]
# A dica 1 de cada mecanismo sempre nomeia a ferramenta específica necessária
# para resolver o laboratório, conforme pedido: quem precisa de DevTools, de um
# decodificador Base64, de um interceptador de requisições etc. deve descobrir
# isso já na primeira dica, sem precisar gastar uma dica só para "adivinhar" a
# ferramenta certa.
HINTS_BY_MECHANISM = {
    "source": [
        "Ferramenta necessária: o código-fonte da página (botão direito → \"Ver/Exibir código-fonte\", ou Ctrl+U / Cmd+Option+U).",
        "Nem tudo que existe no HTML aparece renderizado na tela — procure por comentários e trechos ocultos.",
        "Percorra o documento inteiro, incluindo o que vem antes do <body> e depois do </body>.",
    ],
    "robots": [
        "Ferramenta necessária: o arquivo robots.txt do site (acesse diretamente pela URL, ex.: /robots.txt).",
        "Esse arquivo lista caminhos que os buscadores não devem indexar — mas o navegador consegue acessá-los normalmente.",
        "Abra manualmente qualquer rota listada como \"Disallow\" para ver o que ela entrega.",
    ],
    "sitemap": [
        "Procure no site um mapa com a lista de páginas e rotas disponíveis.",
        "Um mapa do site pode mostrar páginas que não aparecem na navegação principal.",
        "Acesse uma das rotas auxiliares listadas no mapa.",
    ],
    "base64": [
        "Ferramenta necessária: um decodificador Base64 (ex.: CyberChef, ou o terminal com `base64 -d`).",
        "O texto codificado não é criptografia — qualquer decodificador Base64 revela o conteúdo original.",
        "Copie exatamente a string codificada, sem espaços extras, antes de decodificar.",
    ],
    "js": [
        "Ferramenta necessária: DevTools do navegador (abas Console e Sources) para inspecionar o JavaScript carregado.",
        "Variáveis globais definidas em scripts ficam acessíveis digitando o nome delas no Console.",
        "Procure por arquivos .js carregados pela página e leia o conteúdo na aba Sources.",
    ],
    "header": [
        "Ferramenta necessária: DevTools (aba Network) ou `curl -I` para inspecionar os cabeçalhos completos da resposta HTTP.",
        "A interface visual não mostra tudo — os metadados podem estar apenas no cabeçalho da resposta.",
        "Repita a requisição da página principal e leia cada cabeçalho de resposta, um por um.",
    ],
    "receipt": [
        "Ferramenta necessária: DevTools do navegador (aba Network/Rede) para inspecionar a resposta de uma requisição.",
        "Clique no botão 'Baixar recibo' que aparece na página e selecione essa requisição na lista.",
        "Na seção Response Headers/Cabeçalhos de resposta, procure por X-Receipt-Note.",
    ],
    "idor": [
        "Ferramenta necessária: Burp Suite (ou outro interceptador de requisições) — o DevTools não permite adicionar ou alterar cabeçalhos na requisição antes de reenviá-la.",
        "Depois de ver a requisição original, tente trocar o identificador do recurso e observe a resposta.",
        "A autorização pode depender de um cabeçalho que a primeira resposta já revelou — reenvie a requisição incluindo-o.",
    ],
    "search": [
        "Ferramenta necessária: DevTools (aba Network) ou Burp Suite para observar e reenviar a requisição feita pelo formulário de busca.",
        "A busca normal só retorna registros públicos cujo título contém o termo pesquisado — procurar palavras do senso comum não revela nada escondido.",
        "O filtro quebra diante de uma condição de comparação sempre verdadeira dentro de um valor com aspas (ex.: fechar a aspa e encadear um OR com algo que sempre bate), não apenas pela palavra \"or\" estar na busca.",
    ],
    "audit": [
        "Ferramenta necessária: DevTools (aba Network) ou `curl` para inspecionar a resposta completa e os cabeçalhos do endpoint de status.",
        "O cabeçalho da resposta pode apontar diretamente para a rota de auditoria que você precisa visitar.",
        "Depois de descobrir a rota, acesse-a diretamente e leia o corpo da resposta com atenção.",
    ],
    "manifest": [
        "Ferramenta necessária: DevTools (aba Network) para ver os arquivos que a página carrega ao abrir.",
        "Ao carregar, a página busca um arquivo de configuração próprio — procure por um pedido a app.webmanifest (aba Network, filtro Fetch/XHR).",
        "Abra o conteúdo do app.webmanifest diretamente pela URL e leia todos os campos.",
    ],
    "metadata": [
        "Ferramenta necessária: DevTools (aba Network) para inspecionar os cabeçalhos de resposta do recurso de imagem/prévia.",
        "O elemento pode estar oculto na página, mas a requisição dele ainda aparece na aba Network.",
        "Leia os cabeçalhos customizados da resposta, não apenas o corpo retornado.",
    ],
    "redirect": [
        "Ferramenta necessária: DevTools (aba Network) para observar a cadeia, e Burp Suite ou `curl` para repetir uma das etapas manualmente — o DevTools sozinho não deixa adicionar cabeçalhos a uma requisição. Se usar `curl`/Burp fora do navegador, a requisição precisa levar o cookie da sua sessão ativa; o jeito mais simples é clicar com o botão direito na requisição, no Network, e usar \"Copy as cURL\" — isso já inclui o cookie certo.",
        "Clicar e seguir a cadeia normalmente (302 → 302 → 200) nunca mostra a flag, nem olhando o Network: a primeira etapa só devolve um token num cabeçalho, que precisa ser usado em outra requisição.",
        "Reenvie a segunda etapa manualmente (fora do navegador), incluindo o token obtido na primeira resposta como cabeçalho.",
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

assert all(count == {"F": 10, "M": 5, "D": 3}[DIFFICULTY_LETTERS[difficulty]] for (_, difficulty), count in _ordinals.items()) and len(_ordinals) == 9, \
    "Cada lista deve ter exatamente 10 fáceis, 5 médios e 3 difíceis."

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
CHALLENGE_LISTS = {
    "lista-1": {"label": "Lista de desafios 1", "description": "Fundamentos de segurança web e laboratórios clássicos."},
    "lista-2": {"label": "Lista de desafios 2", "description": "Uma edição alternativa com novos cenários e técnicas."},
    "lista-3": {"label": "Lista de desafios 3", "description": "Terceira coleção para evitar repetição entre edições."},
    "ctf-1": {"label": "CTF 1", "description": "Seleção fixa: 5 fáceis, 2 médios e 1 difícil."},
}
FIXED_CHALLENGE_LISTS = {
    "ctf-1": (1, 2, 3, 4, 5, 6, 7, 17),
}


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
    "source": {"tool": "Código-fonte da página (Ctrl+U / clique direito → Ver código-fonte)", "where": "Comentário HTML oculto na página inicial do laboratório.",
        "steps": ["Abra {root}.", "Veja o código-fonte da página (Ctrl+U).", "Procure por um comentário HTML (<!-- ... -->): a flag está escrita nele."]},
    "robots": {"tool": "Navegador (acesso direto por URL)", "where": "Rota em Disallow no robots.txt → endpoint de auditoria.",
        "steps": ["Acesse {root}/robots.txt.", "Leia o caminho em 'Disallow:' — {root}/operations/audit.", "Abra {root}/operations/audit; a flag vem no campo 'reference'."]},
    "base64": {"tool": "Decodificador Base64 (CyberChef ou `base64 -d`)", "where": "Token codificado exibido na própria página.",
        "steps": ["Abra {root} e localize o token codificado em destaque.", "Decodifique de Base64 (ex.: `echo '<token>' | base64 -d`).", "O texto decodificado é a flag."]},
    "js": {"tool": "DevTools → Console/Sources", "where": "Variável global no JavaScript da página.",
        "steps": ["Abra {root} e o DevTools (F12).", "No Console, digite: window.__labRelease", "O valor retornado é a flag."]},
    "header": {"tool": "DevTools → Network ou `curl -I`", "where": "Cabeçalho de resposta X-Campus-Notice.",
        "steps": ["Faça uma requisição a {root} (ex.: `curl -I http://<host>{root}`).", "Leia os cabeçalhos da resposta.", "A flag está no cabeçalho 'X-Campus-Notice'."]},
    "receipt": {"tool": "DevTools → Network", "where": "Cabeçalho X-Receipt-Note da resposta do recibo.",
        "steps": ["Abra {root} e clique em 'Baixar recibo'.", "No Network, selecione a requisição /receipt.", "Leia o cabeçalho de resposta 'X-Receipt-Note'."]},
    "manifest": {"tool": "DevTools → Network/Application ou acesso direto", "where": "Campo maintenance_note do app.webmanifest.",
        "steps": ["Abra {root}/app.webmanifest.", "Leia o JSON retornado.", "A flag está no campo 'maintenance_note'."]},
    "metadata": {"tool": "DevTools → Network ou `curl -I`", "where": "Cabeçalho X-Image-Description do recurso de prévia.",
        "steps": ["Requisite {root}/asset-preview (ex.: `curl -I http://<host>{root}/asset-preview`).", "Leia os cabeçalhos da resposta.", "A flag está no cabeçalho 'X-Image-Description'."]},
    "idor": {"tool": "Burp Suite (ou `curl`) — o DevTools não permite adicionar cabeçalhos a uma requisição", "where": "Registro 701 autorizado pelo cabeçalho vindo do 700.",
        "steps": ["Requisite {root}/api/record/700 e anote o cabeçalho 'X-Lab-Delegation' da resposta.", "Requisite {root}/api/record/701 incluindo esse cabeçalho (ex.: `curl -H 'X-Lab-Delegation: <valor>' http://<host>{root}/api/record/701`).", "A flag vem no campo 'reference'."]},
    "search": {"tool": "DevTools → Network ou Burp Suite (manipular o parâmetro de busca)", "where": "Resposta da busca com uma tautologia que burla o filtro de registros públicos.",
        "steps": ["Use a busca de {root} e observe a requisição a {root}/api/search?q=...", "Reenvie com um payload de tautologia real, ex.: {root}/api/search?q=' OR '1'='1", "O registro restrito aparece junto dos demais, com a flag no campo 'nota'."]},
    "audit": {"tool": "DevTools → Network ou `curl -I`", "where": "Cabeçalho X-Audit-Path → endpoint de auditoria.",
        "steps": ["Requisite {root}/operations/ping e leia o cabeçalho 'X-Audit-Path'.", "Abra o caminho indicado ({root}/operations/audit).", "A flag vem no campo 'reference'."]},
    "redirect": {"tool": "Burp Suite (ou `curl`) — o DevTools mostra a cadeia mas não permite reenviar com um cabeçalho novo", "where": "Cabeçalho X-Delivery-Receipt no segundo salto (/delivery/processing), só quando reenviado com o token de /start.",
        "steps": [
            "No DevTools → Network, clique com o botão direito na requisição de {root}/delivery/start e use \"Copy as cURL\" (isso já inclui o cookie da sessão ativa — sem ele, qualquer requisição a /lab/* é redirecionada para a home e nada funciona).",
            "Rode esse comando colado no terminal; a resposta (302) traz o cabeçalho 'X-Delivery-Token'.",
            "Repita o \"Copy as cURL\" na requisição de {root}/delivery/processing e adicione `-H 'X-Delivery-Token: <valor copiado>'` antes de rodar; só com esse cabeçalho a resposta traz 'X-Delivery-Receipt' com a flag.",
            "Clicar o link normalmente (sem repassar o token manualmente) nunca expõe a flag, mesmo seguindo toda a cadeia pelo Network.",
        ]},
}
_WALKTHROUGH_OVERRIDES = {
    2: {"tool": "Navegador (sitemap XML)", "where": "Mapa do site do portal → página auxiliar de relatório.",
        "steps": ["Abra Guias de viagem no site Wayfarer e clique em Mapa do site do portal.", "No sitemap XML, localize a URL da página auxiliar.", "Acesse /lab/2/files/report; a flag está no conteúdo da página."]},
    6: {"tool": "Burp Suite (ou `curl`) — o DevTools não permite adicionar cabeçalhos a uma requisição", "where": "Perfil 102 autorizado pelo cabeçalho vindo do perfil 101.",
        "steps": ["Requisite /lab/6/profile/101 e anote o cabeçalho 'X-Workspace-Access'.", "Requisite /lab/6/profile/102 incluindo esse cabeçalho.", "A flag vem no campo 'note'."]},
    7: {"tool": "DevTools → Network ou Burp Suite (manipular o parâmetro de busca)", "where": "Resposta da busca com uma tautologia que burla o filtro de eventos públicos.",
        "steps": ["Use a busca de /lab/7 e observe /lab/7/search?q=...", "Reenvie com um payload de tautologia real, ex.: /lab/7/search?q=' OR '1'='1", "O evento restrito da Night Owl aparece junto dos demais, com a flag no campo 'nota'."]},
    8: {"tool": "DevTools → Network ou acesso direto", "where": "Exportação de auditoria referenciada pela agenda.",
        "steps": ["Na agenda de /lab/8, observe a requisição a /lab/8/audit-log.", "Abra /lab/8/audit-log.", "A flag está no campo 'reference' da entrada de migração."]},
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


def playable_challenge(challenge_id, mechanism=None):
    """Desafio jogável no contexto atual: sandbox do admin ou CTF ativo."""
    challenge = sandbox_challenge(challenge_id, mechanism)
    if challenge:
        return challenge
    ctf = current_ctf()
    challenge = challenge_for_ctf(ctf["id"], challenge_id) if ctf else None
    if not challenge or (mechanism and challenge.get("mechanism") != mechanism):
        return None
    return challenge


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
            return jsonify({"status": "FINALIZADO", "code": event["code"], "ranking_url": url_for("ctf_archive_page", ctf_id=event["ctf_id"]), "home_url": url_for("ctf_home")}), 409
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
            return jsonify({"status": "FINALIZADO", "code": event["code"], "ranking_url": url_for("ctf_archive_page", ctf_id=event["ctf_id"]), "home_url": url_for("ctf_home")}), 409
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
        return redirect(url_for("public_ranking_page"))

    @app.get("/ranking")
    def public_ranking_page():
        # Without a live CTF the page is an archive index, not a misleading
        # "current" ranking for the most recent past edition.
        ctf = current_ctf()
        history = ctf_history()
        return render_template("ranking.html", ctf=ctf, history=history)

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
            challenge_availability={key: {difficulty: len(challenge_pool(key, difficulty)) for difficulty in ("Fácil", "Médio", "Difícil")} for key in CHALLENGE_LISTS},
            fixed_challenge_lists=FIXED_CHALLENGE_LISTS,
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
        list_id = request.form.get("challenge_list", "lista-1")
        if list_id not in CHALLENGE_LISTS:
            session["admin_notice"] = "Escolha uma lista de desafios válida."
            return redirect(url_for("admin_dashboard"))
        if list_id in FIXED_CHALLENGE_LISTS:
            selected = sorted(
                (CHALLENGE_BY_ID[challenge_id] for challenge_id in FIXED_CHALLENGE_LISTS[list_id]),
                key=lambda challenge: (DIFFICULTY_ORDER.index(challenge["difficulty"]), challenge["id"]),
            )
        else:
            # Keep bare POSTs from pre-selection integrations compatible with
            # the original eight-lab event. The admin form always submits these
            # fields and therefore always uses the randomized workflow below.
            legacy_default_request = not any(request.form.get(field) is not None for field in ("challenge_list", "easy_count", "medium_count", "hard_count"))
            requested = {}
            for difficulty, field, default in (("Fácil", "easy_count", 4), ("Médio", "medium_count", 3), ("Difícil", "hard_count", 1)):
                raw_count = (request.form.get(field) or str(default)).strip()
                try:
                    requested[difficulty] = int(raw_count)
                except ValueError:
                    requested[difficulty] = -1
                available = challenge_pool(list_id, difficulty)
                if requested[difficulty] < 0 or requested[difficulty] > len(available):
                    session["admin_notice"] = f"Não há desafios {difficulty.lower()} inéditos suficientes nessa lista. Escolha outra composição ou lista."
                    return redirect(url_for("admin_dashboard"))
            total_challenges = sum(requested.values())
            if not 1 <= total_challenges <= 8:
                session["admin_notice"] = "Escolha entre 1 e 8 desafios no total."
                return redirect(url_for("admin_dashboard"))
            if legacy_default_request:
                selected = CHALLENGES[:8]
            else:
                # Sorteio dentro de cada nível, mas a ordem da edição é sempre
                # fáceis → médios → difíceis (ex.: 5/2/1 = posições 1-5 fáceis,
                # 6-7 médios e 8 difícil).
                selected = []
                for difficulty in ("Fácil", "Médio", "Difícil"):
                    selected.extend(random.sample(challenge_pool(list_id, difficulty), requested[difficulty]))
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
            lists[list_id] = {"label": meta["label"], "description": meta["description"], "by_difficulty": by_difficulty}
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
