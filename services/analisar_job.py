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
#  LIMIARES DE NEGÓCIO (ajustar aqui se as regras mudarem)
# ══════════════════════════════════════════════════════════════════════════════
LIMIAR_FASTPASS = 20_000_000
LIMIAR_SUPPLY   = 30_000_000
LIMIAR_FINAP    = 50_000_000          # + CNAE principal precisa ser indústria

# Regularize: dívida total (PGFN + RFB) precisa estar ACIMA do limiar da classe
REGULARIZE_LIMIAR_AB     = 600_000    # classificação A ou B
REGULARIZE_LIMIAR_CD     = 300_000    # classificação C ou D
REGULARIZE_LIMIAR_OUTROS = 1_000_000  # sem classificação / omisso

PASTA_CNPJ = ["B - Documentos", "5 - Cliente", "16 - CNPJ"]

# ══════════════════════════════════════════════════════════════════════════════
#  ELEMENTOS DE ANÁLISE
#  "tipo" decide qual processador roda (ver PROCESSADORES mais abaixo)
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
        "tipo": "existencia",
    },
    {
        "id": "procuracao_existe",
        "categoria": "Contrato",
        "campo": "Procuração",
        "descricao": "Definido exclusivamente pelo Project (não depende do arquivo)",
        "tipo": "manual",
    },
    {
        "id": "honorarios",
        "categoria": "Contrato",
        "campo": "Honorários (%)",
        "descricao": "Percentual de honorários — sempre da cláusula 5.1 do contrato",
        "pasta": ["A - Contrato"],
        "arquivo_contem": ["Contrato"],
        "extensao": [".pdf"],
        "tipo": "honorarios",
    },
    {
        "id": "gross_up",
        "categoria": "Contrato",
        "campo": "Gross Up",
        "descricao": "Contrato prevê gross up? (sempre 14,25%)",
        "pasta": ["A - Contrato"],
        "arquivo_contem": ["Contrato"],
        "extensao": [".pdf"],
        "tipo": "gross_up",
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

    # ── DATA DE ABERTURA (sempre da Matriz) ──────────────────────────────────
    {
        "id": "data_abertura",
        "categoria": "Data de Abertura",
        "campo": "Data de Abertura",
        "descricao": "Data de constituição do CNPJ Matriz",
        "pasta": PASTA_CNPJ,
        "arquivo_contem": ["CNPJ"],
        "arquivo_nao_contem": ["QSA", "Optantes", "Consulta"],
        "extensao": [".pdf"],
        "assinatura": r"COMPROVANTE\s+DE\s+INSCRI",
        "tipo": "data_abertura",
    },

    # ── SIMPLES NACIONAL ─────────────────────────────────────────────────────
    {
        "id": "simples_nacional",
        "categoria": "Simples Nacional",
        "campo": "Simples Nacional",
        "descricao": "Situação no Simples Nacional e no SIMEI",
        "pasta": PASTA_CNPJ,
        "arquivo_contem_qualquer": ["Optantes", "Simples"],
        "extensao": [".pdf"],
        "assinatura": r"Simples\s+Nacional",
        "tipo": "simples",
    },

    # ── QSA ──────────────────────────────────────────────────────────────────
    {
        "id": "socios",
        "categoria": "QSA",
        "campo": "Sócios (QSA)",
        "descricao": "Sócios e administradores — nome e qualificação",
        "pasta": PASTA_CNPJ,
        "arquivo_contem_qualquer": ["QSA"],
        "extensao": [".pdf"],
        "assinatura": r"Quadro\s+de\s+S[óo]cios",
        "tipo": "qsa",
    },

    # ── REGULARIZE ───────────────────────────────────────────────────────────
    {
        "id": "regularize",
        "categoria": "Regularize",
        "campo": "Regularize",
        "descricao": "Perfil Regularize (capacidade de pagamento PGFN) ou sem cadastro",
        "pasta": ["B - Documentos", "2 - Fiscal"],
        "arquivo_contem_qualquer": ["PGFN", "Procuradoria", "Capag", "Capacidade"],
        "extensao": [".pdf"],
        "assinatura": r"capacidade\s+de\s+pagamento",
        "tipo": "regularize",
    },

    # ── PERFIL PREVIDENCIÁRIO ────────────────────────────────────────────────
    {
        "id": "perfil",
        "categoria": "Perfil Prev.",
        "campo": "Perfil Previdenciário",
        "descricao": "Qualquer ano acima do limiar = É PERFIL. Lista todos os anos.",
        "pasta": ["B - Documentos", "6 - Cruzamentos"],
        "arquivo_contem": ["perfil"],
        "extensao": [".pdf", ".xlsx", ".xls", ".txt"],
        "tipo": "perfil",
    },

    # ── FATURAMENTO ──────────────────────────────────────────────────────────
    {
        "id": "faturamento",
        "categoria": "Faturamento",
        "campo": "Faturamento por Ano",
        "descricao": "Total por ano (arquivos ECF) + média dos anos",
        "pasta": ["B - Documentos", "1 - Contábil", "5 - ECF"],
        "arquivo_contem": ["FATURAMENTO"],
        "extensao": [".txt"],
        "tipo": "faturamento",
    },
    {
        "id": "fastpass",
        "categoria": "Faturamento",
        "campo": "Fastpass (≥ R$ 20M)",
        "descricao": "Faturamento médio acima de R$ 20 milhões?",
        "tipo": "derivado",
        "limiar": LIMIAR_FASTPASS,
    },
    {
        "id": "supply",
        "categoria": "Faturamento",
        "campo": "Supply (≥ R$ 30M)",
        "descricao": "Faturamento médio a partir de R$ 30 milhões (abaixo disso desqualifica)",
        "tipo": "derivado",
        "limiar": LIMIAR_SUPPLY,
    },
    {
        "id": "finap",
        "categoria": "Faturamento",
        "campo": "Finap (≥ R$ 50M + indústria)",
        "descricao": "Faturamento médio a partir de R$ 50 milhões e CNAE principal industrial",
        "tipo": "derivado",
        "limiar": LIMIAR_FINAP,
        "exige_industria": True,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  BUSCA DE ARQUIVOS
# ══════════════════════════════════════════════════════════════════════════════
def _contem_todos(nome: str, termos: list[str]) -> bool:
    n = nome.lower()
    return all(t.lower() in n for t in termos)


def _contem_qualquer(nome: str, termos: list[str]) -> bool:
    n = nome.lower()
    return any(t.lower() in n for t in termos)


def _nao_contem(nome: str, termos: list[str]) -> bool:
    n = nome.lower()
    return not any(t.lower() in n for t in termos)


def _varrer_pasta(raiz: str, pastas_alvo: list[str], extensoes: set[str]):
    """Gera todos os arquivos cujo caminho passa pelas pastas-alvo."""
    for dirpath, _dirs, filenames in os.walk(raiz):
        partes = [p.lower() for p in Path(dirpath).parts]
        if not all(any(alvo.lower() in p for p in partes) for alvo in pastas_alvo):
            continue
        for fname in sorted(filenames):
            if extensoes and Path(fname).suffix.lower() not in extensoes:
                continue
            yield os.path.join(dirpath, fname)


def encontrar_arquivos(raiz: str, elemento: dict) -> list[str]:
    """Busca por NOME de arquivo."""
    pastas_alvo    = elemento.get("pasta", [])
    arq_contem     = elemento.get("arquivo_contem", [])
    arq_qualquer   = elemento.get("arquivo_contem_qualquer", [])
    arq_nao_contem = elemento.get("arquivo_nao_contem", [])
    extensoes      = {e.lower() for e in elemento.get("extensao", [])}
    resultados: list[str] = []

    _log(f"      [busca] pasta={pastas_alvo} | contem={arq_contem or arq_qualquer} | ext={list(extensoes) or 'qualquer'}")

    for caminho in _varrer_pasta(raiz, pastas_alvo, extensoes):
        fname = os.path.basename(caminho)
        if arq_contem and not _contem_todos(fname, arq_contem):
            continue
        if arq_qualquer and not _contem_qualquer(fname, arq_qualquer):
            continue
        if arq_nao_contem and not _nao_contem(fname, arq_nao_contem):
            continue
        _log(f"      [✓] {caminho}")
        resultados.append(caminho)

    if not resultados:
        _log("      [✗] nenhum arquivo encontrado pelo nome")
    return resultados


def candidatos(raiz: str, elemento: dict):
    """
    Gera arquivos candidatos: primeiro os que casam pelo NOME; depois (preguiçoso)
    os demais arquivos da pasta cujo CONTEÚDO bate com a assinatura do elemento.
    Assim funciona mesmo quando o arquivo tem nome genérico (ex.: 'pdf2.pdf').
    """
    vistos: set[str] = set()
    for a in encontrar_arquivos(raiz, elemento):
        vistos.add(a)
        yield a

    assinatura = elemento.get("assinatura")
    if not assinatura:
        return
    extensoes = {e.lower() for e in elemento.get("extensao", [".pdf"])}
    for a in _varrer_pasta(raiz, elemento.get("pasta", []), extensoes):
        if a in vistos:
            continue
        if re.search(assinatura, extrair_texto(a), re.IGNORECASE):
            _log(f"      [conteúdo] {a}")
            vistos.add(a)
            yield a

# ══════════════════════════════════════════════════════════════════════════════
#  OCR VIA TESSERACT
# ══════════════════════════════════════════════════════════════════════════════
def _garantir_tesseract() -> bool:
    """Localiza o Tesseract: portátil (empacotado), variável de ambiente,
    instalação padrão do Windows, ou no PATH (Linux/Docker)."""
    import shutil

    def _usar(caminho: str) -> bool:
        if not os.path.exists(caminho):
            return False
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = caminho
        except ImportError:
            pass
        return True

    # 1) Variável de ambiente explícita (setada pelo launcher ao lado do .exe portátil)
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and _usar(env_cmd):
        return True

    # 2) Tesseract portátil ao lado do próprio executável (empacotado com PyInstaller)
    #    sys.executable = caminho do analisar_job.exe quando congelado
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        for rel in (r"tesseract\tesseract.exe", r"..\tesseract\tesseract.exe"):
            if _usar(os.path.join(base, rel)):
                return True

    # 3) Docker / Linux: tesseract instalado via apt (no PATH)
    if shutil.which("tesseract"):
        return True

    # 4) Windows: instalação padrão do instalador oficial
    if os.name == 'nt':
        for p in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if _usar(p):
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
def _extrair_texto_raw(caminho: str) -> str:
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



_CACHE_TEXTO: dict[str, str] = {}


def extrair_texto(caminho: str) -> str:
    """Extrai texto com cache (o mesmo arquivo pode ser lido por vários elementos)."""
    if caminho not in _CACHE_TEXTO:
        _CACHE_TEXTO[caminho] = _extrair_texto_raw(caminho)
    return _CACHE_TEXTO[caminho]


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS NUMÉRICOS (formato brasileiro)
# ══════════════════════════════════════════════════════════════════════════════
_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"


def _brl(s: str):
    """'1.234.567,89' -> 1234567.89 | '45,3' -> 45.3 | '45.3' -> 45.3 | None se inválido."""
    s = (s or "").replace("R$", "").strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        return float(s.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d+,\d+", s):
        return float(s.replace(",", "."))
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    return None


def _fmt_brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_num(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _trecho(txt: str, ini: int, fim: int) -> str:
    return "..." + txt[max(0, ini - 60):min(len(txt), fim + 160)].replace("\n", " ").strip() + "..."


def _r(valor="", trecho="", arquivos=None, status=None, dados=None) -> dict:
    return {
        "valor": valor, "trecho": trecho, "arquivos": arquivos or [],
        "status": status or ("ok" if valor else "nao_encontrado"),
        "dados": dados or {},
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESSADORES
#  Assinatura: (raiz, elemento, ctx) -> dict (ver _r)
#  ctx: dicionário compartilhado entre elementos (ex.: CNAE principal)
# ══════════════════════════════════════════════════════════════════════════════

# ── Contrato: existência / manual ────────────────────────────────────────────
def _proc_existencia(raiz, elem, ctx):
    arquivos = encontrar_arquivos(raiz, elem)
    if arquivos:
        return _r(f"Sim — {os.path.basename(arquivos[0])}", arquivos=arquivos)
    return _r()


def _proc_manual(raiz, elem, ctx):
    # Procuração: vem exclusivamente do Project. Fica em branco por enquanto.
    return _r(status="em_branco")


# ── Honorários: SEMPRE da cláusula 5.1 ───────────────────────────────────────
_RE_INI_51_LINHA = re.compile(r"(?mi)^[ \t]*(?:cl[aá]usula[ \t]*)?5\.1(?!\d)")
_RE_INI_51_QQ    = re.compile(r"(?<![\d.,])5\.1(?!\d)")
_RE_FIM_51       = re.compile(
    r"(?mi)^[ \t]*(?:(?:cl[aá]usula[ \t]*)?5\.2(?!\d)"
    r"|cl[aá]usula[ \t]*(?:6|sexta)\b|6[.\-–)](?:\d|\s))"
)
_RE_PERCENT = re.compile(r"(\d{1,3}(?:[.,]\d{1,4})?)\s*%")
_RE_POR_EXTENSO = re.compile(r"\(\s*([a-zçãõáéíóúâêô ]{3,60}?)\s+por\s+cento\s*\)", re.IGNORECASE)


def _blocos_clausula_51(texto: str):
    """Gera candidatos de bloco da cláusula 5.1 (primeiro os que começam em linha própria)."""
    inicios = [m.start() for m in _RE_INI_51_LINHA.finditer(texto)]
    inicios += [m.start() for m in _RE_INI_51_QQ.finditer(texto) if m.start() not in inicios]
    for ini in inicios:
        fim = ini + 1800
        m_fim = _RE_FIM_51.search(texto, ini + 4)
        if m_fim and m_fim.start() < fim:
            fim = m_fim.start()
        yield ini, texto[ini:fim]


def _percentual_do_bloco(bloco: str):
    for m in _RE_PERCENT.finditer(bloco):
        num = m.group(1)
        antes = bloco[max(0, m.start() - 60):m.start()]
        if re.search(r"gross[\s\-]?up[^%]{0,40}$", antes, re.IGNORECASE):
            continue                       # percentual do gross up, não dos honorários
        if _brl(num) == 14.25:
            continue
        return num + "%", m
    m = _RE_POR_EXTENSO.search(bloco)
    if m:
        return m.group(1).strip() + " por cento", m
    return None, None


def _proc_honorarios(raiz, elem, ctx):
    arquivos = list(candidatos(raiz, elem))
    for arq in arquivos:
        texto = extrair_texto(arq)
        for ini, bloco in _blocos_clausula_51(texto):
            val, m = _percentual_do_bloco(bloco)
            if val:
                _log(f"      → cláusula 5.1: {val}")
                return _r(val, _trecho(texto, ini + m.start(), ini + m.end()), [arq])

    # Fallback (marcado para conferência): primeiro % próximo de 'honorários'
    for arq in arquivos:
        texto = extrair_texto(arq)
        m = re.search(r"(?:honor[aá]rios|remunera[çc][aã]o)[\s\S]{0,500}?(\d{1,3}(?:[.,]\d{1,4})?)\s*%", texto, re.IGNORECASE)
        if m:
            return _r(f"{m.group(1)}% (cláusula 5.1 não localizada — conferir)",
                      _trecho(texto, m.start(), m.end()), [arq], status="ok")
    return _r(arquivos=arquivos[:1], status="sem_dado" if arquivos else "nao_encontrado")


# ── Gross up: só Sim / Não (sempre 14,25%) ───────────────────────────────────
def _proc_gross_up(raiz, elem, ctx):
    arquivos = list(candidatos(raiz, elem))
    if not arquivos:
        return _r()
    for arq in arquivos:
        texto = extrair_texto(arq)
        m = re.search(r"gross[\s\-]?up|14[,\.]25\s*%", texto, re.IGNORECASE)
        if m:
            return _r("Sim (14,25%)", _trecho(texto, m.start(), m.end()), [arq])
    return _r("Não", arquivos=arquivos[:1], status="ok")


# ── Booleano genérico (Passivo) ──────────────────────────────────────────────
def _proc_booleano(raiz, elem, ctx):
    arquivos = list(candidatos(raiz, elem))
    for arq in arquivos:
        texto = extrair_texto(arq)
        for p in elem.get("regex", []):
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                return _r("Sim (mencionado no contrato)", _trecho(texto, m.start(), m.end()), [arq])
    return _r(arquivos=arquivos[:1], status="sem_dado" if arquivos else "nao_encontrado")


# ── Data de abertura: bloco da MATRIZ ────────────────────────────────────────
def _bloco_matriz(texto: str) -> str:
    """Num PDF com matriz + filiais, devolve só o trecho do estabelecimento MATRIZ."""
    partes = re.split(r"(?=N[ÚU]MERO\s+DE\s+INSCRI[ÇC][ÃA]O)", texto, flags=re.IGNORECASE)
    for p in partes:
        if re.search(r"\bMATRIZ\b", p) and not re.search(r"\bFILIAL\b", p[:500]):
            return p
    for p in partes:
        if re.search(r"/0001-\d{2}", p):
            return p
    return texto


def _proc_data_abertura(raiz, elem, ctx):
    for arq in candidatos(raiz, elem):
        texto = extrair_texto(arq)
        bloco = _bloco_matriz(texto)
        m = re.search(
            r"DATA\s+DE\s+(?:CONSTITUI[ÇC][ÃA]O|ABERTURA)[\s\S]{0,200}?(\d{2}[/\-.]\d{2}[/\-.]\d{4})",
            bloco, re.IGNORECASE)
        if not m:
            continue
        mc = re.search(r"ATIVIDADE\s+ECON[ÔO]MICA\s+PRINCIPAL\s*\n?\s*(\d{2}\.\d{2}-\d-\d{2})\s*-\s*([^\n]+)",
                       bloco, re.IGNORECASE)
        dados = {}
        if mc:
            ctx["cnae_principal"] = mc.group(1)
            ctx["cnae_descricao"] = mc.group(2).strip()
            dados = {"cnae_principal": mc.group(1), "cnae_descricao": mc.group(2).strip()}
        return _r(m.group(1), _trecho(bloco, m.start(), m.end()), [arq], dados=dados)
    return _r()


# ── Simples Nacional ─────────────────────────────────────────────────────────
def _proc_simples(raiz, elem, ctx):
    for arq in candidatos(raiz, elem):
        texto = extrair_texto(arq)
        linhas: list[str] = []
        # tolera OCR ("Situacao", "Situagao"...)
        m_sn = re.search(r"Situa\S{1,3}o\s+no\s+Simples\s+Nacional\s*:\s*([^\n\r]+)", texto, re.IGNORECASE)
        m_si = re.search(r"Situa\S{1,3}o\s+no\s+SIMEI\s*:\s*([^\n\r]+)", texto, re.IGNORECASE)
        if m_sn:
            linhas.append("Simples Nacional: " + m_sn.group(1).strip())
        if m_si:
            linhas.append("SIMEI: " + m_si.group(1).strip())
        if not linhas:
            m = re.search(r"(n[aã]o\s+optante[^\n\r]{0,60}|optante\s+pelo\s+simples[^\n\r]{0,60})", texto, re.IGNORECASE)
            if m:
                linhas.append(m.group(1).strip())
        if linhas:
            ref = m_sn or m_si
            return _r("\n".join(linhas), _trecho(texto, ref.start(), ref.end()) if ref else "", [arq])
    return _r()


# ── QSA ──────────────────────────────────────────────────────────────────────
_RE_SOCIO = re.compile(
    r"Nome(?:\s*/\s*Nome\s*Empresarial)?\s*:\s*(?P<n>[^\n\r]+)"
    r"(?:(?!Nome(?:\s*/\s*Nome\s*Empresarial)?\s*:)[\s\S]){0,250}?"
    r"Qualifica\S{1,3}o\s*:\s*(?P<q>[^\n\r]+)",
    re.IGNORECASE)


def _proc_qsa(raiz, elem, ctx):
    for arq in candidatos(raiz, elem):
        texto = extrair_texto(arq)
        capital = re.search(r"CAPITAL\s+SOCIAL\s*:\s*([^\n\r]+)", texto, re.IGNORECASE)
        cap_txt = f" | Capital social: {capital.group(1).strip()}" if capital else ""

        if re.search(r"NATUREZA\s+JUR[ÍI]DICA\s+N[ÃA]O\s+PERMITE", texto, re.IGNORECASE):
            return _r("Sem QSA — a natureza jurídica não permite o preenchimento" + cap_txt,
                      "A NATUREZA JURÍDICA NÃO PERMITE O PREENCHIMENTO DO QSA", [arq],
                      dados={"socios": []})

        socios, vistos = [], set()
        for m in _RE_SOCIO.finditer(texto):
            nome, qual = m.group("n").strip(), m.group("q").strip()
            if nome and (nome, qual) not in vistos:
                vistos.add((nome, qual))
                socios.append({"nome": nome, "qualificacao": qual})
        if socios:
            linhas = [f"{s['nome']} — {s['qualificacao']}" for s in socios]
            return _r("\n".join(linhas) + (("\n" + cap_txt.strip(" |")) if cap_txt else ""),
                      "", [arq], dados={"socios": socios})
    return _r()


# ── Regularize ───────────────────────────────────────────────────────────────
def _limiar_regularize(classe: str) -> int:
    c = (classe or "").strip().upper()[:1]
    if c in ("A", "B"):
        return REGULARIZE_LIMIAR_AB
    if c in ("C", "D"):
        return REGULARIZE_LIMIAR_CD
    return REGULARIZE_LIMIAR_OUTROS


def _proc_regularize(raiz, elem, ctx):
    # 1) Consulta de capacidade de pagamento (PGFN)
    for arq in candidatos(raiz, elem):
        texto = extrair_texto(arq)
        if not re.search(r"capacidade\s+de\s+pagamento", texto, re.IGNORECASE):
            continue
        m_cl = re.search(r"Classifica\S{1,3}o\s+para\s+transa\S{1,3}o\s*:?\s*([A-D]\b|omisso|sem\s+classifica[^\n]*)",
                         texto, re.IGNORECASE)
        classe = (m_cl.group(1).strip() if m_cl else "")
        m_div = re.search(r"Valor\s+total\s+da\s+d[ií]vida\s+na\s+PGFN\s+e\s+RFB\s*:\s*R\$\s*(" + _NUM + ")",
                          texto, re.IGNORECASE)
        divida = _brl(m_div.group(1)) if m_div else None
        if divida is None:
            continue
        m_cont = re.search(r"Valor\s+em\s+contencioso[^:\n]*:\s*R\$\s*(" + _NUM + ")", texto, re.IGNORECASE)
        contencioso = _brl(m_cont.group(1)) if m_cont else None

        limiar = _limiar_regularize(classe)
        eh = divida > limiar
        classe_txt = classe.upper() if classe[:1].upper() in "ABCD" and len(classe) == 1 else (classe or "sem classificação")
        valor = (f"{'SIM' if eh else 'Não'} — classificação {classe_txt} | dívida PGFN+RFB {_fmt_brl(divida)} "
                 f"({'acima' if eh else 'abaixo'} do limiar de {_fmt_brl(limiar)})")
        if contencioso:
            valor += f" | contencioso RFB {_fmt_brl(contencioso)} (não somado)"
        return _r(valor, _trecho(texto, m_div.start(), m_div.end()), [arq], status="ok",
                  dados={"classificacao": classe_txt, "divida_total": divida,
                         "contencioso": contencioso, "limiar": limiar, "perfil_regularize": eh})

    # 2) Arquivo (normalmente .txt) avisando que NÃO há cadastro no Regularize
    for caminho in _varrer_pasta(raiz, ["B - Documentos", "2 - Fiscal"], set()):
        if "regularize" in os.path.basename(caminho).lower():
            _log(f"      [✓] sem cadastro: {caminho}")
            return _r("Sem cadastro no Regularize", arquivos=[caminho], status="ok",
                      dados={"perfil_regularize": False, "sem_cadastro": True})
    return _r()


# ── Perfil previdenciário (todos os anos) ────────────────────────────────────
def _parse_perfil(texto: str) -> list[dict]:
    anos: dict[str, dict] = {}
    for linha in texto.splitlines():
        m_ano = re.search(r"\b((?:19|20)\d{2})\b", linha)
        m_st = re.search(r"\b(acima|abaixo)\b", linha, re.IGNORECASE)
        if not (m_ano and m_st):
            continue
        media = None
        m_med = re.search(r"m[eé]dia\D{0,15}(" + _NUM + ")", linha, re.IGNORECASE)
        if m_med:
            media = _brl(m_med.group(1))
        else:
            ini = m_ano.end() if m_ano.end() < m_st.start() else 0
            nums = [_brl(x) for x in re.findall(_NUM, linha[ini:m_st.start()])]
            nums = [n for n in nums if n is not None]
            media = nums[-1] if nums else None
        anos[m_ano.group(1)] = {"ano": m_ano.group(1), "media": media, "status": m_st.group(1).upper()}
    return [anos[a] for a in sorted(anos)]


def _proc_perfil(raiz, elem, ctx):
    for arq in candidatos(raiz, elem):
        texto = extrair_texto(arq)
        anos = _parse_perfil(texto)
        if anos:
            acima = [a["ano"] for a in anos if a["status"] == "ACIMA"]
            cab = f"É PERFIL — acima em: {', '.join(acima)}" if acima else "Não é perfil — nenhum ano acima"
            linhas = [cab]
            for a in anos:
                med = _fmt_num(a["media"]) if a["media"] is not None else "—"
                linhas.append(a["ano"] + ": média " + med + " — " + a["status"])
            return _r("\n".join(linhas), "", [arq],
                      dados={"anos": anos, "eh_perfil": bool(acima)})
        # Fallback: documento sem tabela por ano, só o veredito
        m = re.search(r"(acima\s*do\s*limiar|abaixo\s*do\s*limiar|limiar[:\s]+(?:acima|abaixo)|(?:acima|abaixo)[^.\n]{0,50}limiar)",
                      texto, re.IGNORECASE)
        if m:
            eh = "acima" in m.group(1).lower()
            return _r(("É PERFIL — " if eh else "Não é perfil — ") + m.group(1).strip() + " (sem detalhe por ano)",
                      _trecho(texto, m.start(), m.end()), [arq], dados={"eh_perfil": eh})
    return _r()


# ── Faturamento: total por ano + média ───────────────────────────────────────
_RE_TOTAL_ARQ = [
    r"TOTAL\s*DO\s*ARQUIVO[^\d]{0,20}(" + _NUM + ")",
    r"(?:receita|faturamento)\s*(?:bruta|total)?\s*[:\-]?\s*R?\$?\s*(" + _NUM + ")",
]


def _ano_do_arquivo(caminho: str, texto: str):
    m = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", os.path.basename(caminho))
    if m:
        return m.group(1)
    m = re.search(r"(?:ano[\s\-]*calend[aá]rio|exerc[ií]cio|ano)\D{0,15}((?:19|20)\d{2})", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", texto)
    return m.group(1) if m else None


def _proc_faturamento(raiz, elem, ctx):
    arquivos = encontrar_arquivos(raiz, elem)
    if not arquivos:
        return _r()
    por_ano: dict[str, float] = {}
    usados: list[str] = []
    for arq in arquivos:
        texto = extrair_texto(arq)

        # Um arquivo com várias linhas "ANO ... VALOR"
        linhas_ano = re.findall(r"(?m)^\s*((?:19|20)\d{2})\D{1,40}?(" + _NUM + r")\s*$", texto)
        if len(linhas_ano) >= 2:
            for ano, v in linhas_ano:
                if _brl(v) is not None:
                    por_ano[ano] = _brl(v)
            usados.append(arq)
            continue

        total = None
        for p in _RE_TOTAL_ARQ:
            m = re.search(p, texto, re.IGNORECASE)
            if m and _brl(m.group(1)) is not None:
                total = _brl(m.group(1))
                break
        if total is None:
            continue
        ano = _ano_do_arquivo(arq, texto) or Path(arq).stem
        por_ano[ano] = total
        usados.append(arq)

    if not por_ano:
        return _r(arquivos=arquivos[:1], status="sem_dado")

    media = sum(por_ano.values()) / len(por_ano)
    linhas = [f"{a}: {_fmt_brl(v)}" for a, v in sorted(por_ano.items())]
    linhas.append(f"Média ({len(por_ano)} ano{'s' if len(por_ano) != 1 else ''}): {_fmt_brl(media)}")
    return _r("\n".join(linhas), "", usados,
              dados={"por_ano": por_ano, "media": media})


# ── Derivados do faturamento: Fastpass / Supply / Finap ──────────────────────
def _eh_industria(cnae: str) -> bool:
    """Indústria de transformação = divisões CNAE 10 a 33."""
    try:
        return 10 <= int(cnae[:2]) <= 33
    except (ValueError, TypeError):
        return False


def _calcular_derivado(elem: dict, resultados: list[dict], ctx: dict) -> str:
    fat = next((r for r in resultados if r["id"] == "faturamento"), None)
    media = (fat or {}).get("dados", {}).get("media")
    if media is None:
        return ""
    limiar = elem["limiar"]
    if media < limiar:
        return f"Não — média {_fmt_brl(media)} (abaixo de {_fmt_brl(limiar)})"
    if elem.get("exige_industria"):
        cnae = ctx.get("cnae_principal")
        if not cnae:
            return f"Verificar — média {_fmt_brl(media)}, mas o CNAE principal não foi identificado (precisa ser indústria)"
        if not _eh_industria(cnae):
            return f"Não — média {_fmt_brl(media)}, mas o CNAE principal ({cnae}) não é indústria"
        return f"Sim — média {_fmt_brl(media)} | indústria (CNAE {cnae})"
    return f"Sim — média {_fmt_brl(media)} (a partir de {_fmt_brl(limiar)})"


PROCESSADORES = {
    "existencia":    _proc_existencia,
    "manual":        _proc_manual,
    "honorarios":    _proc_honorarios,
    "gross_up":      _proc_gross_up,
    "booleano":      _proc_booleano,
    "data_abertura": _proc_data_abertura,
    "simples":       _proc_simples,
    "qsa":           _proc_qsa,
    "regularize":    _proc_regularize,
    "perfil":        _proc_perfil,
    "faturamento":   _proc_faturamento,
}


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def analisar_diretorio(raiz: str, callback=None) -> list[dict]:
    _log(f"\n{'═'*60}")
    _log("  ANÁLISE INICIADA")
    _log(f"  Pasta: {raiz}")
    _log(f"{'═'*60}")
    resultados: list[dict] = []
    ctx: dict = {}
    total = len(ELEMENTOS)

    for i, elemento in enumerate(ELEMENTOS):
        _log(f"\n  [{i+1:02d}/{total}] {elemento['campo']}")
        if callback:
            callback(i, total, elemento["campo"])

        base = {
            "id":        elemento["id"],
            "categoria": elemento["categoria"],
            "campo":     elemento["campo"],
            "descricao": elemento["descricao"],
            "tipo":      elemento.get("tipo", "simples"),
        }

        tipo = elemento.get("tipo")
        if tipo == "derivado":
            valor = _calcular_derivado(elemento, resultados, ctx)
            parcial = _r(valor)
        else:
            try:
                parcial = PROCESSADORES[tipo](raiz, elemento, ctx)
            except Exception as e:                      # um elemento nunca derruba os demais
                _log(f"      [ERRO] {elemento['id']}: {e}")
                parcial = _r(status="erro", trecho=str(e))
        if parcial["valor"]:
            _log(f"      → {parcial['valor'].splitlines()[0][:90]!r}")
        resultados.append({**base, **parcial})

    ok = sum(1 for r in resultados if r["status"] == "ok")
    _log(f"\n{'═'*60}")
    _log(f"  ANÁLISE CONCLUÍDA — {ok}/{total} encontrados")
    _log(f"{'═'*60}\n")
    if callback:
        callback(total, total, "Concluído")
    return resultados


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKLIST DE ALERTAS
#  (Procuração não gera alerta: vem do Project)
# ══════════════════════════════════════════════════════════════════════════════
def _build_checklist(resultados: list[dict]) -> list[dict]:
    def _val(id_elem: str) -> str:
        r = next((x for x in resultados if x["id"] == id_elem), None)
        return (r.get("valor") or "") if r else ""

    fp        = _val("fastpass").lower()
    baixo_fat = fp.startswith("não") or fp.startswith("nao") if fp else False

    itens = [
        (not _val("contrato_existe"),               "SEM CONTRATO"),
        (baixo_fat,                                  "FATURAMENTO MÉDIO ABAIXO DE R$ 20M"),
        (_val("regularize").upper().startswith("SIM"), "COM REGULARIZE"),
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
