# JACITEC CTF

Plataforma web de **Capture The Flag** feita para eventos acadêmicos, aulas de segurança
da informação e competições internas. Cada participante investiga sites fictícios
("laboratórios") em busca de vulnerabilidades reais de aplicações web — coisas como
código-fonte exposto, `robots.txt` esquecido, IDOR, SQL Injection, cabeçalhos HTTP
reveladores, tokens em Base64 etc. — e envia a flag encontrada para pontuar.

Todo o back-end guarda estado em SQLite e a interface é servida por um único
app Flask, sem necessidade de front-end separado ou build step.

## Principais funcionalidades

- **Participação por código**: o participante só entra com nome + código do evento
  gerado pelo administrador.
- **Laboratórios variados**: 54 desafios distribuídos em 3 listas independentes,
  cada uma com **10 fáceis, 5 médios e 3 difíceis** (veja [Listas e desafios](#listas-e-desafios)).
- **Sorteio por composição**: o administrador escolhe a lista e quantos desafios de
  cada dificuldade quer usar (por padrão, 5 fáceis, 2 médios e 1 difícil); os desafios
  específicos são sorteados na hora e ficam fixos para aquela edição.
- **Pontuação sempre normalizada para 1.000 pontos** no total, não importa a composição
  escolhida (veja [Como funciona a pontuação](#como-funciona-a-pontuação)).
- **Dicas progressivas**: cada desafio tem 3 dicas; a primeira sempre indica a
  ferramenta específica necessária (DevTools, `curl`, Burp Suite, um decodificador
  Base64 etc.). Cada dica revelada reduz parte do valor do desafio.
- **Painel de jogo arrastável**: o participante joga dentro de um iframe com um
  painel flutuante (cronômetro, pontos, dicas, envio de flag) que pode ser
  arrastado, minimizado e movido para qualquer canto da tela.
- **Ranking ao vivo** com atualização automática e **detalhamento de pontuação**
  (clique no ícone de olho ao lado da pontuação de qualquer participante para ver
  quantos pontos vieram de desafios fáceis/médios/difíceis e quanto foi perdido em dicas).
- **Arquivo de edições encerradas**: cada CTF finalizado fica salvo com sua
  classificação final, tempos e resumo por desafio de cada participante.
- **Painel administrativo** para gerar eventos, acompanhar o placar em tempo real,
  encerrar o CTF e apagar arquivos antigos.

## Como funciona a pontuação

A pontuação máxima de **qualquer** edição é sempre **1.000 pontos**, mesmo que o
administrador mude a composição (mais fáceis, menos difíceis, etc.). O peso de
cada dificuldade é recalculado proporcionalmente toda vez que um evento é gerado,
sempre respeitando fácil < médio < difícil.

- Cada dica revelada reduz parte do valor daquele desafio.
- Mesmo usando todas as dicas, uma solução correta garante pelo menos 1 ponto.
- O tempo não tira pontos — ele só é usado para desempate (mesma pontuação, menor
  tempo de participação fica na frente).
- No ranking e no arquivo de eventos, o ícone de olho ao lado da pontuação abre um
  modal com o detalhamento: pontos ganhos/máximos por dificuldade, quantos desafios
  foram resolvidos e quanto foi perdido em dicas.

## Listas e desafios

Existem três listas independentes (`lista-1`, `lista-2`, `lista-3`), pensadas para
permitir reaproveitar a plataforma em edições diferentes sem repetir o mesmo conjunto
de desafios visíveis. Cada lista sempre tem:

| Dificuldade | Quantidade por lista |
|---|---|
| Fácil | 10 |
| Médio | 5 |
| Difícil | 3 |

O administrador escolhe apenas a lista e quantos desafios de cada dificuldade quer
sortear (entre 1 e 8 no total); os desafios individuais são sempre sorteados pela
plataforma. Os mesmos desafios podem ser reaproveitados em eventos diferentes — a
lista não se esgota.

Cada laboratório é um site fictício com tema visual próprio (loja, portal de
viagens, painel de desenvolvedor, arcade, etc.) para que a investigação se pareça
com a de um site real, e não com uma lista de exercícios. A técnica necessária para
resolver cada um nunca é explicada na própria página — só nas dicas, reveladas uma
a uma pelo participante.

Os oito desafios "clássicos" (usados desde a primeira versão da plataforma) estão
documentados individualmente em `docs/challenges/`, com nome, objetivo,
dificuldade, pontos, flag, dica e solução.

## Requisitos

- Docker
- Docker Compose

## Variáveis de ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Valores padrão:

```env
DATABASE_URL=sqlite:////app/data/ctf.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=adm2026
SECRET_KEY=change-me
FLASK_ENV=production
```

Troque `ADMIN_USERNAME`, `ADMIN_PASSWORD` e `SECRET_KEY` antes de usar a plataforma
em um evento real.

## Execução com Docker

```bash
docker compose up --build -d
```

A aplicação estará disponível em:

- http://localhost:5001

Para aplicar mudanças de código feitas depois do primeiro build, é preciso
reconstruir a imagem (o código não fica montado como volume):

```bash
docker compose build && docker compose up -d
```

Para parar:

```bash
docker compose down
```

Para remover também os dados persistidos (participantes, eventos, histórico):

```bash
docker compose down -v
```

## Acesso administrativo

- URL: http://localhost:5001/admin/login
- Usuário: valor de `ADMIN_USERNAME` (padrão: `admin`)
- Senha: valor de `ADMIN_PASSWORD` (padrão: `adm2026`)

## Fluxo de uso

1. Acesse o painel administrativo.
2. Escolha a lista de desafios e quantos desafios fáceis, médios e difíceis deseja
   usar (entre 1 e 8 no total) e, opcionalmente, um tempo máximo de duração.
3. Clique em "Gerar código"; a plataforma sorteia os desafios e já calcula a
   pontuação normalizada (sempre somando 1.000 pontos no total).
4. Compartilhe o código gerado com os participantes.
5. Participantes acessam a página inicial → "Participar do CTF", informam nome e
   código.
6. Acompanhe o placar em tempo real pelo painel administrativo ou pela página
   pública de ranking.
7. Finalize a competição quando necessário — o evento e a classificação final ficam
   salvos no arquivo de edições encerradas.

## Regras do CTF

- Teste somente os laboratórios desta plataforma.
- Não compartilhe flags, soluções ou credenciais com outros participantes.
- Não use IA generativa para resolver desafios ou elaborar payloads.
- Não ataque a infraestrutura, participantes ou serviços externos.

## Estrutura do projeto

```text
app/
  __init__.py          # aplicação Flask: rotas, regras de pontuação, catálogo de desafios
  static/              # CSS, ícones e a logo institucional
  templates/           # páginas (landing, participação, painel do jogo, ranking, admin)
    partials/          # componentes reutilizáveis (ex.: modal de pontuação detalhada)
docs/challenges/       # documentação individual dos desafios clássicos (1 a 8)
tests/test_app.py      # testes de integração (pytest + Flask test client)
```

## Testes

Os testes usam um banco SQLite temporário e não dependem do Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/test_app.py -v
```

## Resetar tudo

Para limpar os dados do banco e reinstalar a aplicação do zero:

```bash
docker compose down -v
docker compose up --build -d
```

## Observações técnicas

- O app usa SQLite em volume Docker (`ctf-data`) para manter os dados entre reinícios
  do container sem depender de um banco externo.
- O ranking é atualizado por polling simples (sem WebSocket), então não depende de
  bibliotecas extras no navegador.
- O backend valida o código de entrada, controla o tempo do evento e calcula a
  pontuação inteiramente no servidor — o front-end nunca decide o valor de um desafio.

## Licença e créditos

Este projeto foi desenvolvido pelos alunos **Miguel Santuchi Poleto**
([LinkedIn](https://www.linkedin.com/in/miguelpoleto/)) e **Alessandro Mion Batista**
([LinkedIn](https://www.linkedin.com/in/alessandromb/)) para o Instituto Federal do
Espírito Santo (IFES).

O projeto é distribuído sob a [licença MIT](LICENSE): você pode usar, copiar,
modificar e reaproveitar este projeto livremente — inclusive trocando nome, marca,
logotipos e textos para outra instituição, turma ou evento — **desde que mantenha os
créditos aos autores originais** em algum lugar visível do projeto derivado (por
exemplo, no README ou na página inicial da aplicação).
