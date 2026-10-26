# Uso:
#   .\start.ps1
#
# Garante que o MySQL (Docker) e a API (PM2) estao no ar. E chamado
# automaticamente no logon (via a tarefa agendada criada por instalar-vm.ps1),
# mas tambem pode ser rodado manualmente a qualquer momento - e idempotente.
#
# Para gerar o pacote desktop autocontido (sem API/banco, resultado em .txt),
# use .\build.ps1 em vez deste script.

$PORT = if ($env:PORT) { $env:PORT } else { "3030" }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# 1. MySQL (Docker)
Write-Host "Subindo MySQL (docker compose)..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) { Write-Host "Falha ao subir o MySQL via Docker. Confira se o Docker Desktop esta aberto." -ForegroundColor Red; exit 1 }

# 2. Dependencias
if (-not (Test-Path "node_modules")) { npm install }

# 3. API via PM2
if (-not (Get-Command pm2 -ErrorAction SilentlyContinue)) {
    Write-Host "PM2 nao encontrado. Rode init_vm.txt primeiro (ele instala o PM2)." -ForegroundColor Red
    exit 1
}

$env:PORT = $PORT
pm2 start ecosystem.config.js --update-env | Out-Null
pm2 save | Out-Null

Write-Host "Acesse: http://localhost:$PORT  (de outra maquina: http://IP-DA-VM:$PORT)" -ForegroundColor Green
Write-Host "Para ver os logs da API:  pm2 logs api-analises" -ForegroundColor Yellow
Write-Host "Para ver o status:        pm2 status" -ForegroundColor Yellow
