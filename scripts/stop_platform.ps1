$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PidPath = Join-Path $ProjectRoot 'data\server.pid'
$ExpectedPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Process = $null
if (Test-Path -LiteralPath $PidPath) {
  $SavedId = [int](Get-Content -LiteralPath $PidPath)
  $Candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $SavedId" -ErrorAction SilentlyContinue
  if ($Candidate -and $Candidate.ExecutablePath -eq $ExpectedPython -and $Candidate.CommandLine -like '*uvicorn backend.main:app*') { $Process = $Candidate }
}
if (-not $Process) {
  $Process = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -eq $ExpectedPython -and $_.CommandLine -like '*uvicorn backend.main:app*'
  } | Select-Object -First 1
}
if ($Process) {
  # Stop only this app's process tree, including any active ASR/VLM subprocess.
  taskkill /PID $Process.ProcessId /T /F
  if ($LASTEXITCODE -ne 0) { throw 'Could not stop the platform process.' }
  Write-Output 'Platform stopped. Unfinished jobs resume on next start.'
} else { Write-Output 'No running platform process found.' }
Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
