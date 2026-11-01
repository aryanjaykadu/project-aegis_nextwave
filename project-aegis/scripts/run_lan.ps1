$ErrorActionPreference = 'Stop'
$env:AEGIS_LAN_MODE = 'true'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot

$activeInterfaces = @(Get-NetAdapter -ErrorAction SilentlyContinue |
    Where-Object { $_.Status -eq 'Up' } |
    Sort-Object @{ Expression = { if ($_.InterfaceDescription -match 'Wireless|Wi-Fi') { 0 } else { 1 } } })
$lanAddresses = @(
    foreach ($adapter in $activeInterfaces) {
        Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -AddressState Preferred -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            ForEach-Object {
                [PSCustomObject]@{
                    InterfaceAlias = $adapter.Name
                    IPAddress = $_.IPAddress
                }
            }
    }
)
$lanAddress = $lanAddresses | Select-Object -First 1

if ($lanAddress) {
    Write-Host "Project Aegis is starting on $($lanAddress.InterfaceAlias)."
    Write-Host "This computer: http://127.0.0.1:8001/"
    Write-Host "Phone/tablet:  http://$($lanAddress.IPAddress):8001/"
} else {
    Write-Warning 'No active LAN IPv4 address found. Connect this computer to the same Wi-Fi network as your phone.'
}

Write-Warning 'Keep the phone and computer on the same trusted Wi-Fi. LAN mode blocks operator actions until authentication is configured. Plain HTTP may disable phone geolocation and PWA features; use HTTPS with a certificate trusted by the device for those features.'

$localUvicorn = Join-Path $PSScriptRoot '..\.venv\Scripts\uvicorn.exe'
if (Test-Path -LiteralPath $localUvicorn) {
    & $localUvicorn 'backend.main:app' '--host' '0.0.0.0' '--port' '8001'
} else {
    & uvicorn 'backend.main:app' '--host' '0.0.0.0' '--port' '8001'
}
