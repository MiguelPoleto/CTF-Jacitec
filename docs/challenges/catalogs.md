# Catálogos de desafios

O JACITEC CTF tem **54 desafios** divididos em **3 listas independentes**. Cada lista tem exatamente **10 fáceis, 5 médios e 3 difíceis**, e cada desafio pertence a uma única lista.

## Identificador

Cada desafio tem um identificador no formato `L<lista>-<nível><nº>`:

- `L1`, `L2`, `L3` — a lista;
- `F` = fácil, `M` = médio, `D` = difícil;
- o número é a ordem do desafio dentro daquele nível na lista.

Exemplo: `L2-M03` é o terceiro desafio médio da lista 2. O identificador, a lista e o nível aparecem no painel do participante em cada desafio e no resumo dos CTFs encerrados.

## Como uma edição é montada

O administrador escolhe a lista e quantos desafios de cada nível quer (de 1 a 8 no total). Os desafios são sorteados dentro de cada nível, mas a ordem da edição é sempre **fáceis → médios → difíceis**: com 5 fáceis, 2 médios e 1 difícil, as posições 1 a 5 são fáceis, a 6 e a 7 são médias e a 8 é difícil. Os mesmos desafios podem voltar a ser sorteados em edições futuras.

## Seleção fixa: CTF 1

Além das três listas sorteadas, o painel administrativo oferece a seleção fixa **CTF 1**, com estes oito desafios em ordem de dificuldade:

| Nível | Identificador | Desafio | Conceito |
|---|---|---|---|
| Fácil | L1-F01 | Olhe melhor | Código-fonte HTML / comentários |
| Fácil | L1-F02 | Mapa do site | Sitemap XML / descoberta de conteúdo |
| Fácil | L1-F03 | Base64 em branco | Codificação Base64 |
| Fácil | L1-F04 | Arquivo de frontend | JavaScript publicado no frontend |
| Fácil | L1-F05 | Cabeçalhos curiosos | Cabeçalhos HTTP e cookies |
| Médio | L1-M01 | IDOR no perfil | Controle de acesso a recursos (IDOR) |
| Médio | L1-M02 | Busca indiscreta | SQL injection |
| Difícil | L1-D02 | Cadeia de redirecionamento | Cadeia de redirecionamentos HTTP |

Esta seleção usa os desafios existentes da Lista 1; não cria cópias deles nem altera as três listas do catálogo. Ao escolher **CTF 1** no painel, a composição fica fixa em 5 fáceis, 2 médios e 1 difícil, sem sorteio.

Os desafios 01 a 08 são os laboratórios clássicos da primeira versão, com sites próprios; os demais usam os temas visuais compartilhados.

## Lista 1

| Identificador | Desafio | Nível | Conceito | Doc |
|---|---|---|---|---|
| L1-F01 | Olhe melhor | Fácil | Código-fonte HTML / comentários | [challenge-01](challenge-01.md) |
| L1-F02 | Mapa do site | Fácil | Sitemap XML / descoberta de conteúdo | [challenge-02](challenge-02.md) |
| L1-F03 | Base64 em branco | Fácil | Codificação Base64 | [challenge-03](challenge-03.md) |
| L1-F04 | Arquivo de frontend | Fácil | JavaScript publicado no frontend | [challenge-04](challenge-04.md) |
| L1-F05 | Cabeçalhos curiosos | Fácil | Cabeçalhos de resposta HTTP | [challenge-05](challenge-05.md) |
| L1-F06 | Manifesto público | Fácil | Manifesto da aplicação web | [challenge-09](challenge-09.md) |
| L1-F07 | Metadados da galeria | Fácil | Metadados de recursos | [challenge-10](challenge-10.md) |
| L1-F08 | Rascunho esquecido | Fácil | Código-fonte HTML / comentários | [challenge-11](challenge-11.md) |
| L1-F09 | Recibo de atendimento | Fácil | Inspeção de cabeçalhos HTTP | [challenge-12](challenge-12.md) |
| L1-F10 | Texto transportado | Fácil | Codificação Base64 | [challenge-13](challenge-13.md) |
| L1-M01 | IDOR no perfil | Médio | Controle de acesso a recursos (IDOR) | [challenge-06](challenge-06.md) |
| L1-M02 | Busca indiscreta | Médio | Validação de entrada em busca | [challenge-07](challenge-07.md) |
| L1-M03 | Filtro de inventário | Médio | Validação de entrada em busca | [challenge-14](challenge-14.md) |
| L1-M04 | Resposta temporária | Médio | Cabeçalhos de resposta HTTP | [challenge-15](challenge-15.md) |
| L1-M05 | Console de manutenção | Médio | JavaScript publicado no frontend | [challenge-16](challenge-16.md) |
| L1-D01 | Camadas finais | Difícil | Endpoints operacionais / auditoria | [challenge-08](challenge-08.md) |
| L1-D02 | Cadeia de redirecionamento | Difícil | Cadeia de redirecionamentos HTTP | [challenge-17](challenge-17.md) |
| L1-D03 | Documento com acesso cruzado | Difícil | Controle de acesso a recursos (IDOR) | [challenge-18](challenge-18.md) |

## Lista 2

| Identificador | Desafio | Nível | Conceito | Doc |
|---|---|---|---|---|
| L2-F01 | Comentário de implantação | Fácil | Código-fonte HTML / comentários | [challenge-19](challenge-19.md) |
| L2-F02 | Descoberta responsável | Fácil | Arquivos de descoberta (robots.txt) | [challenge-20](challenge-20.md) |
| L2-F03 | Token de migração | Fácil | Codificação Base64 | [challenge-21](challenge-21.md) |
| L2-F04 | Versão em cache | Fácil | JavaScript publicado no frontend | [challenge-22](challenge-22.md) |
| L2-F05 | Cookie de ambiente | Fácil | Cabeçalhos de resposta HTTP | [challenge-23](challenge-23.md) |
| L2-F06 | Preferências públicas | Fácil | Manifesto da aplicação web | [challenge-24](challenge-24.md) |
| L2-F07 | Biblioteca de imagens | Fácil | Metadados de recursos | [challenge-25](challenge-25.md) |
| L2-F08 | Fonte da newsletter | Fácil | Código-fonte HTML / comentários | [challenge-26](challenge-26.md) |
| L2-F09 | Backup previsível | Fácil | Arquivos de descoberta (robots.txt) | [challenge-27](challenge-27.md) |
| L2-F10 | Mensagem serializada | Fácil | Codificação Base64 | [challenge-28](challenge-28.md) |
| L2-M01 | Pesquisa de acervo | Médio | Validação de entrada em busca | [challenge-29](challenge-29.md) |
| L2-M02 | Cabeçalho de diagnóstico | Médio | Cabeçalhos de resposta HTTP | [challenge-30](challenge-30.md) |
| L2-M03 | Bundle de homologação | Médio | JavaScript publicado no frontend | [challenge-31](challenge-31.md) |
| L2-M04 | Ficha técnica da foto | Médio | Metadados de recursos | [challenge-32](challenge-32.md) |
| L2-M05 | Catálogo interno | Médio | Validação de entrada em busca | [challenge-33](challenge-33.md) |
| L2-D01 | Consulta de pedidos | Difícil | Controle de acesso a recursos (IDOR) | [challenge-34](challenge-34.md) |
| L2-D02 | Relatório de incidente | Difícil | Endpoints operacionais / auditoria | [challenge-35](challenge-35.md) |
| L2-D03 | Entrega contínua | Difícil | Cadeia de redirecionamentos HTTP | [challenge-36](challenge-36.md) |

## Lista 3

| Identificador | Desafio | Nível | Conceito | Doc |
|---|---|---|---|---|
| L3-F01 | Rascunho editorial | Fácil | Código-fonte HTML / comentários | [challenge-37](challenge-37.md) |
| L3-F02 | Serviço de catálogo | Fácil | Arquivos de descoberta (robots.txt) | [challenge-38](challenge-38.md) |
| L3-F03 | Registro legível | Fácil | Codificação Base64 | [challenge-39](challenge-39.md) |
| L3-F04 | Relatório de interface | Fácil | JavaScript publicado no frontend | [challenge-40](challenge-40.md) |
| L3-F05 | Canal de suporte | Fácil | Cabeçalhos de resposta HTTP | [challenge-41](challenge-41.md) |
| L3-F06 | Nota de navegador | Fácil | Manifesto da aplicação web | [challenge-42](challenge-42.md) |
| L3-F07 | Acervo fotográfico | Fácil | Metadados de recursos | [challenge-43](challenge-43.md) |
| L3-F08 | Página institucional | Fácil | Código-fonte HTML / comentários | [challenge-44](challenge-44.md) |
| L3-F09 | Variável esquecida | Fácil | JavaScript publicado no frontend | [challenge-45](challenge-45.md) |
| L3-F10 | Rotas fora do menu | Fácil | Arquivos de descoberta (robots.txt) | [challenge-46](challenge-46.md) |
| L3-M01 | Busca avançada | Médio | Validação de entrada em busca | [challenge-47](challenge-47.md) |
| L3-M02 | Consulta composta | Médio | Validação de entrada em busca | [challenge-48](challenge-48.md) |
| L3-M03 | Dupla verificação | Médio | Cabeçalhos de resposta HTTP | [challenge-49](challenge-49.md) |
| L3-M04 | Arquivo de manutenção | Médio | Manifesto da aplicação web | [challenge-50](challenge-50.md) |
| L3-M05 | Prévia silenciosa | Médio | Metadados de recursos | [challenge-51](challenge-51.md) |
| L3-D01 | Trilha de auditoria | Difícil | Endpoints operacionais / auditoria | [challenge-52](challenge-52.md) |
| L3-D02 | Perfil de fornecedor | Difícil | Controle de acesso a recursos (IDOR) | [challenge-53](challenge-53.md) |
| L3-D03 | Protocolo de entrega | Difícil | Cadeia de redirecionamentos HTTP | [challenge-54](challenge-54.md) |
