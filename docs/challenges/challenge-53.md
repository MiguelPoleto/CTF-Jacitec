# Challenge 53 — L3-D02

Nome: Perfil de fornecedor
Lista: 3
Dificuldade: Difícil
Identificador: L3-D02

Flag: JACITEC{catalog_53_idor}

Conceito: Controle de acesso a recursos (IDOR)

Descrição (só para a organização): Teste a autorização do recurso, em vez de somente o endereço.

Dica 1: Ferramenta necessária: DevTools (aba Network) ou um interceptador de requisições (ex.: Burp Suite) para repetir a chamada alterando parâmetros e cabeçalhos.
Dica 2: Depois de ver a requisição original, tente trocar o identificador do recurso e observe a resposta.
Dica 3: A autorização pode depender de um cabeçalho que a primeira resposta já revelou — reenvie a requisição incluindo-o.
