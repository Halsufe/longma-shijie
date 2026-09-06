$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\python.exe"
$Port = 8000
$OutLog = Join-Path $ProjectRoot "server-autostart.out.log"
$ErrLog = Join-Path $ProjectRoot "server-autostart.err.log"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "项目虚拟环境不存在: $PythonPath"
}

# Avoid starting a second copy when the task is triggered more than once.
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    exit 0
}

Start-Sleep -Seconds 5
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    exit 0
}

Start-Process -FilePath $PythonPath `
    -ArgumentList "run.py" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog
