$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'venv failed' } }
  & .venv\Scripts\python.exe -m pip install -r requirements-platform-lock.txt
  if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed' }
  & .venv\Scripts\python.exe -m playwright install chromium
  if ($LASTEXITCODE -ne 0) { throw 'Browser install failed' }
  npm --prefix frontend ci
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed' }
  npm --prefix frontend run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
  & .venv\Scripts\python.exe scripts/init_platform.py
} finally { Pop-Location }
