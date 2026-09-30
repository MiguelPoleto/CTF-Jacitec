# Challenge 05

Nome: Cabeçalhos curiosos
Dificuldade: Fácil
Pontos: 15

Flag: JACITEC{cookies_and_headers_tell_all}

Conceito: HTTP / parâmetros / cookies / headers

Como resolver:
1. Abra a aba "Network" do navegador e observe cada requisição do CTF.
2. Verifique cookies, headers e parâmetros que parecem estranhos ou não fazem parte do fluxo normal da página.
3. Muitas vezes a informação útil é entregue de forma discreta em um cabeçalho de resposta, em um cookie ou em um token de sessão.
4. A resposta esperada pode ser um identificador, um valor secreto ou uma string com a flag no formato correto.

Ferramentas úteis:
- DevTools -> Network
- observação de cookies e headers
- testes simples em curl com `-I` e `-v`

Dica 1: Observe os dados enviados em requisições e cookies.
Dica 2: O navegador guarda metadados importantes em headers.
Dica 3: A pista pode estar em uma variável de sessão discreta.

Dica 1: Observe os dados enviados em requisições e cookies.
Dica 2: O navegador guarda metadados importantes em headers.
Dica 3: A pista pode estar em uma variável de sessão discreta.
