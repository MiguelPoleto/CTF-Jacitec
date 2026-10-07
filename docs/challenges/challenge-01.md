# Challenge 01

Nome: Olhe melhor
Dificuldade: Fácil
Peso base: 5 pontos

Flag: `JACITEC{source_hidden_01}`

Conceito: HTML / comentários

## Como resolver

1. Abra o laboratório e use F12 para abrir as ferramentas de desenvolvedor.
2. Na aba **Elements**, use o seletor de elementos e clique dentro do site do desafio. O laboratório está dentro de um iframe; confirme que a árvore exibida corresponde ao documento do laboratório, não à página externa do CTF.
3. Examine os comentários HTML no início desse documento. A flag está em um comentário e não aparece no conteúdo visual.
4. Copie a flag exatamente como está.

**Atenção:** Ctrl+U pode exibir o código-fonte da página externa que contém o iframe, não o documento carregado dentro dele. Use o DevTools para inspecionar o conteúdo do laboratório.

Ferramentas úteis:
- DevTools do navegador, aba **Elements**
- Seletor de elementos

Dicas:
1. O laboratório está incorporado em um iframe; inspecione o documento carregado nele.
2. Examine a árvore de elementos, inclusive o conteúdo não visível.
3. Procure o comentário HTML no início do documento do laboratório.
