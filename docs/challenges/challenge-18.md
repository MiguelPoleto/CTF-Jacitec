# Challenge 18 — L1-D03

Nome: Documento com acesso cruzado
Lista: 1
Dificuldade: Difícil
Identificador: L1-D03

Flag: JACITEC{catalog_18_idor}

Conceito: Controle de acesso a recursos (IDOR)

Descrição (só para a organização): A validação de acesso depende de mais que trocar um número.

Dica 1: Ferramenta necessária: DevTools (aba Network) ou um interceptador de requisições (ex.: Burp Suite) para repetir a chamada alterando parâmetros e cabeçalhos.
Dica 2: Depois de ver a requisição original, tente trocar o identificador do recurso e observe a resposta.
Dica 3: A autorização pode depender de um cabeçalho que a primeira resposta já revelou — reenvie a requisição incluindo-o.
