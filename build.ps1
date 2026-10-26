# =============================================================================
#  build.ps1 - Gera o pacote 100% autocontido da API Analises (Windows)
# =============================================================================
#  Roda UMA vez numa maquina Windows com Node.js e Python instalados
#  (a propria VM, ja preparada pelo init_vm.txt, serve).
#
#  Produz dist\ApiAnalises\ - uma pasta portatil que roda em QUALQUER Windows,
#  sem precisar instalar Node, Python, Tesseract ou banco de dados:
#    - server.exe         (Node + Express + SQLite, empacotado)
#    - analisar_job.exe   (Python + libs de extracao, empacotado)
#    - tesseract\         (OCR portatil, sem instalador)
#    - iniciar.bat        (launcher: da dois cliques e sobe a API)
#    - frontend embutido no server.exe
#
#  Uso (PowerShell, dentro da pasta do projeto):
#    .\build.ps1
#
#  Gera tambem dist\ApiAnalises.zip pronto para copiar pra outra maquina.
#
#  Texto sem acentos de proposito (evita erro de encoding no PowerShell).
# =============================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$distBuild = "$root\dist\build"
$pkgDir    = "$root\dist\ApiAnalises"

Write-Host ""
Write-Host "=== Build - API Analises (pacote autocontido) ===" -ForegroundColor Cyan
Write-Host ""

New-Item -ItemType Directory -Path $distBuild -Force | Out-Null

# -- 0. Pre-requisitos (so no AMBIENTE DE BUILD; o pacote final nao exige nada disso) --
Write-Host "[0/5] Verificando Node.js e Python no ambiente de build..." -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js nao encontrado. Rode init_vm.txt primeiro." }
$pythonOk = $false
try { $pythonOk = ((& python --version 2>&1) -match "Python 3") } catch {}
if (-not $pythonOk) { throw "Python 3 nao encontrado. Rode init_vm.txt primeiro." }
Write-Host "  ok" -ForegroundColor Green
Write-Host ""

# -- 1. Node: instala deps e empacota server.exe ------------------------------
Write-Host "[1/5] Empacotando servidor Node (server.exe)..." -ForegroundColor Cyan
if (-not (Test-Path "$root\node_modules")) {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install falhou." }
}
npm run build:server
if ($LASTEXITCODE -ne 0) { throw "Build do server.exe falhou." }
Write-Host "  ok: dist\build\server.exe" -ForegroundColor Green
Write-Host ""

# -- 2. Python: empacota analisar_job.exe -------------------------------------
Write-Host "[2/5] Empacotando analisador Python (analisar_job.exe)..." -ForegroundColor Cyan
& "$root\build\build_python.ps1"
if ($LASTEXITCODE -ne 0) { throw "Build do analisar_job.exe falhou." }
Write-Host "  ok: dist\build\analisar_job.exe" -ForegroundColor Green
Write-Host ""

# -- 3. Tesseract OCR portatil (sem instalador no destino) --------------------
Write-Host "[3/5] Preparando Tesseract OCR portatil..." -ForegroundColor Cyan
$tessOut = "$distBuild\tesseract"
if (-not (Test-Path "$tessOut\tesseract.exe")) {
    $TESSERACT_URL = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe"
    $tmp = "$env:TEMP\api-analises-build"
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $exe = "$tmp\tesseract-setup.exe"
    Write-Host "  Baixando instalador do Tesseract..." -ForegroundColor Yellow
    Invoke-WebRequest -UseBasicParsing -Uri $TESSERACT_URL -OutFile $exe
    Write-Host "  Instalando numa pasta isolada (vira portatil depois)..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $tessOut -Force | Out-Null
    Start-Process $exe -ArgumentList "/S", "/D=$tessOut" -Wait
    if (-not (Test-Path "$tessOut\tesseract.exe")) { throw "Instalacao do Tesseract nao gerou tesseract.exe em $tessOut" }
    if (-not (Test-Path "$tessOut\tessdata\por.traineddata")) {
        Write-Host "  Baixando idioma portugues..." -ForegroundColor Yellow
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/por.traineddata" -OutFile "$tessOut\tessdata\por.traineddata"
    }
} else {
    Write-Host "  ja preparado, pulando download" -ForegroundColor Green
}
Write-Host "  ok: dist\build\tesseract\" -ForegroundColor Green
Write-Host ""

# -- 4. Monta a pasta final distribuivel ---------------------------------------
Write-Host "[4/5] Montando pacote final (dist\ApiAnalises\)..." -ForegroundColor Cyan
Remove-Item -Recurse -Force $pkgDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null

Copy-Item "$distBuild\server.exe"       "$pkgDir\server.exe"       -Force
Copy-Item "$distBuild\analisar_job.exe" "$pkgDir\analisar_job.exe" -Force
Copy-Item "$distBuild\tesseract"        "$pkgDir\tesseract"        -Recurse -Force
New-Item -ItemType Directory -Path "$pkgDir\data\jobs" -Force | Out-Null

@"
@echo off
title API Analises - Studio Fiscal
cd /d "%~dp0"
set PORT=3030
set TESSERACT_CMD=%~dp0tesseract\tesseract.exe
set TESSDATA_PREFIX=%~dp0tesseract\tessdata
echo.
echo  === API Analises - Studio Fiscal ===
echo  Acesse: http://localhost:%PORT%
echo  (Para parar: feche esta janela ou Ctrl+C)
echo.
server.exe
pause
"@ | Set-Content -Path "$pkgDir\iniciar.bat" -Encoding ASCII

@"
API Analises - Studio Fiscal (pacote autocontido)
==================================================

Como usar:
  1. Copie esta pasta inteira para a maquina de destino (qualquer Windows).
  2. De dois cliques em "iniciar.bat".
  3. Acesse http://localhost:3030 no navegador.

Nada mais precisa estar instalado: Node, Python, Tesseract e o banco de
dados (SQLite) ja estao todos dentro desta pasta.

O banco fica em data\database.sqlite e as analises (JSON) em data\jobs\ -
faca backup dessa pasta "data" periodicamente.

Para mudar a porta, edite PORT= no comeco do iniciar.bat.
"@ | Set-Content -Path "$pkgDir\LEIA-ME.txt" -Encoding UTF8

Write-Host "  ok" -ForegroundColor Green
Write-Host ""

# -- 5. Self-test: sobe o pacote final e confere /health ----------------------
Write-Host "[5/5] Testando o pacote final..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "$pkgDir\server.exe" -WorkingDirectory $pkgDir -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
$ok = $false
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:3030/health" -TimeoutSec 5
    $ok = ($resp.status -eq "ok")
} catch {}
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$pkgDir\data" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$pkgDir\data\jobs" -Force | Out-Null

if ($ok) {
    Write-Host "  ok: server.exe sobe e responde em /health" -ForegroundColor Green
} else {
    Write-Host "  ATENCAO: nao foi possivel confirmar /health. Rode iniciar.bat manualmente e veja o log." -ForegroundColor Yellow
}
Write-Host ""

# -- 6. Zip final -----------------------------------------------------------
Write-Host "Compactando dist\ApiAnalises.zip..." -ForegroundColor Cyan
$zipPath = "$root\dist\ApiAnalises.zip"
Remove-Item $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path $pkgDir -DestinationPath $zipPath
Write-Host "  ok: $zipPath" -ForegroundColor Green
Write-Host ""

Write-Host "=== Pronto! ===" -ForegroundColor Green
Write-Host "Pacote em: dist\ApiAnalises\" -ForegroundColor Green
Write-Host "Zip:       dist\ApiAnalises.zip" -ForegroundColor Green
