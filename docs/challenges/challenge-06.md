# Challenge 06

Nome: IDOR no perfil
Dificuldade: Médio
Pontos: 15

Flag: JACITEC{idor_is_a_risk_06}

Conceito: IDOR / autorização / manipulação de identificadores

Como resolver:
1. Aplique a lógica de IDOR: altere um identificador numérico ou um parâmetro que parece referenciar um recurso interno.
2. Teste variações como trocar `1` por `2`, `3` ou outro valor e veja se o resultado muda sem autorização.
3. Se a aplicação expõe um recurso sensível por URL ou por query string sem verificar o dono do dado, o problema pode revelar a flag.
4. Depois de confirmar a falha, copie a informação exposta e use como resposta final.

Ferramentas úteis:
- navegador e inspeção de URL/parametros
- curl para testar IDs diferentes
- observação de respostas HTTP e JSON

Dica 1: A API parece confiar no valor de um parâmetro.
Dica 2: Teste se alterar o identificador muda o resultado.
Dica 3: Verifique se a autorização é realmente validada.

Dica 1: A API parece confiar no valor de um parâmetro.
Dica 2: Teste se alterar o identificador muda o resultado.
Dica 3: Verifique se a autorização é realmente validada.
