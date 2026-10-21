param()

$PORT = if ($env:PORT) { $env:PORT } else { "3000" }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan
Write-Host ""

# 1. Mata processo na porta
Write-Host "[1/6] Liberando porta $PORT..." -ForegroundColor Yellow
$pids = netstat -ano | Select-String (":$PORT\s") | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
foreach ($p in $pids) {
    if ($p -ne "0") {
        taskkill /PID $p /F 2>$null | Out-Null
        Write-Host "      PID $p finalizado" -ForegroundColor Green
    }
}
Write-Host "      OK" -ForegroundColor Green

# 2. npm install se necessario
Write-Host "[2/6] Verificando node_modules..." -ForegroundColor Yellow
if (-not (Test-Path "node_modules")) {
    Write-Host "      Rodando npm install..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Host "ERRO: npm install falhou" -ForegroundColor Red; exit 1 }
}
Write-Host "      OK" -ForegroundColor Green

# 3. pip install
Write-Host "[3/6] Verificando dependencias Python..." -ForegroundColor Yellow
$py = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
if (Test-Path "requirements.txt") {
    & $py -m pip install -r requirements.txt -q --disable-pip-version-check 2>$null
}
Write-Host "      OK" -ForegroundColor Green

# 4. .env
Write-Host "[4/6] Verificando .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "      .env criado do .env.example" -ForegroundColor Yellow
    } else {
        Write-Host "ERRO: .env nao encontrado" -ForegroundColor Red; exit 1
    }
}
Write-Host "      OK" -ForegroundColor Green

# 5. Docker Desktop + MySQL
Write-Host "[5/6] Verificando Docker / MySQL..." -ForegroundColor Yellow

$dockerOk = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    Write-Host "      Docker Desktop nao esta rodando. Iniciando..." -ForegroundColor Yellow
    $dockerExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        Write-Host "      Aguardando Docker iniciar (pode demorar ~30s)..." -ForegroundColor Yellow
        $tentativas = 0
        while ($tentativas -lt 30) {
            Start-Sleep -Seconds 3
            $tentativas++
            try {
                docker info 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
            } catch {}
            Write-Host "      ... tentativa $tentativas/30" -ForegroundColor DarkYellow
        }
        if (-not $dockerOk) {
            Write-Host "ERRO: Docker nao respondeu. Abra o Docker Desktop manualmente e rode .\start.ps1 novamente." -ForegroundColor Red
            exit 1
        }
        Write-Host "      Docker pronto" -ForegroundColor Green
    } else {
        Write-Host "ERRO: Docker Desktop nao encontrado. Instale em https://docs.docker.com/desktop/windows/" -ForegroundColor Red
        exit 1
    }
}

Write-Host "      Subindo MySQL..." -ForegroundColor Yellow
docker compose up mysql -d 2>$null | Out-Null

Write-Host "      Aguardando MySQL ficar pronto..." -ForegroundColor Yellow
$mysqlOk = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = docker compose exec mysql mysqladmin ping -h localhost -u root -pstudiofiscal --silent 2>$null
        if ($LASTEXITCODE -eq 0) { $mysqlOk = $true; break }
    } catch {}
    Write-Host "      ... aguardando MySQL ($i/20)" -ForegroundColor DarkYellow
}

if ($mysqlOk) {
    Write-Host "      MySQL pronto" -ForegroundColor Green
} else {
    Write-Host "      MySQL pode ainda estar iniciando, tentando assim mesmo..." -ForegroundColor Yellow
}

# 6. Sobe servidor
Write-Host "[6/6] Subindo servidor Node..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Acesse: http://localhost:$PORT" -ForegroundColor Cyan
Write-Host ""

node server.js
