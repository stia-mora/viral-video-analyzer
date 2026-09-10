param(
  [Parameter(Mandatory = $true)]
  [string]$Url,

  [string]$VaultPath,
  [string]$EnvName,
  [ValidateSet('Chinese', 'English', 'auto')]
  [string]$Language,
  [ValidateSet('auto', 'always', 'off')]
  [string]$Timestamps,
  [string]$Format = 'best',
  [switch]$SkipDownload
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$configPath = Join-Path $ProjectRoot 'config\defaults.json'
$config = Get-Content -Encoding UTF8 -Raw -LiteralPath $configPath | ConvertFrom-Json

if (-not $EnvName) { $EnvName = $config.conda_env }
if (-not $Language) { $Language = $config.language }
if (-not $Timestamps) { $Timestamps = $config.timestamps }
if (-not $VaultPath) { $VaultPath = if ($env:OBSIDIAN_VAULT_PATH) { $env:OBSIDIAN_VAULT_PATH } else { $config.obsidian_vault_path } }

$videoId = $null
if ($Url -match 'modal_id=(\d+)') { $videoId = $Matches[1] }
elseif ($Url -match '/video/(\d+)') { $videoId = $Matches[1] }
if (-not $videoId) { throw "Could not find Douyin video id from URL: $Url" }

$videoUrl = "https://www.douyin.com/video/$videoId"
$out = Join-Path $ProjectRoot "outputs\douyin\$videoId"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'
$env:HF_HOME = Join-Path $ProjectRoot $config.hf_cache
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'

if (-not $SkipDownload) {
  conda run -n $EnvName python -m yt_dlp --no-playlist --write-info-json --no-mtime -f $Format -o "$out\video.%(ext)s" $videoUrl
}

$videoFile = Get-ChildItem -LiteralPath $out -File |
  Where-Object { $_.Name -like 'video.*' -and $_.Name -notlike '*.info.json' -and $_.Extension -notin @('.part', '.ytdl') } |
  Sort-Object Length -Descending |
  Select-Object -First 1
if (-not $videoFile) { throw "No downloaded video file found in $out" }

$audio = Join-Path $out 'audio.wav'
ffmpeg -y -i $videoFile.FullName -ar 16000 -ac 1 -c:a pcm_s16le $audio

conda run -n $EnvName python (Join-Path $ProjectRoot 'scripts\qwen3_asr_transcribe.py') --audio $audio --out-dir $out --language $Language --timestamps $Timestamps

$notePath = python (Join-Path $ProjectRoot 'scripts\write_obsidian_note.py') --out-dir $out --vault $VaultPath

Write-Output "video_id=$videoId"
Write-Output "out_dir=$out"
Write-Output "note=$notePath"

