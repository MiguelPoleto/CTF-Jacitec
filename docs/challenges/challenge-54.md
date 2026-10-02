# Challenge 54 — L3-D03

Nome: Protocolo de entrega
Lista: 3
Dificuldade: Difícil
Identificador: L3-D03

Flag: JACITEC{catalog_54_redirect}

Conceito: Cadeia de redirecionamentos HTTP

Descrição (só para a organização): Os cabeçalhos e códigos de status formam a pista final.

Dica 1: Ferramenta necessária: DevTools (aba Network, com "Preserve log" ativado) ou `curl -IL` para acompanhar toda a cadeia de redirecionamentos HTTP.
Dica 2: Cada etapa da cadeia pode carregar um cabeçalho próprio — não olhe apenas a resposta final.
Dica 3: Siga o redirecionamento passo a passo até a resposta que já não redireciona mais.
