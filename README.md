# Achador de Licitações — DOU Seção 3

Programa para consultar o Diário Oficial da União (Seção 3 — Contratos,
Editais e Avisos) em uma data escolhida, ver um panorama geral e baixar
um Excel com as colunas **DATA / TÍTULO / OBJETO / RESUMO BREVE** (mais
ÓRGÃO, TIPO DE ATO e um link direto para a matéria, que ajudam sem fugir
do pedido original).

Este repositório tem **duas formas de usar**, com o mesmo motor por trás
(`dou_scraper.py` + `gerar_excel.py`):

1. **App Flask local** (`app.py`) — página com campo de data e botão
   GERAR, resposta instantânea. Só roda enquanto você tiver o servidor
   ligado na sua máquina (ou hospedado em algum serviço como Render).
2. **Site estático no GitHub Pages + GitHub Actions** (pasta `docs/`) —
   não precisa de nenhum servidor ligado 24h; o GitHub Actions faz a
   busca no DOU e o GitHub Pages só mostra os resultados prontos. É o
   jeito de deixar isso **100% dentro do GitHub**, sem depender de
   Render/Railway/etc. Ver seção **"Publicar 100% no GitHub"** abaixo.

## Opção 1 — Rodar o app Flask localmente

```bash
pip install -r requirements.txt
python app.py
```

Depois abra `http://localhost:5000` no navegador, escolha uma data e
clique em **GERAR**.

## Opção 2 — Publicar 100% no GitHub (Actions + Pages)

Esse é o jeito de ter uma página web pública **sem pagar nada e sem sair
do GitHub**, no mesmo espírito do que foi feito no projeto Move Group.
A diferença é que aqui o site não pode buscar os dados do DOU sozinho no
navegador (o in.gov.br bloqueia isso por CORS), então quem faz a busca é
um workflow do **GitHub Actions**, e o **GitHub Pages** só exibe o
resultado já pronto (arquivos JSON/Excel dentro de `docs/dados/`).

### Passo a passo (uma vez só)

1. Crie um repositório novo no GitHub (pode ser público ou privado — se
   for privado, o GitHub Pages exige um plano pago; se puder, deixe
   público) e suba todo o conteúdo desta pasta nele.
2. Abra `docs/index.html` e troque a linha:
   ```js
   const REPO_GITHUB = "SEU_USUARIO/dou-licitacoes";
   ```
   pelo `usuario/nome-do-repositorio` de verdade. Suba essa alteração
   (commit + push).
3. No GitHub, vá em **Settings → Pages** do repositório. Em "Build and
   deployment", escolha **Source: Deploy from a branch**, branch
   **main**, pasta **/docs**. Salve.
4. Espere 1–2 minutos e o GitHub mostra o link do site (algo como
   `https://seu_usuario.github.io/dou-licitacoes/`). Essa é a página
   pública.
5. Para gerar a primeira consulta: vá na aba **Actions** do repositório
   → clique no workflow **"Gerar Consulta DOU"** na lista à esquerda →
   botão **"Run workflow"** → informe uma data no formato `AAAA-MM-DD`
   (ou deixe em branco para usar a data de hoje) → **Run workflow**.
6. Aguarde cerca de 1 minuto (acompanhe em Actions, vai aparecer um ✅
   quando terminar) e recarregue o site do passo 4: a data vai aparecer
   no seletor.

Depois disso, toda vez que você quiser uma nova data, repita o passo 5 —
ou simplesmente espere: o workflow também roda **sozinho, automaticamente,
todo dia útil às 9h05 (horário de Brasília)**, gerando a consulta do dia
sem precisar fazer nada.

### O que cada peça faz nesse modelo

- `.github/workflows/gerar-dou.yml` — o workflow do GitHub Actions. Roda
  `scripts/gerar_estatico.py`, e depois faz commit + push dos arquivos
  gerados de volta para o próprio repositório.
- `scripts/gerar_estatico.py` — a mesma lógica do `app.py`, mas em vez de
  responder a uma requisição HTTP, escreve os resultados em
  `docs/dados/<data>.json` e `docs/dados/<data>.xlsx` (mais um
  `docs/dados/index.json` com a lista de tudo que já foi gerado).
- `docs/index.html` — o site estático publicado pelo GitHub Pages. Lê o
  `index.json` para montar a lista de datas disponíveis e, ao escolher
  uma, busca o `.json` correspondente para montar o panorama e a prévia,
  além de linkar o `.xlsx` para download.
- `docs/usuarios/usuarios.xlsx` — planilha com os usuários que podem
  entrar no site (ver seção "Login" abaixo).

### Login (acesso restrito)

O site pede usuário e senha antes de mostrar qualquer conteúdo. As
credenciais válidas ficam na planilha `docs/usuarios/usuarios.xlsx`, com
duas colunas: `login` e `senha`. O usuário inicial já vem cadastrado:

| login | senha |
|-------|-------|
| admin | admin |

**Para adicionar, remover ou trocar a senha de um usuário:** abra
`docs/usuarios/usuarios.xlsx` direto no GitHub (ou baixe, edite no Excel
e suba de novo), adicione/edite as linhas e faça commit. Não precisa
mexer em nenhum outro arquivo — na próxima vez que alguém carregar o
site, a planilha atualizada já vale.

**Importante — isso não é segurança de verdade.** O site é 100%
estático e público (GitHub Pages não roda nenhum código no servidor), e
a checagem de usuário/senha é feita inteiramente no navegador: a
planilha com as senhas é um arquivo público do repositório, que
qualquer pessoa pode baixar diretamente pela URL, e uma pessoa com
conhecimento técnico pode abrir o "Inspecionar" do navegador e pular a
tela de login sem nem precisar da senha. Trate essa tela como uma
cortina simples para o link não ficar "escancarado" para qualquer
visitante casual — troque a senha padrão `admin`/`admin`, mas não
guarde aqui senhas que você usa em outros lugares nem dados realmente
sigilosos. Se um dia precisar de login de verdade (com senha
protegida), a solução exige um backend/servidor real, o que muda a
arquitetura "100% GitHub Pages" descrita aqui.

### Limitações desse modelo (comparado ao app Flask local)

- Não existe um botão "GERAR" que qualquer visitante do site possa
  clicar — só quem tem acesso de escrita ao repositório (você) consegue
  disparar o workflow pela aba Actions. Isso é intencional: uma página
  pública não pode ter permissão de gravar no seu repositório.
- A geração leva ~1 minuto (tempo de start do GitHub Actions), não é
  instantânea como no app Flask.
- Se quiser voltar a ter o "digite a data e clique GERAR" com resposta
  na hora para qualquer visitante, é preciso um servidor de verdade
  rodando — nesse caso, use a Opção 1 hospedada em algo como Render (ver
  seção "Publicar com servidor" mais abaixo). O código do repositório
  serve para os dois casos, sem duplicar nada.

## Como funciona a consulta ao DOU (importante para manutenção)

Diferente do que se costuma imaginar, **não existe um endpoint de busca
JSON separado e documentado**. O que descobri inspecionando ao vivo (F12
→ Network e o arquivo `main.js` do portlet "leituradou") é o seguinte:

A página `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=do3`
é renderizada inteiramente no servidor e já vem, embutida no próprio
HTML, com **todas** as matérias do dia/seção (não só as 10 da primeira
página visual), dentro de uma tag:

```html
<script id="params" type="application/json">
{
  "typeNormDay": {...},
  "idPortletInstance": "...",
  "dateUrl": "09-09-2026",
  "section": "DO3",
  "jsonArray": [ { ...matéria 1... }, { ...matéria 2... }, ... ]
}
</script>
```

A paginação, os filtros de órgão/tipo de ato e a busca que aparecem na
tela são feitos **inteiramente no navegador** (JavaScript), fatiando esse
`jsonArray` — não há nenhuma requisição de rede adicional quando você
clica em "Próximo" ou muda de página. Confirmei isso ao vivo em
09/09/2026: cliquei em várias páginas e o painel de rede do navegador não
registrou nenhuma chamada nova.

Por isso, `dou_scraper.py` faz uma única requisição HTTP `GET` a essa
URL e extrai o `jsonArray` de dentro do HTML (função
`_extrair_json_array`). Isso é mais simples e mais robusto do que tentar
imitar uma chamada AJAX não documentada — mas ainda é um detalhe de
implementação do site do in.gov.br, que pode mudar no futuro.

Cada item de `jsonArray` tem campos como `title`, `titulo`, `subTitulo`,
`content` (um resumo/prévia, geralmente truncado pelo próprio site com
"..."), `artType` (tipo do ato), `hierarchyStr` (caminho do órgão),
`pubDate`, `editionNumber`, `numberPage` e `urlTitle` (usado para montar
o link da matéria completa em `https://www.in.gov.br/web/dou/-/<urlTitle>`).

O campo **OBJETO** da planilha é extraído do texto de `content` por uma
expressão regular que procura o trecho depois de "Objeto:" (formato comum
nas publicações do DOU). Quando o padrão não é encontrado, cai no início
do próprio resumo como alternativa. O campo **RESUMO BREVE** é o próprio
`content`, limpo e limitado a ~280 caracteres.

### Se o site mudar (endpoint parar de funcionar)

O parsing foi escrito de forma defensiva (`_extrair_json_array` tenta três
estratégias diferentes antes de desistir) e levanta um erro claro
(`DouScraperError`) explicando o que aconteceu, em vez de travar
silenciosamente. Se mesmo assim parar de funcionar:

1. Abra `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=do3`
   no navegador com o DevTools aberto (F12 → aba **Network**).
2. Marque "Preserve log" e recarregue a página.
3. Veja se a estrutura do HTML mudou (procure por `id="params"` no
   código-fonte da página, `Ctrl+U`) ou se agora existe uma chamada AJAX
   separada retornando os dados (filtre por `Fetch/XHR`).
4. Ajuste `_extrair_json_array` em `dou_scraper.py` de acordo com o que
   encontrar.

### Alternativa oficial: INLABS

Se a "Leitura do Jornal" mudar de forma muito mais profunda, existe uma
alternativa **oficial e documentada** para consumo automatizado do DOU: o
**INLABS**, serviço da Imprensa Nacional que disponibiliza os arquivos
XML de cada edição (`https://inlabs.in.gov.br`). É mais trabalhoso de
integrar (requer cadastro/autenticação e parsing de XML em vez de JSON),
mas é a via suportada pelo próprio governo caso o scraping da página
pública deixe de ser viável.

## Filtro "somente licitação"

O painel tem uma caixa de seleção "Somente itens de licitação". Quando
marcada, filtra os itens cujo tipo de ato, título ou resumo contenham
palavras como "licitação", "pregão", "dispensa", "inexigibilidade",
"chamamento", "credenciamento", "concorrência" ou "leilão" (ver
`PALAVRAS_LICITACAO` em `dou_scraper.py`). Ajuste essa lista se quiser
refinar o filtro.

## Estrutura dos arquivos

- `app.py` — servidor Flask (rotas `/`, `/api/gerar`, `/api/download`) —
  usado na Opção 1 (local ou hospedado com servidor).
- `dou_scraper.py` — consulta e parsing do DOU (ver seção acima). Usado
  pelas duas opções.
- `gerar_excel.py` — monta o `.xlsx` (aba **Panorama** + aba **Relação**,
  com formatação navy/dourado, cabeçalho fixo e filtro automático). Usado
  pelas duas opções.
- `templates/index.html` — painel visual do app Flask (Opção 1): campo de
  data, checkbox de filtro, botão GERAR, cards de panorama, tabelas de
  contagem e prévia da relação.
- `scripts/gerar_estatico.py` — versão "linha de comando" da mesma
  consulta, usada pelo GitHub Actions na Opção 2 (ver acima).
- `.github/workflows/gerar-dou.yml` — workflow do GitHub Actions da
  Opção 2.
- `docs/index.html` — site estático publicado pelo GitHub Pages na
  Opção 2 (mesmo visual do `templates/index.html`, mas lê arquivos
  prontos em vez de chamar uma API).
- `docs/dados/` — onde a Opção 2 guarda os arquivos gerados
  (`index.json` + um `.json`/`.xlsx` por data consultada). Começa vazio;
  vai sendo preenchido conforme você roda o workflow.
- `tests/` — testes automatizados que **não dependem de internet**:
  - `fixture_dou_params.json`: um recorte real (6 itens) do `jsonArray`
    observado ao vivo no in.gov.br em 09/09/2026, usado para validar o
    parser sem precisar acessar a rede.
  - `test_scraper_offline.py`: testa a extração do JSON, o mapeamento
    para `MateriaDOU`, a extração do "Objeto:" e o filtro de licitação.
  - `test_app_offline.py`: testa as rotas do Flask de ponta a ponta,
    substituindo apenas a chamada HTTP real por uma resposta simulada a
    partir do fixture (usando `unittest.mock`).
  - `test_estatico_offline.py`: testa `scripts/gerar_estatico.py` (usado
    pelo GitHub Actions) da mesma forma, num diretório temporário.

Rode os testes com:

```bash
python tests/test_scraper_offline.py
python tests/test_app_offline.py
python tests/test_estatico_offline.py
```

## O que foi testado e o que falta testar de verdade

**Testado neste desenvolvimento:**
- A estrutura real da página do in.gov.br foi **inspecionada ao vivo no
  navegador** em 09/09/2026 (Network tab + código-fonte), confirmando o
  formato do `jsonArray` descrito acima.
- Toda a lógica de parsing, extração de "Objeto:", geração do Excel
  (Panorama + Relação, formatação, filtro automático) e as rotas Flask
  (`/`, `/api/gerar`, `/api/download`, tratamento de erros) foram
  testadas de ponta a ponta usando esse recorte real de dados.
- O servidor Flask sobe e responde normalmente (`python app.py`).

**Ainda não testado (o ambiente onde este código foi preparado não tem
acesso de rede ao in.gov.br):**
- A chamada HTTP real de `dou_scraper.py` para `in.gov.br` — ou seja, o
  `requests.get()` de verdade, na sua máquina. A estrutura foi confirmada
  navegando manualmente, mas vale rodar:

  ```bash
  python dou_scraper.py 09-09-2026
  ```

  e conferir se aparece a lista de matérias. Se dequé algum erro,
  provavelmente é porque o site mudou algo desde a inspeção — siga a
  seção "Se o site mudar" acima.
- Testar uma data sem publicação (fim de semana/feriado) para confirmar
  que o painel mostra "0 matérias encontradas" de forma amigável (o
  código já trata esse caso, mas não foi validado contra o site real).

## Publicar com servidor (para o app Flask com botão GERAR na hora)

Se preferir manter a experiência atual do app Flask (qualquer visitante
digita a data e clica GERAR, resposta instantânea) só que acessível pela
internet, algumas opções:
- **Render** ou **Railway**: conecte o repositório, defina o comando de
  start como `gunicorn app:app` (adicione `gunicorn` ao
  `requirements.txt`) e a porta pela variável de ambiente `PORT`.
- **PythonAnywhere**: suba os arquivos e configure uma Web App Flask
  apontando para `app.py`.
- **VPS próprio**: rode com `gunicorn -w 2 -b 0.0.0.0:8000 app:app` atrás
  de um Nginx como proxy reverso.

Em qualquer uma dessas opções, lembre-se de que o cache do último
resultado (`_ultimo_resultado` em `app.py`) é global e em memória — bom
para uso pessoal/local, mas se várias pessoas forem usar o site ao mesmo
tempo, cada uma pode acabar baixando o Excel da consulta de outra pessoa.
Nesse caso, vale trocar por algo com escopo de sessão.
