# -*- coding: utf-8 -*-
"""
app.py — Achador de Licitações (DOU Seção 3)

Servidor Flask com três rotas:
  GET  /            -> painel (templates/index.html)
  POST /api/gerar    -> consulta o DOU para a data informada e devolve um
                         panorama (JSON) + prévia da lista de matérias
  GET  /api/download -> baixa o .xlsx gerado na última chamada a /api/gerar

Como rodar:
    pip install -r requirements.txt
    python app.py
    (abra http://localhost:5000 no navegador)
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file

from dou_scraper import DouScraperError, consultar_dou
from gerar_excel import gerar_excel_bytes

app = Flask(__name__)

# Cache simples em memória do último resultado gerado, para permitir o
# download do Excel sem precisar consultar o DOU de novo. Como é uma
# ferramenta de uso local/pessoal, um cache global (sem sessão) é
# suficiente; se for publicar para múltiplos usuários simultâneos, troque
# por algo com escopo de sessão (flask.session + um armazenamento
# temporário por usuário).
_ultimo_resultado = {
    "data": None,          # date
    "so_licitacao": False,
    "materias": [],        # list[MateriaDOU]
    "xlsx_bytes": None,
}


@app.route("/")
def index():
    hoje = datetime.now().strftime("%Y-%m-%d")
    return render_template("index.html", hoje=hoje)


@app.route("/api/gerar", methods=["POST"])
def api_gerar():
    payload = request.get_json(silent=True) or {}
    data_str = payload.get("data")
    so_licitacao = bool(payload.get("so_licitacao", False))

    if not data_str:
        return jsonify({"erro": "Informe uma data."}), 400

    try:
        data_consulta = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"erro": "Data inválida. Use o seletor de data do formulário."}), 400

    if data_consulta > datetime.now().date():
        return jsonify({"erro": "Não é possível consultar uma data futura."}), 400

    try:
        materias = consultar_dou(data_consulta, secao=3)
    except DouScraperError as exc:
        return jsonify({"erro": str(exc)}), 502

    if so_licitacao:
        materias = [m for m in materias if m.is_licitacao()]

    xlsx_bytes = gerar_excel_bytes(materias, data_consulta, so_licitacao=so_licitacao)

    _ultimo_resultado["data"] = data_consulta
    _ultimo_resultado["so_licitacao"] = so_licitacao
    _ultimo_resultado["materias"] = materias
    _ultimo_resultado["xlsx_bytes"] = xlsx_bytes

    contagem_tipo = {}
    for m in materias:
        chave = m.tipo_ato or "(não informado)"
        contagem_tipo[chave] = contagem_tipo.get(chave, 0) + 1
    contagem_tipo_ordenada = sorted(contagem_tipo.items(), key=lambda x: x[1], reverse=True)

    contagem_orgao = {}
    for m in materias:
        chave = (m.orgao.split("/")[0] if m.orgao else "(não informado)")
        contagem_orgao[chave] = contagem_orgao.get(chave, 0) + 1
    contagem_orgao_ordenada = sorted(contagem_orgao.items(), key=lambda x: x[1], reverse=True)[:10]

    preview = [
        {
            "data": m.data,
            "titulo": m.titulo,
            "objeto": m.objeto,
            "resumo_breve": m.resumo_breve,
            "orgao": m.orgao,
            "tipo_ato": m.tipo_ato,
            "url": m.url,
        }
        for m in materias[:50]
    ]

    return jsonify(
        {
            "data": data_consulta.strftime("%d/%m/%Y"),
            "so_licitacao": so_licitacao,
            "total": len(materias),
            "contagem_tipo": contagem_tipo_ordenada,
            "contagem_orgao": contagem_orgao_ordenada,
            "preview": preview,
            "preview_truncada": len(materias) > len(preview),
        }
    )


@app.route("/api/download")
def api_download():
    if not _ultimo_resultado["xlsx_bytes"]:
        return jsonify({"erro": "Gere uma consulta antes de baixar o Excel."}), 400

    data_consulta = _ultimo_resultado["data"]
    nome_arquivo = f"dou_secao3_{data_consulta.strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        BytesIO(_ultimo_resultado["xlsx_bytes"]),
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
