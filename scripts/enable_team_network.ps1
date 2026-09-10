# Optional: run as administrator only if Windows Firewall blocks LAN access.
$ErrorActionPreference = 'Stop'
$RuleName = '片析团队工作台 8765'
if (-not (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private -RemoteAddress LocalSubnet
}
Write-Output 'LAN access allowed on private networks for local-subnet clients only.'
