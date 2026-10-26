# Uso:
#   .\start.ps1    -> roda a API a partir do codigo-fonte (Node + Python do sistema)
#                      banco SQLite local, sem depender de nada externo.
#
# Para gerar o pacote autocontido (.exe, sem precisar de Node/Python/Tesseract
# instalados na maquina de destino), use .\build.ps1 em vez deste script.
param([switch]$SemDocker)  # mantido por compatibilidade; nao tem mais efeito (nao ha mais Docker/MySQL)

$PORT = if ($env:PORT) { $env:PORT } else { "3030" }

Write-Host "=== API Analises - Studio Fiscal ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# 1. Libera a porta SO se quem a usa for um processo node
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

# 2. Dependencias e servidor
if (-not (Test-Path "node_modules")) { npm install }

$env:PORT = $PORT
Write-Host "Acesse: http://localhost:$PORT  (de outra maquina: http://IP-DA-VM:$PORT)" -ForegroundColor Green
node server.js
