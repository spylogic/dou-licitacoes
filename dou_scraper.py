# -*- coding: utf-8 -*-
"""
dou_scraper.py
Consulta a Leitura do Jornal do Diário Oficial da União (in.gov.br) para uma
data e seção específicas, e retorna a lista de matérias publicadas.

DESCOBERTA IMPORTANTE (documentada aqui para quem for dar manutenção):
A página https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=doN é
renderizada no servidor (Liferay) e já traz, embutido no próprio HTML, um
bloco:

    <script id="params" type="application/json">
        { "typeNormDay": {...}, "dateUrl": "...", "section": "...",
          "jsonArray": [ { ...matéria 1... }, { ...matéria 2... }, ... ] }
    </script>

O "jsonArray" contém TODAS as matérias do dia/seção (não só as 10 da
primeira página visual) — a paginação e os filtros da página são feitos
inteiramente no navegador (JavaScript), sem nenhuma requisição adicional.
Isso foi confirmado inspecionando o arquivo main.js do portlet
"leituradou" e observando o tráfego de rede ao navegar/paginar no site.

Ou seja: não existe (nem é necessário) um endpoint de busca separado —
basta baixar essa página normalmente e extrair o JSON do elemento
#params. Essa abordagem é mais robusta do que tentar imitar uma chamada
AJAX não documentada, mas ainda assim é um detalhe de implementação do
site que pode mudar. Por isso o parsing abaixo é defensivo: se a
estrutura mudar, uma exceção clara (DouScraperError) é levantada, e o
README traz um caminho alternativo (INLABS).

Cada item de "jsonArray" tem campos como:
    pubName          -> ex: "DO3" (seção)
    urlTitle         -> slug usado na URL da matéria completa
    numberPage       -> página da edição impressa
    subTitulo/titulo -> subtítulo/título adicionais (nem sempre preenchidos)
    title            -> título principal (ex: "AVISO DE LICITAÇÃO")
    pubDate          -> data de publicação (DD/MM/AAAA)
    content          -> resumo/prévia do conteúdo (truncado pelo site)
    editionNumber    -> número da edição do DOU
    artType          -> tipo do ato (ex: "Aviso de Licitação-Pregão")
    pubOrder         -> chave de ordenação interna
    hierarchyStr     -> caminho hierárquico do órgão (separado por "/")
    hierarchyList    -> mesmo caminho, como lista
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.in.gov.br/leiturajornal"

# Seções do DOU. A seção 3 é a de "Contratos, Editais e Avisos" (licitações).
SECOES = {
    1: "do1",
    2: "do2",
    3: "do3",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Palavras-chave usadas para identificar itens relacionados a licitação
# quando o usuário opta por filtrar (ver app.py, parâmetro "so_licitacao").
PALAVRAS_LICITACAO = [
    "licita",
    "pregão",
    "pregao",
    "dispensa",
    "inexigibilidade",
    "chamamento",
    "credenciamento",
    "concorrência",
    "concorrencia",
    "leilão",
    "leilao",
]


class DouScraperError(Exception):
    """Erro ao consultar ou interpretar a página do DOU."""


@dataclass
class MateriaDOU:
    data: str  # DD/MM/AAAA
    titulo: str
    orgao: str
    tipo_ato: str
    objeto: str
    resumo_breve: str
    edicao: str = ""
    pagina: str = ""
    url: str = ""

    def is_licitacao(self) -> bool:
        alvo = f"{self.tipo_ato} {self.titulo} {self.resumo_breve}".lower()
        return any(p in alvo for p in PALAVRAS_LICITACAO)


def _formatar_data_br(data: date_cls) -> str:
    return data.strftime("%d-%m-%Y")


def _extrair_objeto(content: str) -> str:
    """Tenta extrair a parte "Objeto: ..." do texto de prévia.

    O campo "content" retornado pelo DOU normalmente é um texto corrido,
    do tipo "AVISO DE LICITAÇÃO ... Objeto: fornecimento de ... Data de
    abertura: ...". Fazemos uma extração best-effort; se não encontrar o
    padrão "Objeto:", devolve o próprio texto (truncado) como fallback.
    """
    if not content:
        return ""

    padrao = re.search(
        r"objeto\s*[:\-]\s*(.+?)(?:\.\s{2,}|\.?\s*(?:data\s+de\s+|valor\s*(?:total)?\s*[:\-]|"
        r"n[uú]mero\s+do\s+processo|processo\s*n[ºo]|vig[eê]ncia\s*[:\-]|"
        r"contratante\s*[:\-]|contratado\s*[:\-]|modalidade\s*[:\-]|"
        r"forma\s+de\s+apresenta[cç][ãa]o|endere[cç]o\s+eletr[oô]nico)\b|$)",
        content,
        flags=re.IGNORECASE,
    )
    if padrao:
        objeto = padrao.group(1).strip(" .")
        if objeto:
            return objeto[:500]

    return content[:300].strip()


def _limpar_resumo(content: str, tamanho: int = 280) -> str:
    if not content:
        return ""
    texto = re.sub(r"\s+", " ", content).strip()
    if texto.endswith("..."):
        texto = texto[:-3].rstrip()
    if len(texto) > tamanho:
        texto = texto[:tamanho].rsplit(" ", 1)[0] + "..."
    return texto


def _montar_titulo(item: dict) -> str:
    titulo = (item.get("title") or "").strip()
    titulo_extra = (item.get("titulo") or "").strip()
    subtitulo = (item.get("subTitulo") or "").strip()
    partes = [p for p in [titulo, titulo_extra, subtitulo] if p]
    # Evita duplicar quando "titulo" repete o "title"
    texto = " - ".join(dict.fromkeys(partes))
    return texto or "(sem título)"


def _montar_url(item: dict) -> str:
    url_title = item.get("urlTitle")
    if url_title:
        return f"https://www.in.gov.br/web/dou/-/{url_title}"
    return ""


def _item_para_materia(item: dict) -> MateriaDOU:
    content = item.get("content") or ""
    return MateriaDOU(
        data=item.get("pubDate", ""),
        titulo=_montar_titulo(item),
        orgao=item.get("hierarchyStr", ""),
        tipo_ato=item.get("artType", ""),
        objeto=_extrair_objeto(content),
        resumo_breve=_limpar_resumo(content),
        edicao=str(item.get("editionNumber", "")),
        pagina=str(item.get("numberPage", "")),
        url=_montar_url(item),
    )


def _extrair_json_array(html: str) -> list:
    """Extrai o array de matérias embutido no HTML da página.

    Estratégia principal: procurar <script id="params" type="application/json">.
    Estratégias alternativas (defensivas, caso o site mude o id/estrutura):
      1. Qualquer <script type="application/json"> que contenha "jsonArray".
      2. Busca por regex direta no HTML bruto por "jsonArray":[...].
    """
    soup = BeautifulSoup(html, "html.parser")

    candidatos = []
    tag_params = soup.find("script", id="params")
    if tag_params is not None:
        candidatos.append(tag_params.string or tag_params.get_text())

    if not candidatos:
        for tag in soup.find_all("script", attrs={"type": "application/json"}):
            texto = tag.string or tag.get_text()
            if texto and "jsonArray" in texto:
                candidatos.append(texto)

    for texto in candidatos:
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(dados, dict) and "jsonArray" in dados:
            return dados.get("jsonArray") or []

    # Último recurso: regex direta no HTML bruto.
    match = re.search(r'"jsonArray"\s*:\s*(\[.*?\])\s*[,}]', html, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise DouScraperError(
        "Não foi possível localizar a lista de matérias (jsonArray) no HTML "
        "retornado pelo in.gov.br. O site pode ter mudado de estrutura. "
        "Consulte o README.md (seção 'Se o site mudar') para o passo a "
        "passo de investigação com o F12/Network do navegador, ou use a "
        "alternativa oficial via INLABS."
    )


def consultar_dou(
    data: date_cls,
    secao: int = 3,
    timeout: int = 30,
    session: Optional[requests.Session] = None,
) -> List[MateriaDOU]:
    """Consulta o DOU para a data e seção informadas.

    Retorna uma lista de MateriaDOU (pode ser vazia, por exemplo em finais
    de semana/feriados, quando não há edição publicada).
    """
    if secao not in SECOES:
        raise ValueError(f"Seção inválida: {secao}. Use 1, 2 ou 3.")

    data_str = _formatar_data_br(data)
    params = {"data": data_str, "secao": SECOES[secao]}

    http = session or requests.Session()
    try:
        resp = http.get(BASE_URL, params=params, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise DouScraperError(
            f"Falha ao acessar o in.gov.br: {exc}. Verifique sua conexão "
            "com a internet ou tente novamente em alguns instantes."
        ) from exc

    json_array = _extrair_json_array(resp.text)

    materias = [_item_para_materia(item) for item in json_array]
    return materias


if __name__ == "__main__":
    # Teste manual rápido: python dou_scraper.py [DD-MM-AAAA]
    import sys

    if len(sys.argv) > 1:
        d = date_cls.fromisoformat(
            "-".join(reversed(sys.argv[1].split("-")))
        )  # aceita DD-MM-AAAA
    else:
        d = date_cls.today()

    resultado = consultar_dou(d, secao=3)
    print(f"Total de matérias em {d.strftime('%d/%m/%Y')}, Seção 3: {len(resultado)}")
    for m in resultado[:5]:
        print("-" * 60)
        print("Título:", m.titulo)
        print("Órgão:", m.orgao)
        print("Tipo:", m.tipo_ato)
        print("Objeto:", m.objeto[:150])
