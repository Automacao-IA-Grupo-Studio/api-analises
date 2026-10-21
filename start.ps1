# ╔══════════════════════════════════════════════╗
# ║   API Análises — Studio Fiscal               ║
# ║   Script de inicialização para Windows       ║
# ╚══════════════════════════════════════════════╝

$PORT = if ($env:PORT) { $env:PORT } else { "3000" }

Write-Host ""
Write-Host "  ▶ Iniciando API Análises..." -ForegroundColor Cyan

# ── 1. Mata qualquer processo na porta ───────────────────────────────────────
Write-Host "  ▶ Liberando porta $PORT..." -ForegroundColor Yellow
$processos = netstat -ano | Select-String ":$PORT\s" | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Sort-Object -Unique | Where-Object { $_ -match '^\d+$' }

foreach ($pid in $processos) {
    try {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Host "    ✓ Processo $pid finalizado" -ForegroundColor Green
    } catch {}
}

Start-Sleep -Milliseconds 500

# ── 2. npm install (só se node_modules não existir) ──────────────────────────
if (-not (Test-Path "node_modules")) {
    Write-Host "  ▶ Instalando dependências Node..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ npm install falhou!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Dependências instaladas" -ForegroundColor Green
} else {
    Write-Host "  ✓ node_modules OK" -ForegroundColor Green
}

# ── 3. pip install (só se requirements.txt existir) ──────────────────────────
if (Test-Path "requirements.txt") {
    $pythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
    Write-Host "  ▶ Verificando dependências Python..." -ForegroundColor Yellow
    & $pythonBin -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ pip install falhou!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Dependências Python OK" -ForegroundColor Green
}

# ── 4. Verifica .env ──────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  ⚠  .env criado a partir do .env.example — revise as configurações!" -ForegroundColor Yellow
    } else {
        Write-Host "  ✗ .env não encontrado!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✓ .env OK" -ForegroundColor Green
}

# ── 5. Verifica MySQL (porta 3307) ────────────────────────────────────────────
Write-Host "  ▶ Verificando MySQL..." -ForegroundColor Yellow
$mysqlOk = $false
try {
    $conn = New-Object System.Net.Sockets.TcpClient
    $conn.Connect("localhost", 3307)
    $conn.Close()
    $mysqlOk = $true
    Write-Host "  ✓ MySQL acessível na porta 3307" -ForegroundColor Green
} catch {
    Write-Host "  ⚠  MySQL não encontrado na porta 3307" -ForegroundColor Yellow
    Write-Host "     Execute: docker compose up mysql -d" -ForegroundColor DarkYellow
}

# ── 6. Sobe o servidor ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔═══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Subindo servidor na porta $PORT...      ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

node server.js
