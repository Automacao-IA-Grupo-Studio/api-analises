# Uso:
#   .\start.ps1               -> MySQL no Docker (precisa do Docker Desktop)
#   .\start.ps1 -SemDocker    -> MySQL instalado direto no Windows (VM sem Docker)
param([switch]$SemDocker)

$PORT = if ($env:PORT) { $env:PORT } else { "3030" }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

if (-not $SemDocker) {
    # 1. Docker precisa estar aberto (nao tenta abrir nem matar nada dele)
    $dockerOk = $false
    for ($i = 1; $i -le 60; $i++) {
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
        if ($i -eq 1) { Write-Host "Aguardando o Docker Desktop (abra-o se nao iniciar sozinho)..." -ForegroundColor Yellow }
        Start-Sleep -Seconds 3
    }
    if (-not $dockerOk) {
        Write-Host "Docker Desktop nao respondeu em 3 min. Abra-o e rode .\start.ps1 de novo." -ForegroundColor Red
        exit 1
    }

    # 2. Remove container antigo da API (ele ocupava a porta 3030); MySQL nao e tocado
    docker rm -f api-analises *> $null

    # 3. Sobe so o MySQL e espera ficar pronto
    docker compose up mysql -d
    for ($i = 1; $i -le 30; $i++) {
        docker compose exec -T mysql mysqladmin ping -h localhost -u root -pstudiofiscal --silent *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 2
    }
} else {
    # MySQL nativo: so espera a porta do .env responder
    $dbPort = 3306
    $linha = Select-String -Path ".env" -Pattern '^DB_PORT=(\d+)' | Select-Object -First 1
    if ($linha) { $dbPort = [int]$linha.Matches[0].Groups[1].Value }
    $mysqlOk = $false
    for ($i = 1; $i -le 30; $i++) {
        if (Test-NetConnection -ComputerName localhost -Port $dbPort -InformationLevel Quiet -WarningAction SilentlyContinue) { $mysqlOk = $true; break }
        if ($i -eq 1) { Write-Host "Aguardando o MySQL na porta $dbPort..." -ForegroundColor Yellow }
        Start-Sleep -Seconds 2
    }
    if (-not $mysqlOk) {
        Write-Host "MySQL nao respondeu na porta $dbPort. Confira o servico (services.msc) e o .env." -ForegroundColor Red
        exit 1
    }
}

# 4. Libera a porta SO se quem a usa for um processo node
$conns = Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq "node") {
        Stop-Process -Id $proc.Id -Force
        Write-Host "node antigo (PID $($proc.Id)) encerrado" -ForegroundColor Yellow
    } elseif ($proc) {
        Write-Host "Porta $PORT em uso por '$($proc.ProcessName)' - NAO encerrado. Mude PORT no .env." -ForegroundColor Red
        exit 1
    }
}

# 5. Dependencias e servidor
if (-not (Test-Path "node_modules")) { npm install }

$env:PORT = $PORT
Write-Host "Acesse: http://localhost:$PORT  (de outra maquina: http://IP-DA-VM:$PORT)" -ForegroundColor Green
node server.js
