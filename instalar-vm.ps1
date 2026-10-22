# Rodar UMA vez na VM, em PowerShell como Administrador:
#   .\instalar-vm.ps1
#Requires -RunAsAdministrator
$PORT = 3030
$dir  = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Libera a porta no firewall do Windows
Remove-NetFirewallRule -DisplayName "API Analises" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "API Analises" -Direction Inbound -Protocol TCP `
    -LocalPort $PORT -Action Allow -Profile Any | Out-Null
Write-Host "Firewall: porta $PORT liberada" -ForegroundColor Green

# 2. Sobe a API sozinha quando este usuario fizer logon (acessa o \\studiofiscal com as credenciais dele)
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $dir `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\start.ps1`""
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
Register-ScheduledTask -TaskName "API Analises" -Action $acao -Trigger $gatilho `
    -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -Force | Out-Null
Write-Host "Tarefa agendada 'API Analises' criada (inicia no logon)" -ForegroundColor Green

Write-Host "`nAcesse de outra maquina: http://$((Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127|169)' } | Select-Object -First 1).IPAddress):$PORT" -ForegroundColor Cyan
