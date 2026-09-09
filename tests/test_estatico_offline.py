# -*- coding: utf-8 -*-
"""
Teste offline de scripts/gerar_estatico.py — o script usado pelo GitHub
Actions no modelo "só GitHub" (Actions + Pages). Roda em um diretório
temporário (não mexe em docs/dados/ de verdade) e usa unittest.mock para
não depender de internet.
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    tmp_dir = tempfile.mkdtemp(prefix="dou_teste_")
    try:
        import scripts.gerar_estatico as ge
        importlib.reload(ge)
        ge.DADOS_DIR = os.path.join(tmp_dir, "docs", "dados")

        html_fake = _html_da_fixture()

        with patch("requests.Session.get", return_value=RespostaFalsa(html_fake)):
            with patch.object(sys, "argv", ["gerar_estatico.py", "2026-09-09"]):
                ge.main()
            with patch.object(sys, "argv", ["gerar_estatico.py", "2026-09-09", "--so-licitacao"]):
                ge.main()

        arquivos = sorted(os.listdir(ge.DADOS_DIR))
        esperados = {
            "2026-09-09.json",
            "2026-09-09.xlsx",
            "2026-09-09_licitacao.json",
            "2026-09-09_licitacao.xlsx",
            "index.json",
        }
        assert esperados.issubset(set(arquivos)), arquivos
        print("OK: todos os arquivos esperados foram gerados:", arquivos)

        with open(os.path.join(ge.DADOS_DIR, "index.json"), encoding="utf-8") as f:
            indice = json.load(f)
        assert len(indice) == 2, indice
        totais = {(e["data_iso"], e["so_licitacao"]): e["total"] for e in indice}
        assert totais[("2026-09-09", False)] == 6
        assert totais[("2026-09-09", True)] == 4
        print("OK: index.json tem as duas entradas com os totais corretos.")

        with open(os.path.join(ge.DADOS_DIR, "2026-09-09.json"), encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["total"] == 6
        assert len(payload["preview"]) == 6
        print("OK: JSON da consulta sem filtro tem os 6 itens completos.")

        # Rodar de novo para a mesma data não deve duplicar entradas no índice.
        with patch("requests.Session.get", return_value=RespostaFalsa(html_fake)):
            with patch.object(sys, "argv", ["gerar_estatico.py", "2026-09-09"]):
                ge.main()
        with open(os.path.join(ge.DADOS_DIR, "index.json"), encoding="utf-8") as f:
            indice2 = json.load(f)
        assert len(indice2) == 2, indice2
        print("OK: reexecutar a mesma data atualiza em vez de duplicar no índice.")

        print("\nTodos os testes de gerar_estatico.py (offline) passaram.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
