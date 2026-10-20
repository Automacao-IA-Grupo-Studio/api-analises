#!/usr/bin/env python3
"""
ler_jobs.py — Utilitário CLI para inspecionar JSONs salvos em data/jobs/
════════════════════════════════════════════════════════════════════════
Uso:
  python3 ler_jobs.py                   → lista todos os JSONs
  python3 ler_jobs.py <arquivo.json>    → mostra detalhes de um job
  python3 ler_jobs.py --resumo          → resumo rápido de todos
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data" / "jobs"


def listar():
    arquivos = sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not arquivos:
        print("Nenhum job analisado ainda.")
        return
    print(f"\n{'─'*70}")
    print(f"{'Arquivo':<50} {'Analisado em':<20} {'Status'}")
    print(f"{'─'*70}")
    for f in arquivos:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ts   = data.get("analisado_em", "?")[:19]
            ok   = data.get("resumo", {}).get("encontrados", "?")
            tot  = data.get("resumo", {}).get("total", "?")
            print(f"{f.name:<50} {ts:<20} {ok}/{tot} campos")
        except Exception as e:
            print(f"{f.name:<50} {'ERRO':<20} {e}")
    print(f"{'─'*70}")
    print(f"Total: {len(arquivos)} job(s)\n")


def detalhar(caminho: str):
    try:
        data = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except FileNotFoundError:
        # Tenta em data/jobs/
        tentativa = DATA_DIR / caminho
        data = json.loads(tentativa.read_text(encoding="utf-8"))

    print(f"\n{'═'*60}")
    print(f"  Job: {data.get('pasta_raiz', '?')}")
    print(f"  Analisado em: {data.get('analisado_em', '?')[:19]}")
    print(f"{'═'*60}")

    # Checklist
    print("\n  CHECKLIST:")
    for item in data.get("checklist", []):
        icone = "☒" if item["alerta"] else "☐"
        cor   = "(!)" if item["alerta"] else "   "
        print(f"  {icone} {cor} {item['descricao']}")

    # Resultados
    print(f"\n  RESULTADOS ({data['resumo']['encontrados']}/{data['resumo']['total']}):")
    for r in data.get("resultados", []):
        status = r["status"]
        valor  = r.get("valor", "")
        campo  = r["campo"]
        if valor:
            print(f"  ✔  {campo:<30} {valor[:60]}")
        elif status == "nao_encontrado":
            print(f"  ✕  {campo:<30} [arquivo não encontrado]")
        else:
            print(f"  ⚠  {campo:<30} [arquivo ok, dado não extraído]")
    print()


def resumo():
    arquivos = sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    total_jobs = len(arquivos)
    if not total_jobs:
        print("Nenhum job.")
        return

    alertas_total = 0
    for f in arquivos:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            alertas_total += data.get("resumo", {}).get("alertas_checklist", 0)
        except Exception:
            pass

    print(f"\nTotal de jobs analisados: {total_jobs}")
    print(f"Total de alertas (checklist): {alertas_total}")
    print(f"Último: {arquivos[0].name if arquivos else 'nenhum'}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        listar()
    elif args[0] == "--resumo":
        resumo()
    else:
        detalhar(args[0])
