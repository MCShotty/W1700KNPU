$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
. (Join-Path $repo 'tools\router\read_wifi_baseline.ps1') -FunctionsOnly

function Convert-Object([string]$Value) { $Value | ConvertFrom-Json }
function Assert-Equal($Actual, $Expected) {
    if ($Actual -cne $Expected) { throw "Expected '$Expected', got '$Actual'" }
}
function Assert-Rejected([scriptblock]$Run) {
    $rejected = $false
    try { & $Run | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Expected incomplete or wrong-board input to fail' }
}

$board = Convert-Object '{"board_name":"gemtek,w1700k-ubi","model":"Gemtek W1700K (OpenWrt U-Boot layout)","kernel":"test","release":{"revision":"test"}}'
$npu = Convert-Object '{"npu":{"runtime_state":"compiled-out","compiled_support":false,"provider_attached":false}}'
$radio = Convert-Object '{"radio0":{"up":true,"pending":false,"disabled":false,"config":{"band":"2g","channel":"6","ssid":"PRIVATE_SENTINEL","key":"PRIVATE_SENTINEL"},"interfaces":[]}}'
$noConfig = Convert-Object '{"values":{"radio0":{".type":"wifi-device","band":"2g"}}}'
$noHostapd = Convert-Object '{"interfaces":{}}'
$configured = Convert-Object '{"values":{"test":{".type":"wifi-iface","mode":"ap","ssid":"PRIVATE_SENTINEL","key":"PRIVATE_SENTINEL"}}}'
$mld = Convert-Object '{"values":{"test":{".type":"wifi-mld","ssid":"PRIVATE_SENTINEL","key":"PRIVATE_SENTINEL"}}}'
$liveRadio = Convert-Object '{"radio0":{"up":true,"pending":false,"disabled":false,"config":{"band":"2g"},"interfaces":[{"ifname":"PRIVATE_SENTINEL","config":{"ssid":"PRIVATE_SENTINEL","key":"PRIVATE_SENTINEL"}}]}}'
$liveHostapd = Convert-Object '{"interfaces":{"PRIVATE_SENTINEL":{"state":"ENABLED","ssid":"PRIVATE_SENTINEL","key":"PRIVATE_SENTINEL"}}}'
$cases = @()

$result = ConvertTo-WifiBaseline $board $npu $radio $noConfig $noHostapd
Assert-Equal $result.Decision 'no-configured-networks'
Assert-Equal $result.RadioCount 1
Assert-Equal $result.Radios[0].Up $true
Assert-Equal $result.RuntimeInterfaceCount 0
Assert-Equal $result.HostapdInterfaceCount 0
$cases += 'radio-up-is-not-an-ap'

$result = ConvertTo-WifiBaseline $board $npu $radio $configured $noHostapd
Assert-Equal $result.Decision 'no-hostapd-interfaces'
Assert-Equal $result.ConfiguredWifiInterfaceCount 1
$cases += 'configured-is-not-running'

$result = ConvertTo-WifiBaseline $board $npu $liveRadio $configured $liveHostapd
Assert-Equal $result.Decision 'hostapd-interfaces-present-unvalidated'
Assert-Equal $result.RuntimeInterfaceCount 1
Assert-Equal $result.HostapdInterfaceCount 1
foreach ($field in @('BeaconValidated', 'ClientAssociationValidated', 'ClientTrafficValidated',
                     'ConfigurationWrites', 'ModuleLoads', 'FlashPerformed')) {
    Assert-Equal $result[$field] $false
}
if (($result | ConvertTo-Json -Depth 8).Contains('PRIVATE_SENTINEL')) { throw 'Private input leaked' }
$cases += 'process-is-not-client-acceptance-and-private-data-redacted'

$result = ConvertTo-WifiBaseline $board $npu $radio $mld $noHostapd
Assert-Equal $result.Decision 'no-hostapd-interfaces'
Assert-Equal $result.ConfiguredMldSectionCount 1
$cases += 'mld-section-is-not-empty-configuration'

$result = ConvertTo-WifiBaseline $board $npu $liveRadio $noConfig $liveHostapd
Assert-Equal $result.Decision 'configuration-runtime-mismatch'
$cases += 'stale-runtime-not-empty-baseline'

Assert-Rejected { ConvertTo-WifiBaseline (Convert-Object '{"board_name":"wrong"}') $npu $radio $noConfig $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu $radio (Convert-Object '{}') $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu $radio $noConfig (Convert-Object '{}') }
Assert-Rejected { ConvertTo-WifiBaseline $board (Convert-Object '{}') $radio $noConfig $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu (Convert-Object '{"radio0":{"up":true}}') $noConfig $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu $null $noConfig $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu $radio $noConfig (Convert-Object '{"interfaces":[]}') }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu $radio (Convert-Object '{"values":false}') $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu (Convert-Object '{"radio0":{"up":"false","pending":false,"disabled":false,"interfaces":[]}}') $noConfig $noHostapd }
Assert-Rejected { ConvertTo-WifiBaseline $board $npu (Convert-Object '{"radio0":{"up":true,"pending":false,"disabled":false,"interfaces":null}}') $noConfig $noHostapd }
$cases += 'wrong-board-and-nine-incomplete-or-malformed-response-controls'

[ordered]@{Passed=$true; NominalCases=5; RejectionControls=10; Cases=$cases; NetworkCalls=0} | ConvertTo-Json -Depth 4
