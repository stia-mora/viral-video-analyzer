param([int]$Port = 8765, [string]$Bind = '0.0.0.0', [switch]$Foreground)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Please run scripts\setup_platform.ps1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\dist\index.html'))) { throw 'Frontend build missing. Run npm --prefix frontend run build.' }
Push-Location $ProjectRoot
try {
  & $PythonExe scripts/init_platform.py
  if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
  if ($Foreground) {
    & $PythonExe -m uvicorn backend.main:app --host $Bind --port $Port
  } else {
    $PidPath = Join-Path $ProjectRoot 'data\server.pid'
    $Existing = Get-CimInstance Win32_Process | Where-Object {
      $_.CommandLine -like '*uvicorn backend.main:app*' -and $_.ExecutablePath -eq $PythonExe
    } | Select-Object -First 1
    if ($Existing) {
      Set-Content -LiteralPath $PidPath -Value $Existing.ProcessId
      Write-Output "Platform already running: PID $($Existing.ProcessId)"
      return
    }
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
    $Process = Start-Process -FilePath $PythonExe -ArgumentList @('-m','uvicorn','backend.main:app','--host',$Bind,'--port',"$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ProjectRoot 'data\server.log') -RedirectStandardError (Join-Path $ProjectRoot 'data\server-error.log')
    Set-Content -LiteralPath $PidPath -Value $Process.Id
    Write-Output "Platform started: http://localhost:$Port (PID $($Process.Id))"
  }
} finally { Pop-Location }
