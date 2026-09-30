# JACITEC CTF

Plataforma web simples de Capture The Flag para uso em eventos acadêmicos e competições internas.

## Objetivo

A plataforma permite:

- participantes entrarem com nome e código do CTF;
- administrar o ciclo de vida de uma competição;
- registrar pontuação, dicas e skips;
- exibir ranking em tempo real;
- manter histórico de competições finalizadas.

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

## Execução com Docker

```bash
docker compose up --build -d
```

A aplicação estará disponível em:

- http://localhost:5001

Para parar:

```bash
docker compose down
```

Para remover também os dados persistidos:

```bash
docker compose down -v
```

## Acesso administrativo

- URL: http://localhost:5000/admin/login
- Usuário: admin
- Senha: adm2026

## Fluxo de uso

1. Acesse o painel administrativo.
2. Clique em "GERAR NOVO CTF".
3. Copie o código exibido.
4. Entregue o código aos participantes.
5. Acompanhe o ranking em tempo real.
6. Finalize a competição quando necessário.

## Estrutura dos desafios

Os desafios estão documentados em:

```text
docs/challenges/
```

Cada arquivo explica:

- nome;
- objetivo;
- dificuldade;
- pontos;
- flag;
- dica e solução.

## Resetar tudo

Para limpar os dados do banco e reinstalar a aplicação:

```bash
docker compose down -v
docker compose up --build -d
```

## Observações

- O app usa SQLite em volume Docker para manter os dados no repositório do projeto.
- O ranking é atualizado por polling e não depende de instalação local de bibliotecas extras.
- O backend valida o código e controla o tempo e a pontuação no servidor.
