# -*- coding: utf-8 -*-
"""
Teste de integração do app Flask, SEM tocar a rede: usa unittest.mock para
substituir a chamada HTTP dentro de dou_scraper.consultar_dou por uma
resposta construída a partir do fixture real (fixture_dou_params.json).

Isso valida: rota /, rota /api/gerar (JSON de panorama/preview) e rota
/api/download (geração e download do .xlsx) de ponta a ponta, exercitando
o mesmo código que roda em produção — só a chamada de rede é simulada,
porque este ambiente de desenvolvimento não tem acesso ao in.gov.br.
"""
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixture_dou_params.json")


class RespostaFalsa:
    def __init__(self, texto):
        self.text = texto
        self.status_code = 200

    def raise_for_status(self):
        pass


def _html_da_fixture():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        fixture = json.load(f)
    return f"""<html><body>
    <script id="params" type="application/json">{json.dumps(fixture, ensure_ascii=False)}</script>
    </body></html>"""


def main():
    html_fake = _html_da_fixture()
    client = app_module.app.test_client()

    # 1) GET /
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Achador de Licita" in resp.data
    print("OK: GET / renderiza o painel (status 200).")

    # 2) POST /api/gerar (sem filtro)
    with patch("requests.Session.get", return_value=RespostaFalsa(html_fake)):
        resp = client.post(
            "/api/gerar",
            data=json.dumps({"data": "2026-09-09", "so_licitacao": False}),
            content_type="application/json",
        )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["total"] == 6, body
    assert len(body["preview"]) == 6
    assert body["contagem_tipo"]
    print(f"OK: POST /api/gerar sem filtro -> total={body['total']}")

    # 3) POST /api/gerar (somente licitação)
    with patch("requests.Session.get", return_value=RespostaFalsa(html_fake)):
        resp = client.post(
            "/api/gerar",
            data=json.dumps({"data": "2026-09-09", "so_licitacao": True}),
            content_type="application/json",
        )
    body2 = resp.get_json()
    assert body2["total"] == 4, body2  # 4 dos 6 itens do fixture são de licitação
    print(f"OK: POST /api/gerar com filtro so_licitacao -> total={body2['total']}")

    # 4) GET /api/download (usa o cache do último /api/gerar, que foi o filtrado)
    resp = client.get("/api/download")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(resp.data) > 1000
    saida = os.path.join(os.path.dirname(__file__), "download_teste.xlsx")
    with open(saida, "wb") as f:
        f.write(resp.data)
    print(f"OK: GET /api/download -> {len(resp.data)} bytes salvos em {saida}")

    # 5) Data inválida
    resp = client.post(
        "/api/gerar",
        data=json.dumps({"data": "não-é-uma-data"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    print("OK: data inválida retorna 400 com mensagem amigável.")

    # 6) Data futura
    resp = client.post(
        "/api/gerar",
        data=json.dumps({"data": "2099-01-01"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    print("OK: data futura é rejeitada com 400.")

    print("\nTodos os testes de integração (offline) passaram.")


if __name__ == "__main__":
    main()
