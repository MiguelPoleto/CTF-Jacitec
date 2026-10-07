# Challenge 03

Nome: Base64 em branco
Dificuldade: Fácil
Peso base: 5 pontos

Flag: `JACITEC{base64_is_not_a_secret}`

Conceito: Base64 / encoding simples

## Como resolver

1. Na página inicial do Devdesk, clique em **Ler documentação da API**.
2. Na seção **Campo de token legado**, copie o valor Base64 exibido no bloco de código.
3. Decodifique o valor usando qualquer decodificador Base64. O resultado é diretamente a flag; não é uma rota nem uma pista intermediária.
4. Copie a flag decodificada exatamente como está.

Ferramentas úteis:
- Decodificador Base64
- DevTools do navegador, se precisar inspecionar o texto da página

Dicas:
1. Abra a documentação da API pelo botão na página inicial.
2. Na seção **Campo de token legado**, a sequência do bloco de código está em Base64. Converta-a para texto legível com um decodificador; não é uma senha para testar no site.
3. O texto decodificado é `JACITEC{base64_is_not_a_secret}`.
