# -*- coding: utf-8 -*-
"""
gerar_estatico.py — usado pelo GitHub Actions (.github/workflows/gerar-dou.yml)

Roda a mesma consulta ao DOU que o app.py faz, mas em vez de responder a
uma requisição HTTP, escreve os resultados como arquivos estáticos dentro
de docs/dados/, que o GitHub Pages serve diretamente. Assim, todo o
"servidor" vira uma execução do GitHub Actions, e o site (docs/index.html)
só lê arquivos prontos — sem precisar de nenhum backend rodando 24h.

Uso:
    python scripts/gerar_estatico.py 2026-09-09
    python scripts/gerar_estatico.py 2026-09-09 --so-licitacao

Gera, dentro de docs/dados/:
    2026-09-09.json              (ou 2026-09-09_licitacao.json)
    2026-09-09.xlsx              (ou 2026-09-09_licitacao.xlsx)
    index.json                   (lista de todas as consultas já geradas)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dou_scraper import DouScraperError, consultar_dou  # noqa: E402
from gerar_excel import gerar_excel_bytes  # noqa: E402

DADOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "dados"
)


def _slug(data_str: str, so_licitacao: bool) -> str:
    return f"{data_str}_licitacao" if so_licitacao else data_str


def _montar_payload(materias, data_consulta, so_licitacao):
    contagem_tipo = {}
    for m in materias:
        chave = m.tipo_ato or "(não informado)"
        contagem_tipo[chave] = contagem_tipo.get(chave, 0) + 1
    contagem_tipo_ordenada = sorted(contagem_tipo.items(), key=lambda x: x[1], reverse=True)

    contagem_orgao = {}
    for m in materias:
        chave = m.orgao.split("/")[0] if m.orgao else "(não informado)"
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
        for m in materias
    ]

    return {
        "data": data_consulta.strftime("%d/%m/%Y"),
        "data_iso": data_consulta.strftime("%Y-%m-%d"),
        "so_licitacao": so_licitacao,
        "total": len(materias),
        "contagem_tipo": contagem_tipo_ordenada,
        "contagem_orgao": contagem_orgao_ordenada,
        "preview": preview,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }


def _atualizar_index(entry: dict):
    index_path = os.path.join(DADOS_DIR, "index.json")
    indice = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            try:
                indice = json.load(f)
            except json.JSONDecodeError:
                indice = []

    indice = [
        e
        for e in indice
        if not (e.get("data_iso") == entry["data_iso"] and e.get("so_licitacao") == entry["so_licitacao"])
    ]
    indice.append(entry)
    indice.sort(key=lambda e: (e["data_iso"], e["so_licitacao"]), reverse=True)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Gera JSON+XLSX estáticos de uma consulta ao DOU.")
    parser.add_argument("data", help="Data no formato AAAA-MM-DD")
    parser.add_argument("--so-licitacao", action="store_true", help="Filtrar somente itens de licitação")
    args = parser.parse_args()

    try:
        data_consulta = datetime.strptime(args.data, "%Y-%m-%d").date()
    except ValueError:
        print(f"ERRO: data inválida '{args.data}'. Use o formato AAAA-MM-DD.", file=sys.stderr)
        sys.exit(1)

    if data_consulta > datetime.now().date():
        print("ERRO: não é possível consultar uma data futura.", file=sys.stderr)
        sys.exit(1)

    print(f"Consultando DOU Seção 3 para {data_consulta.strftime('%d/%m/%Y')}...")
    try:
        materias = consultar_dou(data_consulta, secao=3)
    except DouScraperError as exc:
        print(f"ERRO ao consultar o DOU: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.so_licitacao:
        materias = [m for m in materias if m.is_licitacao()]

    print(f"{len(materias)} matéria(s) encontrada(s)"
          f"{' (filtro: somente licitação)' if args.so_licitacao else ''}.")

    os.makedirs(DADOS_DIR, exist_ok=True)
    base = _slug(args.data, args.so_licitacao)

    xlsx_bytes = gerar_excel_bytes(materias, data_consulta, so_licitacao=args.so_licitacao)
    xlsx_path = os.path.join(DADOS_DIR, f"{base}.xlsx")
    with open(xlsx_path, "wb") as f:
        f.write(xlsx_bytes)
    print(f"Excel salvo em {xlsx_path}")

    payload = _montar_payload(materias, data_consulta, args.so_licitacao)
    json_path = os.path.join(DADOS_DIR, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"JSON salvo em {json_path}")

    _atualizar_index(
        {
            "data_iso": args.data,
            "data": data_consulta.strftime("%d/%m/%Y"),
            "so_licitacao": args.so_licitacao,
            "total": len(materias),
            "arquivo_json": f"{base}.json",
            "arquivo_xlsx": f"{base}.xlsx",
            "gerado_em": payload["gerado_em"],
        }
    )
    print("index.json atualizado.")


if __name__ == "__main__":
    main()
