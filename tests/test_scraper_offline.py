# -*- coding: utf-8 -*-
"""
Teste offline do parser do dou_scraper.py.

Este teste NÃO acessa a internet: ele monta um HTML mínimo que reproduz a
estrutura real observada no in.gov.br (um <script id="params"
type="application/json"> contendo "jsonArray") e verifica se
_extrair_json_array / _item_para_materia funcionam corretamente.

A estrutura foi validada manualmente em 09/09/2026 navegando ao vivo em
https://www.in.gov.br/leiturajornal?data=09-09-2026&secao=do3 (ver README.md).
Este sandbox de desenvolvimento não tem acesso de rede ao in.gov.br, então
o teste de ponta a ponta (requests.get real) deve ser feito rodando
`python dou_scraper.py 09-09-2026` na máquina do usuário, com internet.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dou_scraper import _extrair_json_array, _item_para_materia, DouScraperError  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixture_dou_params.json")


def _montar_html_de_fixture(fixture: dict) -> str:
    return f"""
    <html><head></head><body>
    <script id="params" type="application/json">
    {json.dumps(fixture, ensure_ascii=False)}
    </script>
    </body></html>
    """


def test_extrai_json_array_ok():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        fixture = json.load(f)
    html = _montar_html_de_fixture(fixture)
    array = _extrair_json_array(html)
    assert len(array) == len(fixture["jsonArray"])
    assert array[0]["title"] == "EXTRATO DE TERMO ADITIVO Nº 11/2026 - UASG 110097"
    print("OK: extração do jsonArray funciona,", len(array), "itens.")


def test_item_para_materia():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        fixture = json.load(f)
    item_licitacao = next(
        i for i in fixture["jsonArray"] if "Licitação" in i["artType"]
    )
    materia = _item_para_materia(item_licitacao)
    assert materia.data == "09/09/2026"
    assert "AVISO DE LICITAÇÃO" in materia.titulo
    assert materia.orgao
    assert materia.is_licitacao()
    assert materia.objeto  # deve ter extraído algo do campo "Objeto:"
    print("OK: MateriaDOU montada corretamente:")
    print("  titulo:", materia.titulo)
    print("  orgao:", materia.orgao)
    print("  tipo_ato:", materia.tipo_ato)
    print("  objeto:", materia.objeto)
    print("  resumo_breve:", materia.resumo_breve[:100], "...")
    print("  url:", materia.url)


def test_erro_quando_nao_ha_params():
    html = "<html><body><p>página sem dados</p></body></html>"
    try:
        _extrair_json_array(html)
        raise AssertionError("Deveria ter levantado DouScraperError")
    except DouScraperError:
        print("OK: erro claro levantado quando #params não existe.")


def test_filtro_licitacao():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        fixture = json.load(f)
    materias = [_item_para_materia(i) for i in fixture["jsonArray"]]
    so_licitacao = [m for m in materias if m.is_licitacao()]
    print(f"OK: filtro de licitação: {len(so_licitacao)} de {len(materias)} itens.")
    assert 0 < len(so_licitacao) < len(materias)


if __name__ == "__main__":
    test_extrai_json_array_ok()
    test_item_para_materia()
    test_erro_quando_nao_ha_params()
    test_filtro_licitacao()
    print("\nTodos os testes offline passaram.")
