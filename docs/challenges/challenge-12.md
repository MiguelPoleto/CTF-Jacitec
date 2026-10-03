# Challenge 12 — L1-F09

Nome: Recibo de atendimento
Lista: 1
Dificuldade: Fácil
Identificador: L1-F09

Flag: JACITEC{catalog_12_receipt}

Conceito: Inspeção de cabeçalhos HTTP

Descrição (só para a organização): O recibo da solicitação contém uma nota técnica nos cabeçalhos HTTP.

Dica 1: Ferramenta necessária: DevTools do navegador (aba Network/Rede) para inspecionar a resposta de uma requisição.
Dica 2: Clique no botão "Baixar recibo" que aparece na página e selecione essa requisição na lista.
Dica 3: Na seção Response Headers/Cabeçalhos de resposta, procure por X-Receipt-Note.

Como resolver:
1. Abra o laboratório e clique em "Baixar recibo".
2. No DevTools → Network/Rede, selecione a requisição `/receipt`.
3. Leia o cabeçalho de resposta `X-Receipt-Note` e envie o valor como flag.
