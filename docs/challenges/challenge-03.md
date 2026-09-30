# Challenge 03

Nome: Base64 em branco
Dificuldade: Fácil
Pontos: 10

Flag: JACITEC{base64_is_not_a_secret}

Conceito: Base64 / encoding simples

Como resolver:
1. Encontre a string codificada dentro do código, no HTML, no JavaScript, no payload da API ou em um atributo escondido.
2. Teste a decodificação em Base64, pois o padrão de entrada é geralmente legível após a conversão.
3. Se a saída for um texto ou uma mensagem indicando uma rota, um nome de arquivo ou uma pista, significa que você chegou no ponto correto.
4. A flag costuma sair naturalmente a partir da mensagem decodificada; é só copiar o valor final.

Ferramentas úteis:
- base64 decoder online ou comando `echo ... | base64 -d`
- navegador DevTools
- inspeção do HTML/JS

Dica 1: O dado parece ser texto codificado em base64.
Dica 2: Testar a decodificação pode revelar a pista.
Dica 3: A string parece estar em um formato de texto simples.

Dica 1: O dado parece ser texto codificado em base64.
Dica 2: Testar a decodificação pode revelar a pista.
Dica 3: A string parece estar em um formato de texto simples.
