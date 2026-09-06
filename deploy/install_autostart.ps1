$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TaskName = "LM_SJ_Backend"
$ScriptPath = Join-Path $ProjectRoot "deploy\start_lm_sj.ps1"

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "启动脚本不存在: $ScriptPath"
}

$PowerShell = (Get-Command powershell.exe).Source
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Start LM_SJ backend after user logon" -Force | Out-Null
Write-Output "已注册开机启动任务: $TaskName"
