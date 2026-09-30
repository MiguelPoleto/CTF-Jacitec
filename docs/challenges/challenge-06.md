# Challenge 06

Nome: IDOR no perfil
Dificuldade: Médio
Pontos: 15

Flag: JACITEC{idor_is_a_risk_06}

Conceito: IDOR / autorização / manipulação de identificadores

Como resolver:
1. Abra o perfil próprio (`101`) pela página CloudVault e capture a requisição no Network, curl ou Burp Repeater.
2. Inspecione os cabeçalhos da resposta: o serviço legado fornece uma credencial de laboratório em `X-Workspace-Access`.
3. Repita a requisição para o recurso compartilhado (`102`) incluindo esse cabeçalho. Somente trocar o número agora retorna `403` e não expõe a flag.
4. O objetivo é demonstrar que uma autorização frágil, baseada em um segredo entregue no tráfego do usuário, ainda permite acesso cruzado.

Ferramentas úteis:
- DevTools (Network) para ler cabeçalhos de resposta
- curl ou Burp Suite Repeater para repetir a requisição com um cabeçalho
- observação de respostas HTTP, código 403 e JSON

Dica 1: A API parece confiar no valor de um parâmetro.
Dica 2: Teste se alterar o identificador muda o resultado.
Dica 3: Verifique se a autorização é realmente validada.

Dica 1: A API parece confiar no valor de um parâmetro.
Dica 2: Teste se alterar o identificador muda o resultado.
Dica 3: Verifique se a autorização é realmente validada.
