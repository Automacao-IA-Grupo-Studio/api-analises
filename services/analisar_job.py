#!/usr/bin/env python3
"""
analisar_job.py — Serviço headless de análise de documentos
════════════════════════════════════════════════════════════
Uso:   python3 analisar_job.py <pasta_raiz>
Saída: JSON no stdout  |  Logs de progresso no stderr

Adaptado de analisador.py (Studio Fiscal v2.0)
⚠  SOMENTE LEITURA — nunca altera, move ou exclui arquivos.
"""

import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime

# ── Importações com tratamento de erro claro ──────────────────────────────────
try:
    import pdfplumber
except ImportError:
    print(json.dumps({"erro": "pdfplumber não instalado. Execute: pip install pdfplumber"}))
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  ELEMENTOS DE ANÁLISE  (idêntico ao analisador.py original)
# ══════════════════════════════════════════════════════════════════════════════
ELEMENTOS: list[dict] = [
    # ── CONTRATO ─────────────────────────────────────────────────────────────
    {
        "id": "contrato_existe",
        "categoria": "Contrato",
        "campo": "Contrato Assinado",
        "descricao": "PDF de contrato em A - Contrato › 1 - Contrato Studio",
        "pasta": ["A - Contrato", "1 - Contrato Studio"],
        "extensao": [".pdf"],
        "regex": [],
        "tipo": "existencia",
    },
    {
        "id": "procuracao_existe",
        "categoria": "Contrato",
        "campo": "Procuração",
        "descricao": "PDF de procuração em A - Contrato › 2 - Procurações",
        "pasta": ["A - Contrato", "2 - Procura"],
        "extensao": [".pdf"],
        "regex": [],
        "tipo": "existencia",
    },
    {
        "id": "honorarios",
        "categoria": "Contrato",
        "campo": "Honorários (%)",
        "descricao": "Percentual de honorários do GS (Cláusula 5.1)",
        "pasta": ["A - Contrato"],
        "arquivo_contem": ["Contrato"],
        "extensao": [".pdf"],
        "regex": [
            r"(?:honor[aá]rios|cl[aá]usula\s*5[\s\.,]?)[\s\S]{0,500}?(\d{1,3}(?:[\.,]\d{1,4})?)\s*%",
            r"(\d{1,3}(?:[\.,]\d{1,4})?)\s*%[^\n]{0,150}(?:honor[aá]rios|remunera[çc][aã]o)",
            r"remunera[çc][aã]o[\s\S]{0,300}?(\d{1,3}(?:[\.,]\d{1,4})?)\s*%",
            r"(?:honor[aá]rios|remunera[çc][aã]o)[\s\S]{0,600}?\((\d{1,3}(?:[\.,]\d{1,4})?)\s*%\)",
        ],
    },
    {
        "id": "gross_up",
        "categoria": "Contrato",
        "campo": "Gross Up",
        "descricao": "Comissão extra sobre honorários",
        "pasta": ["A - Contrato"],
        "arquivo_contem": ["Contrato"],
        "extensao": [".pdf"],
        "regex": [
            r"gross[\s\-]?up[^%\n]{0,200}?(\d{1,3}[\.,]\d{1,4})\s*%",
            r"(\d{1,3}[\.,]\d{1,4})\s*%[^%\n]{0,80}gross[\s\-]?up",
            r"14[,\.]25\s*%",
        ],
    },
    {
        "id": "passivo",
        "categoria": "Contrato",
        "campo": "Passivo",
        "descricao": "Menção a passivos a serem realizados",
        "pasta": ["A - Contrato"],
        "arquivo_contem": ["Contrato"],
        "extensao": [".pdf"],
        "regex": [r"(passivo[s]?[^.\n]{0,300})"],
        "tipo": "booleano",
    },

    # ── QSA / RECEITA FEDERAL ─────────────────────────────────────────────────
    {
        "id": "data_abertura",
        "categoria": "QSA",
        "campo": "Data de Abertura",
        "descricao": "Data de constituição (CNPJ Matriz)",
        "pasta": ["B - Documentos", "5 - Cliente", "16 - CNPJ"],
        "arquivo_contem": ["CNPJ", "MATRIZ"],
        "arquivo_nao_contem": ["QSA", "Optantes", "Consulta"],
        "extensao": [".pdf"],
        "regex": [
            r"constitui[çc][aã]o[\s\S]{0,80}?(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
            r"data\s*de\s*constitui[çc][aã]o\s*:?\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
            r"data\s*de\s*abertura[\s\S]{0,60}?(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
            r"abertura\s*:?\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
            r"constitu[íi]da\s*em\s*:?\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
            r"\b(\d{2}\/\d{2}\/\d{4})\b",
        ],
    },
    {
        "id": "simples_nacional",
        "categoria": "QSA",
        "campo": "Simples Nacional",
        "descricao": "Situação no Simples Nacional e SIMEI",
        "pasta": ["B - Documentos", "5 - Cliente", "16 - CNPJ"],
        "arquivo_contem": ["Optantes", "Consulta"],
        "extensao": [".pdf"],
        "regex": [
            r"simples\s*nacional\s*:?\s*((?:n[aã]o\s*)?optante[^\n\r]{0,70})",
            r"(n[aã]o\s*optante\s*pelo\s*simples\s*nacional)",
            r"(optante\s*pelo\s*simples\s*nacional(?!\s*n[aã]o))",
            r"simei\s*:?\s*(n[aã]o\s*enquadrado[^\n\r]{0,40}|enquadrado[^\n\r]{0,40})",
            r"per[íi]odos?\s*anteriores?\s*:?\s*(.{5,80}?)(?:\n|$)",
        ],
        "tipo": "multiplo",
    },
    {
        "id": "socios",
        "categoria": "QSA",
        "campo": "Sócios (QSA)",
        "descricao": "Sócios e administradores — nome e qualificação",
        "pasta": ["B - Documentos", "5 - Cliente", "16 - CNPJ"],
        "arquivo_contem": ["QSA"],
        "extensao": [".pdf"],
        "regex": [
            r"\d{3}\.\d{3}\.\d{3}-\d{2}",
            r"\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}",
            r"(?:Nome/Nome\s*Empresarial|Nome\s*Empresarial)\s*:\s*\n?\s*([A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛÇ][^\n\r]{4,70})",
            r"Qualifica[çc][aã]o\s*:\s*\n?\s*([^\n\r]{5,80})",
            r"\n([A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛÇ]{2,}(?:\s+[A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛÇ]{2,}){2,})\n",
        ],
        "tipo": "multiplo",
    },

    # ── SITUAÇÃO FISCAL ───────────────────────────────────────────────────────
    {
        "id": "situacao_fiscal",
        "categoria": "Situação Fiscal",
        "campo": "Certidão Federal",
        "descricao": "Tipo de certidão (Negativa, PEFN ou Positiva)",
        "pasta": ["B - Documentos", "2 - Fiscal", "6 - Situação Fiscal"],
        "extensao": [".pdf"],
        "regex": [
            r"(CERTID[ÃA]O\s+POSITIVA\s+COM\s+EFEITOS\s+DE\s+NEGATIVA[^\n\r]{0,80})",
            r"(CERTID[ÃA]O\s+NEGATIVA\s+DE\s+D[ÉE]BITOS[^\n\r]{0,80})",
            r"(CERTID[ÃA]O\s+POSITIVA\s+DE\s+D[ÉE]BITOS[^\n\r]{0,80})",
            r"(?:situa[çc][aã]o|status)\s*(?:fiscal|de\s*d[ée]bitos)[:\s]+([^\n\r]{5,80})",
        ],
    },
    {
        "id": "regularize",
        "categoria": "Situação Fiscal",
        "campo": "Regularize",
        "descricao": "Arquivo SEM CADASTRO REGULARIZE na pasta Situação Fiscal",
        "pasta": ["B - Documentos", "2 - Fiscal", "6 - Situação Fiscal"],
        "arquivo_contem": ["REGULARIZE"],
        "extensao": [],
        "regex": [],
        "tipo": "existencia_alerta",
    },

    # ── PERFIL PREVIDENCIÁRIO ─────────────────────────────────────────────────
    {
        "id": "perfil",
        "categoria": "Perfil Prev.",
        "campo": "Perfil Previdenciário",
        "descricao": "Acima ou abaixo do limiar previdenciário",
        "pasta": ["B - Documentos", "6 - Cruzamentos"],
        "arquivo_contem": ["perfil"],
        "extensao": [".pdf", ".xlsx", ".xls", ".txt"],
        "regex": [
            r"(acima\s*do\s*limiar)",
            r"(abaixo\s*do\s*limiar)",
            r"limiar[:\s]+(acima|abaixo)",
            r"(acima|abaixo)[^.\n]{0,50}limiar",
        ],
    },

    # ── FATURAMENTO ───────────────────────────────────────────────────────────
    {
        "id": "faturamento",
        "categoria": "Faturamento",
        "campo": "Faturamento por Ano",
        "descricao": "Total por ano (arquivo ECF) + média",
        "pasta": ["B - Documentos", "1 - Contábil", "5 - ECF"],
        "arquivo_contem": ["FATURAMENTO"],
        "extensao": [".txt"],
        "regex": [
            r"TOTAL\s*DO\s*ARQUIVO[^\d]{0,20}([0-9]+[,\.]?[0-9]*(?:[,\.][0-9]+)?)",
            r"(?:receita|faturamento)\s*(?:bruta|total)?[:\s]+([0-9]+[,\.]?[0-9]*(?:[,\.][0-9]+)?)",
        ],
        "tipo": "multiplo",
    },
    {
        "id": "fastpass",
        "categoria": "Faturamento",
        "campo": "Fastpass (≥ R$ 20M)",
        "descricao": "Faturamento médio acima de R$ 20 milhões?",
        "pasta": ["B - Documentos", "1 - Contábil", "5 - ECF"],
        "arquivo_contem": ["FATURAMENTO"],
        "extensao": [".txt"],
        "regex": [],
        "tipo": "derivado_fastpass",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  BUSCA DE ARQUIVOS
# ══════════════════════════════════════════════════════════════════════════════
def _contem_todos(nome: str, termos: list[str]) -> bool:
    n = nome.lower()
    return all(t.lower() in n for t in termos)


def _nao_contem(nome: str, termos: list[str]) -> bool:
    n = nome.lower()
    return not any(t.lower() in n for t in termos)


def encontrar_arquivos(raiz: str, elemento: dict) -> list[str]:
    pastas_alvo    = elemento.get("pasta", [])
    arq_contem     = elemento.get("arquivo_contem", [])
    arq_nao_contem = elemento.get("arquivo_nao_contem", [])
    extensoes      = {e.lower() for e in elemento.get("extensao", [])}
    resultados: list[str] = []

    _log(f"      [busca] pasta={pastas_alvo} | contem={arq_contem} | ext={list(extensoes) or 'qualquer'}")

    for dirpath, _dirs, filenames in os.walk(raiz):
        partes = [p.lower() for p in Path(dirpath).parts]
        if not all(any(alvo.lower() in p for p in partes) for alvo in pastas_alvo):
            continue
        for fname in filenames:
            if extensoes and Path(fname).suffix.lower() not in extensoes:
                continue
            if arq_contem and not _contem_todos(fname, arq_contem):
                continue
            if arq_nao_contem and not _nao_contem(fname, arq_nao_contem):
                continue
            caminho_completo = os.path.join(dirpath, fname)
            _log(f"      [✓] {caminho_completo}")
            resultados.append(caminho_completo)

    if not resultados:
        _log(f"      [✗] nenhum arquivo encontrado")

    return resultados


# ══════════════════════════════════════════════════════════════════════════════
#  OCR VIA TESSERACT
# ══════════════════════════════════════════════════════════════════════════════
def _garantir_tesseract() -> bool:
    """Localiza Tesseract no Windows ou Linux/Docker."""
    import shutil

    # Docker / Linux: tesseract instalado via apt
    if shutil.which("tesseract"):
        return True

    # Windows: caminhos padrão
    if os.name == 'nt':
        for p in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.exists(p):
                try:
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = p
                except ImportError:
                    pass
                return True

    _log("      [ocr] Tesseract não encontrado. Instale via:")
    _log("            Linux/Docker: apt-get install tesseract-ocr tesseract-ocr-por")
    _log("            Windows: winget install UB-Mannheim.TesseractOCR")
    return False


def _ocr_pdf(caminho: str) -> str:
    _log("      [ocr] PDF sem texto — ativando OCR Tesseract...")
    if not _garantir_tesseract():
        return ""
    try:
        import pymupdf as fitz  # nova API (evita warning no stdout)
    except ImportError:
        try:
            import fitz  # fallback versão antiga
        except ImportError:
            _log("      [ocr] pymupdf não instalado")
            return ""
    try:
        from PIL import Image
    except ImportError:
        _log("      [ocr] Pillow não instalado")
        return ""
    try:
        import pytesseract
    except ImportError:
        _log("      [ocr] pytesseract não instalado")
        return ""
    import io

    try:
        doc = fitz.open(caminho)
        partes: list[str] = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                txt = pytesseract.image_to_string(img, lang="por")
            except Exception:
                txt = pytesseract.image_to_string(img)
            partes.append(txt)
            _log(f"      [ocr] página {i+1}: {len(txt)} chars")
        doc.close()
        resultado = "\n".join(partes)
        if resultado.strip():
            _log(f"      [ocr] total {len(resultado)} chars extraídos")
        return resultado
    except Exception as e:
        _log(f"      [ocr] ERRO: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRAÇÃO DE TEXTO
# ══════════════════════════════════════════════════════════════════════════════
def extrair_texto(caminho: str) -> str:
    ext  = Path(caminho).suffix.lower()
    nome = os.path.basename(caminho)
    _log(f"      [lendo] {nome}")
    try:
        if ext == ".pdf":
            partes: list[str] = []
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        partes.append(t)
            texto = "\n".join(partes)
            if texto.strip():
                _log(f"      [pdf] {len(texto)} chars (pdfplumber)")
                return texto

            try:
                try:
                    import pymupdf as fitz  # nova API (evita warning no stdout)
                except ImportError:
                    import fitz
                doc = fitz.open(caminho)
                texto2 = "\n".join(p.get_text() for p in doc)
                doc.close()
                if texto2.strip():
                    _log(f"      [pdf] {len(texto2)} chars (pymupdf)")
                    return texto2
            except Exception as e:
                _log(f"      [pymupdf] erro: {e}")

            return _ocr_pdf(caminho)

        elif ext == ".txt":
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    with open(caminho, "r", encoding=enc, errors="strict") as f:
                        texto = f.read()
                    _log(f"      [txt] {len(texto)} chars")
                    return texto
                except UnicodeDecodeError:
                    continue
            with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(caminho, data_only=True)
                linhas: list[str] = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        linha = " ".join(str(c) for c in row if c is not None)
                        if linha.strip():
                            linhas.append(linha)
                texto = "\n".join(linhas)
                _log(f"      [xlsx] {len(linhas)} linhas")
                return texto
            except Exception as e:
                _log(f"      [xlsx] ERRO: {e}")
                return ""

        else:
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    with open(caminho, "r", encoding=enc, errors="strict") as f:
                        return f.read()
                except (UnicodeDecodeError, OSError):
                    continue
            return ""

    except Exception as e:
        _log(f"      [ERRO] {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  APLICAÇÃO DE REGEX
# ══════════════════════════════════════════════════════════════════════════════
def aplicar_regex(texto: str, elemento: dict) -> tuple[str, str]:
    padroes = elemento.get("regex", [])
    tipo    = elemento.get("tipo", "simples")

    def _trecho(m: re.Match, txt: str) -> str:
        inicio = max(0, m.start() - 60)
        fim    = min(len(txt), m.end() + 160)
        return "..." + txt[inicio:fim].replace("\n", " ").strip() + "..."

    if tipo == "booleano":
        for p in padroes:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                return "Sim (mencionado no contrato)", _trecho(m, texto)
        return "", ""

    elif tipo == "multiplo":
        encontrados: list[str] = []
        trechos: list[str]     = []
        vistos: set[str]       = set()
        for p in padroes:
            for m in re.finditer(p, texto, re.IGNORECASE):
                val = " | ".join(g for g in m.groups() if g) if m.groups() else m.group(0)
                val = val.strip()
                if val and val not in vistos:
                    vistos.add(val)
                    encontrados.append(val)
                    trechos.append(_trecho(m, texto))
        if encontrados:
            return "\n".join(encontrados[:15]), "\n---\n".join(trechos[:15])
        return "", ""

    else:
        for p in padroes:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                val = next((g for g in (m.groups() or []) if g), m.group(0))
                return val.strip(), _trecho(m, texto)
        return "", ""


# ══════════════════════════════════════════════════════════════════════════════
#  FASTPASS
# ══════════════════════════════════════════════════════════════════════════════
def _calcular_fastpass(resultados: list[dict]) -> str:
    fat = next((r for r in resultados if r["id"] == "faturamento"), None)
    if not fat or not fat.get("valor"):
        return ""
    numeros_str = re.findall(r"[\d,\.]+", fat["valor"].replace(".", "").replace(",", "."))
    valores: list[float] = []
    for ns in numeros_str:
        try:
            valores.append(float(ns.replace(",", ".")))
        except ValueError:
            pass
    if not valores:
        return ""
    media = sum(valores) / len(valores)
    if media >= 20_000_000:
        return f"Sim — média R$ {media:,.0f} (acima de R$ 20.000.000)"
    else:
        return f"Não — média R$ {media:,.0f} (abaixo de R$ 20.000.000)"


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def analisar_diretorio(raiz: str, callback=None) -> list[dict]:
    _log(f"\n{'═'*60}")
    _log(f"  ANÁLISE INICIADA")
    _log(f"  Pasta: {raiz}")
    _log(f"{'═'*60}")
    resultados: list[dict] = []
    total = len(ELEMENTOS)

    for i, elemento in enumerate(ELEMENTOS):
        _log(f"\n  [{i+1:02d}/{total}] {elemento['campo']}")
        if callback:
            callback(i, total, elemento["campo"])

        result: dict = {
            "id":        elemento["id"],
            "categoria": elemento["categoria"],
            "campo":     elemento["campo"],
            "descricao": elemento["descricao"],
            "valor":     "",
            "trecho":    "",
            "arquivos":  [],
            "status":    "nao_encontrado",
            "tipo":      elemento.get("tipo", "simples"),
        }

        tipo_elem = elemento.get("tipo", "simples")

        if tipo_elem == "derivado_fastpass":
            result["status"] = "derivado"
            resultados.append(result)
            continue

        if tipo_elem == "existencia":
            arquivos = encontrar_arquivos(raiz, elemento)
            result["arquivos"] = arquivos
            if arquivos:
                result["valor"]  = f"Sim — {os.path.basename(arquivos[0])}"
                result["status"] = "ok"
            resultados.append(result)
            continue

        if tipo_elem == "existencia_alerta":
            arquivos = encontrar_arquivos(raiz, elemento)
            result["arquivos"] = arquivos
            if arquivos:
                result["valor"]  = f"SIM — {os.path.basename(arquivos[0])}"
                result["status"] = "ok"
            else:
                result["valor"]  = "Não"
                result["status"] = "ok"
            resultados.append(result)
            continue

        arquivos = encontrar_arquivos(raiz, elemento)
        result["arquivos"] = arquivos

        if not arquivos:
            result["status"] = "nao_encontrado"
        else:
            for arq in arquivos:
                texto = extrair_texto(arq)
                val, trecho = aplicar_regex(texto, elemento)
                if val:
                    _log(f"      → {val[:80]!r}")
                    result["valor"]    = val
                    result["trecho"]   = trecho
                    result["status"]   = "ok"
                    result["arquivos"] = [arq]
                    break
            else:
                result["status"] = "sem_dado"

        resultados.append(result)

    # Calcula Fastpass depois de ter o Faturamento
    for r in resultados:
        if r["id"] == "fastpass":
            val = _calcular_fastpass(resultados)
            r["valor"]  = val
            r["status"] = "ok" if val else "nao_encontrado"

    ok = sum(1 for r in resultados if r["status"] == "ok")
    _log(f"\n{'═'*60}")
    _log(f"  ANÁLISE CONCLUÍDA — {ok}/{total} encontrados")
    _log(f"{'═'*60}\n")
    if callback:
        callback(total, total, "Concluído")
    return resultados


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKLIST DE ALERTAS
# ══════════════════════════════════════════════════════════════════════════════
def _build_checklist(resultados: list[dict]) -> list[dict]:
    def _val(id_elem: str) -> str:
        r = next((x for x in resultados if x["id"] == id_elem), None)
        return (r.get("valor") or "") if r else ""

    fp        = _val("fastpass").lower()
    baixo_fat = fp.startswith("não") or fp.startswith("nao") if fp else False

    itens = [
        (not _val("contrato_existe"),         "SEM CONTRATO"),
        (not _val("procuracao_existe"),        "SEM PROCURAÇÃO"),
        (baixo_fat,                            "FATURAMENTO MÉDIO ABAIXO DE R$ 20M"),
        (_val("regularize").startswith("SIM"), "COM REGULARIZE"),
    ]
    return [{"alerta": bool(a), "descricao": d} for a, d in itens]


# ══════════════════════════════════════════════════════════════════════════════
#  LOG (stderr, para não poluir o JSON no stdout)
# ══════════════════════════════════════════════════════════════════════════════
def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "erro": "Uso: python3 analisar_job.py <pasta_raiz>"
        }), flush=True)
        sys.exit(1)

    pasta_raiz = sys.argv[1]

    if not os.path.isdir(pasta_raiz):
        print(json.dumps({
            "erro": f"Diretório não encontrado: {pasta_raiz}"
        }), flush=True)
        sys.exit(1)

    def callback(atual, total, campo):
        _log(f"[{atual}/{total}] {campo}")

    try:
        resultados = analisar_diretorio(pasta_raiz, callback)
        checklist  = _build_checklist(resultados)

        # Resumo numérico
        ok       = sum(1 for r in resultados if r["status"] == "ok")
        alertas  = sum(1 for r in resultados if r["status"] in ("nao_encontrado", "sem_dado") and not r.get("valor"))
        n_alertas = sum(1 for c in checklist if c["alerta"])

        saida = {
            "pasta_raiz":  pasta_raiz,
            "analisado_em": datetime.now().isoformat(),
            "resumo": {
                "total":         len(resultados),
                "encontrados":   ok,
                "nao_encontrados": alertas,
                "alertas_checklist": n_alertas,
            },
            "checklist":   checklist,
            "resultados":  resultados,
        }

        print(json.dumps(saida, ensure_ascii=False, default=str), flush=True)

    except Exception as e:
        import traceback
        print(json.dumps({
            "erro":      str(e),
            "traceback": traceback.format_exc(),
        }), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
