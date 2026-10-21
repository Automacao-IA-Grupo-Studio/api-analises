$PORT = if ($env:PORT) { $env:PORT } else { "3000" }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan

# 1. Docker precisa estar aberto (nao tenta abrir nem matar nada dele)
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop nao esta rodando. Abra-o e rode .\start.ps1 de novo." -ForegroundColor Red
    exit 1
}

# 2. Remove container antigo da API (ele ocupava a porta 3000); MySQL nao e tocado
docker rm -f api-analises *> $null

# 3. Sobe so o MySQL e espera ficar pronto
docker compose up mysql -d
for ($i = 1; $i -le 30; $i++) {
    docker compose exec -T mysql mysqladmin ping -h localhost -u root -pstudiofiscal --silent *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
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
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "Acesse: http://localhost:$PORT" -ForegroundColor Green
node server.js
