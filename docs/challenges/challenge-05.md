# Challenge 05

Nome: Cabeçalhos curiosos
Dificuldade: Fácil
Peso base: 5 pontos

Flag: `JACITEC{cookies_and_headers_tell_all}`

Conceito: HTTP / cabeçalhos de resposta

## Como resolver

1. Abra o DevTools na aba **Network** e recarregue a página inicial do laboratório Second Story.
2. Selecione a requisição GET da página do laboratório.
3. Nos **Response Headers** (cabeçalhos de resposta), localize `X-Campus-Notice`.
4. O valor desse cabeçalho é a flag. Este desafio não usa cookie nem variável de sessão.

Ferramentas úteis:
- DevTools do navegador, aba **Network**
- Inspeção dos cabeçalhos da resposta HTTP

Dicas:
1. Selecione a requisição GET da página inicial do laboratório.
2. Inspecione os cabeçalhos de resposta, não os cabeçalhos enviados pelo navegador.
3. O valor de `X-Campus-Notice` é a flag.
