# Challenge 42

Nome: Reserva fora do escopo
Dificuldade: Difícil
Pontos: 30

Flag: JACITEC{catalog_42_idor}

Conceito: IDOR / autorização

Como resolver:
1. Leia o enunciado e execute apenas o fluxo normal do laboratório.
2. Consulte o recurso próprio, capture o cabeçalho de delegação e repita a requisição autorizada para o recurso de referência.
3. Registre a evidência encontrada e envie a flag no painel do CTF.

Ferramentas úteis:
- DevTools → Network, curl ou Burp Repeater

Dica 1: Comece pelo comportamento normal da página.
Dica 2: A evidência está no tráfego, código ou recurso técnico indicado pelo laboratório.
Dica 3: Não teste nada fora deste ambiente isolado.

