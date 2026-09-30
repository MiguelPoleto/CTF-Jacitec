# Challenge 07

Nome: Busca indiscreta
Dificuldade: Médio
Pontos: 15

Flag: JACITEC{sql_injection_is_not_safe}

Conceito: SQL injection / entrada de usuário

Como resolver:
1. Identifique o ponto de entrada da busca e teste entradas simples, como um nome comum ou uma palavra aleatória.
2. Observe como a aplicação monta a query e qual tipo de retorno ela entrega.
3. Tente sequência de caracteres que alterem a lógica da expressão, por exemplo usar operadores lógicos e comparações em combinações simples.
4. O objetivo é burlar a condição de filtro para obter uma resposta que normalmente não estaria disponível.

Ferramentas úteis:
- Burp Suite ou interceptador de requisições
- navegador DevTools
- testes com payloads SQL básicos e validação de resposta da app

Dica 1: Observe os parâmetros enviados na busca.
Dica 2: Substituir um valor por outra expressão pode mudar a resposta.
Dica 3: Uma expressão lógica pode burlar a filtragem da consulta.

Dica 1: Observe os parâmetros enviados na busca.
Dica 2: Substituir um valor por outra expressão pode mudar a resposta.
Dica 3: Uma expressão lógica pode burlar a filtragem da consulta.
