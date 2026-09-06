param(
    [string]$OutputPath,
    [switch]$FunctionsOnly
)

$ErrorActionPreference = 'Stop'

function ConvertTo-WifiBaseline {
    param($Board, $Npu, $Wireless, $Uci, $Hostapd)

    if ($Board.board_name -ne 'gemtek,w1700k-ubi' -or
        $Board.model -ne 'Gemtek W1700K (OpenWrt U-Boot layout)') {
        throw 'Device identity mismatch'
    }
    foreach ($inputPair in @(@($Uci, 'values'), @($Hostapd, 'interfaces'), @($Npu, 'npu'))) {
        if ($null -eq $inputPair[0] -or
            $null -eq $inputPair[0].PSObject.Properties[$inputPair[1]] -or
            $inputPair[0].($inputPair[1]) -isnot [pscustomobject]) {
            throw "Incomplete response: $($inputPair[1])"
        }
    }
    if ($Wireless -isnot [pscustomobject]) { throw 'Incomplete wireless response' }
    $sections = @($Uci.values.PSObject.Properties | ForEach-Object Value)
    $networks = @($sections | Where-Object { $_.'.type' -eq 'wifi-iface' })
    $mlds = @($sections | Where-Object { $_.'.type' -eq 'wifi-mld' })
    $runtimeInterfaces = 0
    $radios = @($Wireless.PSObject.Properties | ForEach-Object {
        $radio = $_.Value
        foreach ($field in @('up', 'pending', 'disabled', 'interfaces')) {
            if ($null -eq $radio.PSObject.Properties[$field]) {
                throw "Incomplete radio response: $field"
            }
        }
        foreach ($field in @('up', 'pending', 'disabled')) {
            if ($radio.$field -isnot [bool]) { throw "Invalid radio boolean: $field" }
        }
        if ($radio.interfaces -isnot [array]) { throw 'Invalid radio interface array' }
        $interfaceCount = @($radio.interfaces).Count
        $runtimeInterfaces += $interfaceCount
        [ordered]@{
            Up = [bool]$radio.up
            Pending = [bool]$radio.pending
            Disabled = [bool]$radio.disabled
            Band = $radio.config.band
            Channel = $radio.config.channel
            Htmode = $radio.config.htmode
            Country = $radio.config.country
            RuntimeInterfaceCount = $interfaceCount
        }
    })
    $hostapdInterfaces = @($Hostapd.interfaces.PSObject.Properties).Count
    $configurationEmpty = $networks.Count -eq 0 -and $mlds.Count -eq 0
    $decision = if ($configurationEmpty -and ($hostapdInterfaces -gt 0 -or $runtimeInterfaces -gt 0)) {
        'configuration-runtime-mismatch'
    } elseif ($configurationEmpty) {
        'no-configured-networks'
    } elseif ($hostapdInterfaces -eq 0) {
        'no-hostapd-interfaces'
    } else {
        'hostapd-interfaces-present-unvalidated'
    }
    [ordered]@{
        Schema = 1
        Board = $Board.board_name
        Model = $Board.model
        Kernel = $Board.kernel
        ReleaseRevision = $Board.release.revision
        RuntimeNpu = $Npu.npu.runtime_state
        WlanNpuCompiledSupport = $Npu.npu.compiled_support
        NpuProviderAttached = $Npu.npu.provider_attached
        RadioCount = $radios.Count
        Radios = $radios
        ConfiguredWifiInterfaceCount = $networks.Count
        ConfiguredMldSectionCount = $mlds.Count
        RuntimeInterfaceCount = $runtimeInterfaces
        HostapdInterfaceCount = $hostapdInterfaces
        Decision = $decision
        ConfigurationValuesRedacted = $true
        BeaconValidated = $false
        ClientAssociationValidated = $false
        ClientTrafficValidated = $false
        ConfigurationWrites = $false
        ModuleLoads = $false
        FlashPerformed = $false
        Scope = 'Read-only configuration and process presence, not RF or client acceptance'
    }
}

if ($FunctionsOnly) { return }

$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$source = '192.168.1.224'
$pin = '//wsl.localhost/Ubuntu/home/captain/W1700KNPU/.local/ssh/w1700k.known_hosts'
if (-not (Get-NetIPAddress -InterfaceAlias Ethernet -AddressFamily IPv4 |
          Where-Object IPAddress -eq $source)) {
    throw 'Verified Ethernet source unavailable; do not fall back to host WiFi'
}

function Read-RouterJson([string]$Command) {
    $raw = & ssh.exe -b $source -o BatchMode=yes -o StrictHostKeyChecking=yes `
        -o "UserKnownHostsFile=$pin" -o ConnectTimeout=5 root@192.168.1.1 $Command
    if ($LASTEXITCODE -ne 0) { throw "Pinned router read failed: $Command" }
    ($raw -join "`n") | ConvertFrom-Json
}

$started = [datetime]::UtcNow.ToString('o')
$board = Read-RouterJson 'ubus call system board'
if ($board.board_name -ne 'gemtek,w1700k-ubi' -or
    $board.model -ne 'Gemtek W1700K (OpenWrt U-Boot layout)') {
    throw 'Device identity mismatch'
}
$npu = Read-RouterJson '/usr/sbin/w1700k-wlan-npu-mode json'
$wireless = Read-RouterJson 'ubus call network.wireless status'
# Keep credential-bearing configuration in memory; export only allowlisted fields.
$uci = Read-RouterJson 'ubus call uci get ''{"config":"wireless"}'''
$hostapd = Read-RouterJson 'ubus call hostapd status'
$result = ConvertTo-WifiBaseline $board $npu $wireless $uci $hostapd
$result['CaptureStartedUtc'] = $started
$result['CapturedUtc'] = [datetime]::UtcNow.ToString('o')
$result['EthernetBound'] = $true
$result['StrictHostKeyChecking'] = $true
$json = $result | ConvertTo-Json -Depth 6
if ($OutputPath) {
    $canonical = [IO.Path]::GetFullPath($repo).TrimEnd('\') + '\'
    $target = [IO.Path]::GetFullPath($OutputPath)
    if (-not $target.StartsWith($canonical, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Output must stay in the canonical workspace'
    }
    if (Test-Path -LiteralPath $target) { throw 'Refusing to overwrite an existing capture' }
    $parent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $json | Set-Content -LiteralPath $target -Encoding utf8
}
$json
