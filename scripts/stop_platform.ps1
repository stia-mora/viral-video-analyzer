$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PidPath = Join-Path $ProjectRoot 'data\server.pid'
if (-not (Test-Path -LiteralPath $PidPath)) { Write-Output 'No saved server PID.'; exit 0 }
$SavedId = [int](Get-Content -LiteralPath $PidPath)
$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $SavedId" -ErrorAction SilentlyContinue
$ExpectedPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if ($Process -and $Process.ExecutablePath -eq $ExpectedPython -and $Process.CommandLine -like '*uvicorn backend.main:app*') {
  # Stop only this app's process tree, including any active ASR/VLM subprocess.
  taskkill /PID $SavedId /T /F
  if ($LASTEXITCODE -ne 0) { throw 'Could not stop the platform process.' }
  Write-Output 'Platform stopped. Unfinished jobs resume on next start.'
} elseif ($Process) { throw 'PID belongs to a different process; refusing to stop it.' }
Remove-Item -LiteralPath $PidPath
