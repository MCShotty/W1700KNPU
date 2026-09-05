$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$source = '192.168.1.224'
$pin = '//wsl.localhost/Ubuntu/home/captain/W1700KNPU/.local/ssh/w1700k.known_hosts'
if (-not (Get-NetIPAddress -InterfaceAlias Ethernet -AddressFamily IPv4 | Where-Object IPAddress -eq $source)) {
    throw 'Verified Ethernet source is unavailable; do not fall back to host WiFi'
}
function Read-Router([string]$Command) {
    $out = & ssh.exe -b $source -o BatchMode=yes -o StrictHostKeyChecking=yes `
        -o "UserKnownHostsFile=$pin" -o ConnectTimeout=5 root@192.168.1.1 $Command
    if ($LASTEXITCODE -ne 0) { throw 'Pinned router read failed' }
    return $out -join "`n"
}
$board = (Read-Router 'ubus call system board') | ConvertFrom-Json
if ($board.board_name -ne 'gemtek,w1700k-ubi' -or $board.model -ne 'Gemtek W1700K (OpenWrt U-Boot layout)') {
    throw 'Device identity mismatch'
}
$state = (Read-Router '/usr/sbin/w1700k-wlan-npu-mode json') | ConvertFrom-Json
$memory = Read-Router 'grep -E "MemTotal|MemAvailable" /proc/meminfo'
$memTotal = [regex]::Match($memory,'MemTotal:\s+(\d+)').Groups[1].Value
$memAvailable = [regex]::Match($memory,'MemAvailable:\s+(\d+)').Groups[1].Value
if (-not $memTotal -or -not $memAvailable) { throw 'Incomplete memory readback' }
$result = [ordered]@{
    CapturedUtc=[datetime]::UtcNow.ToString('o'); PinnedSsh=$true; EthernetBound=$true
    Board=$board.board_name; Model=$board.model; Kernel=$board.kernel
    RuntimeNpu=$state.npu.runtime_state; CompiledSupport=$state.npu.compiled_support
    ProviderAttached=$state.npu.provider_attached; NpuProviderPresent=$state.npu.npu_provider_present
    MemTotalKiB=[long]$memTotal; MemAvailableKiB=[long]$memAvailable
    ConfigurationWrites=$false; ModuleLoads=$false; FlashPerformed=$false
    Scope='read-only management health; not active-NPU or client-throughput proof'
}
$json = $result | ConvertTo-Json -Depth 4
$json | Set-Content -LiteralPath (Join-Path $repo 'research\checkpoints\2026-09-05-npu-attach\router-baseline.json') -Encoding utf8
$json
