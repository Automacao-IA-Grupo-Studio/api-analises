param()

$PORT = "3000"
if ($env:PORT) { $PORT = $env:PORT }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan
Write-Host ""

# 1. Mata processo na porta
Write-Host "[1/5] Liberando porta $PORT..." -ForegroundColor Yellow
$pids = netstat -ano | Select-String (":$PORT\s") | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
foreach ($p in $pids) {
    taskkill /PID $p /F 2>$null | Out-Null
    Write-Host "      PID $p finalizado" -ForegroundColor Green
}
Start-Sleep -Milliseconds 500

# 2. npm install se necessario
Write-Host "[2/5] Verificando node_modules..." -ForegroundColor Yellow
if (-not (Test-Path "node_modules")) {
    Write-Host "      Rodando npm install..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Host "ERRO: npm install falhou" -ForegroundColor Red; exit 1 }
}
Write-Host "      OK" -ForegroundColor Green

# 3. pip install
Write-Host "[3/5] Verificando dependencias Python..." -ForegroundColor Yellow
$py = "python"
if ($env:PYTHON_BIN) { $py = $env:PYTHON_BIN }
if (Test-Path "requirements.txt") {
    & $py -m pip install -r requirements.txt -q --disable-pip-version-check
}
Write-Host "      OK" -ForegroundColor Green

# 4. .env
Write-Host "[4/5] Verificando .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "      .env criado do .env.example - revise as configs!" -ForegroundColor Yellow
    } else {
        Write-Host "ERRO: .env nao encontrado" -ForegroundColor Red
        exit 1
    }
}
Write-Host "      OK" -ForegroundColor Green

# 5. Sobe servidor
Write-Host "[5/5] Subindo servidor..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  http://localhost:$PORT" -ForegroundColor Cyan
Write-Host ""

node server.js
