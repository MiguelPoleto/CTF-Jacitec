# Challenge 04

Nome: Arquivo de frontend
Dificuldade: Fácil
Peso base: 5 pontos

Flag: `JACITEC{js_holds_the_truth}`

Conceito: DevTools / JavaScript inline

## Como resolver

1. Abra o DevTools com F12 e inspecione o documento do laboratório Pixel Arcade, carregado dentro do iframe.
2. Na aba **Sources**, abra a página inicial do laboratório e examine o script inline no fim do documento.
3. Localize a constante `arcadeReleaseNote`; seu valor é a flag.
4. Copie a flag exatamente como está.

**Atenção:** o botão **Verificar atualização** só mostra uma mensagem de status e não revela a flag.

Ferramentas úteis:
- DevTools, aba **Sources**
- Busca de texto nas fontes da página

Dicas:
1. Inspecione a página inicial do laboratório dentro do iframe.
2. Procure o script inline no fim do documento.
3. Leia o valor de `arcadeReleaseNote`.
