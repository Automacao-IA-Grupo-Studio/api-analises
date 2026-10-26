# =============================================================================
#  build_python.ps1 - Empacota services/analisar_job.py num .exe standalone
# =============================================================================
#  Usa PyInstaller para gerar analisar_job.exe: roda em qualquer Windows,
#  sem precisar de Python instalado na maquina de destino.
#
#  PRECISA rodar numa maquina Windows com Python instalado (PyInstaller nao
#  faz cross-compile: um .exe Windows so pode ser gerado rodando no Windows).
#
#  Uso (PowerShell, dentro da pasta do projeto):
#    .\build\build_python.ps1
#
#  Saida: dist\build\analisar_job.exe
#
#  Texto sem acentos de proposito (evita erro de encoding no PowerShell).
# =============================================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== Empacotando analisar_job.py (PyInstaller) ===" -ForegroundColor Cyan

# ---- 1. Confere Python -------------------------------------------------------
$pythonOk = $false
try { $pythonOk = ((& python --version 2>&1) -match "Python 3") } catch {}
if (-not $pythonOk) {
    throw "Python 3 nao encontrado no PATH. Instale (python.org) e rode de novo, ou rode primeiro o init_vm.txt."
}

# ---- 2. Venv isolada para o build (evita poluir o Python do sistema) --------
$venvDir = "$root\build\.venv-build"
if (-not (Test-Path $venvDir)) {
    Write-Host "[1/4] Criando ambiente virtual de build..." -ForegroundColor Yellow
    python -m venv $venvDir
} else {
    Write-Host "[1/4] Ambiente virtual de build ja existe" -ForegroundColor Green
}
$venvPython = "$venvDir\Scripts\python.exe"

# ---- 3. Dependencias ----------------------------------------------------------
Write-Host "[2/4] Instalando dependencias (requirements.txt + pyinstaller)..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --disable-pip-version-check --quiet
& $venvPython -m pip install -r "$root\requirements.txt" --disable-pip-version-check --quiet
& $venvPython -m pip install "pyinstaller>=6.0.0" --disable-pip-version-check --quiet

# ---- 4. Build com PyInstaller --------------------------------------------------
Write-Host "[3/4] Rodando PyInstaller (onefile)..." -ForegroundColor Yellow
$buildWork = "$root\build\.pyinstaller-work"
$buildDist = "$root\build\.pyinstaller-dist"
Remove-Item -Recurse -Force $buildWork, $buildDist -ErrorAction SilentlyContinue

& $venvPython -m PyInstaller `
    --onefile `
    --name analisar_job `
    --distpath $buildDist `
    --workpath $buildWork `
    --specpath "$root\build" `
    --collect-all pdfplumber `
    --collect-all pypdfium2 `
    --collect-all pymupdf `
    --collect-all PIL `
    --collect-all pytesseract `
    --collect-all openpyxl `
    --collect-all charset_normalizer `
    "$root\services\analisar_job.py"

if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou (veja o log acima)." }

# ---- 5. Copia pro destino final ------------------------------------------------
Write-Host "[4/4] Copiando para dist\build\analisar_job.exe..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "$root\dist\build" -Force | Out-Null
Copy-Item "$buildDist\analisar_job.exe" "$root\dist\build\analisar_job.exe" -Force

# ---- 6. Smoke test ---------------------------------------------------------
Write-Host ""
Write-Host "Teste rapido (sem pasta real -> espera erro amigavel em JSON):" -ForegroundColor Cyan
& "$root\dist\build\analisar_job.exe" "C:\pasta-que-nao-existe"

Write-Host ""
Write-Host "OK: dist\build\analisar_job.exe gerado com sucesso." -ForegroundColor Green
