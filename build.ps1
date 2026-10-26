# =============================================================================
#  build.ps1 - Gera o pacote 100% autocontido do APP DESKTOP (Windows)
# =============================================================================
#  Roda UMA vez numa maquina Windows com Node.js e Python instalados.
#
#  Produz dist\AnaliseDesktop\ - uma pasta portatil que roda em QUALQUER
#  Windows, sem precisar instalar Node, Python ou Tesseract:
#    - AnaliseDesktop.exe + DLLs do Electron  (janela grafica do app)
#    - analisar_job.exe   (Python + libs de extracao, empacotado)
#    - tesseract\         (OCR portatil, sem instalador)
#    - LEIA-ME.txt
#
#  Este pacote NAO sobe API nem usa banco de dados externo: cada analise
#  grava o resultado num arquivo local (data\jobs.json, dentro da propria
#  pasta do app) e mostra tudo numa janela grafica (mesmo visual do Modo
#  API). Cada maquina/usuario tem seu proprio historico, local, sem rede.
#  Para o modo API (producao, multiusuario, MySQL), veja init_vm.txt /
#  docker-compose.yml / ecosystem.config.js.
#
#  Uso (PowerShell, dentro da pasta do projeto):
#    .\build.ps1
#
#  Gera tambem dist\AnaliseDesktop.zip pronto para copiar pra outra maquina.
#
#  Texto sem acentos de proposito (evita erro de encoding no PowerShell).
# =============================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$distBuild   = "$root\dist\build"
$electronOut = "$distBuild\AnaliseDesktop-win32-x64"
$pkgDir      = "$root\dist\AnaliseDesktop"

Write-Host ""
Write-Host "=== Build - Analise Desktop (pacote autocontido) ===" -ForegroundColor Cyan
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

# -- 1. App desktop (Electron): instala deps e empacota pra win32-x64 --------
Write-Host "[1/5] Empacotando app desktop (Electron)..." -ForegroundColor Cyan
Push-Location "$root\desktop-gui"
npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install (desktop-gui) falhou." }
npm run build:win
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Build do AnaliseDesktop.exe falhou." }
Pop-Location
if (-not (Test-Path "$electronOut\AnaliseDesktop.exe")) { throw "electron-packager nao gerou AnaliseDesktop.exe em $electronOut" }
Write-Host "  ok: $electronOut\AnaliseDesktop.exe" -ForegroundColor Green
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
Write-Host "[4/5] Montando pacote final (dist\AnaliseDesktop\)..." -ForegroundColor Cyan
Remove-Item -Recurse -Force $pkgDir -ErrorAction SilentlyContinue

# Copia a pasta inteira que o electron-packager gerou (AnaliseDesktop.exe +
# todas as DLLs/recursos do Electron) como base do pacote final.
Copy-Item $electronOut $pkgDir -Recurse -Force

Copy-Item "$distBuild\analisar_job.exe" "$pkgDir\analisar_job.exe" -Force
Copy-Item "$distBuild\tesseract"        "$pkgDir\tesseract"        -Recurse -Force

@"
Analise Desktop - Studio Fiscal (pacote autocontido)
======================================================

Como usar:
  1. Copie esta pasta inteira para a maquina de destino (qualquer Windows).
  2. De dois cliques em "AnaliseDesktop.exe".
  3. Uma janela abre com o mesmo painel do Modo API: formulario para
     analisar um job (numero + caminho da pasta de rede) e a lista dos
     jobs ja analisados NESTA maquina.

Nada mais precisa estar instalado: Node, Python, Tesseract e os dados
(arquivo local) ja estao todos dentro desta pasta.

Os resultados ficam em data\jobs.json, dentro desta mesma pasta - cada
maquina/usuario tem seu proprio historico, local, sem depender de rede ou
servidor. Faca backup dessa pasta "data" periodicamente.

Para enviar os resultados pro sistema central (API + MySQL na VM, com
historico compartilhado por todo o time), use o Modo API em vez deste
pacote - veja o README do projeto.
"@ | Set-Content -Path "$pkgDir\LEIA-ME.txt" -Encoding UTF8

Write-Host "  ok" -ForegroundColor Green
Write-Host ""

# -- 5. Zip final -----------------------------------------------------------
Write-Host "[5/5] Compactando dist\AnaliseDesktop.zip..." -ForegroundColor Cyan
$zipPath = "$root\dist\AnaliseDesktop.zip"
Remove-Item $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path $pkgDir -DestinationPath $zipPath
Write-Host "  ok: $zipPath" -ForegroundColor Green
Write-Host ""

Write-Host "=== Pronto! ===" -ForegroundColor Green
Write-Host "Pacote em: dist\AnaliseDesktop\" -ForegroundColor Green
Write-Host "Zip:       dist\AnaliseDesktop.zip" -ForegroundColor Green
