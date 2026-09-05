param([ValidateSet('Audit','Apply')][string]$Mode = 'Audit')
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath('C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult')
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$planPath = Join-Path $repo '.migration\obsolete-images-plan.json'
$protectedHashes = @('0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f',
                     '502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56')
$cutoff = [datetime]'2026-09-01T00:00:00Z'
if ($Mode -eq 'Audit') {
    $rows = @()
    foreach ($f in Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.itb') {
        if ($f.LastWriteTimeUtc -ge $cutoff -or $f.FullName -match '(?i)recovery|initram|factory|calibration|bootloader|rollback|V6\.87|Daybreak21') { continue }
        if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        $stream = $f.OpenRead()
        try { $magic = New-Object byte[] 4; [void]$stream.Read($magic,0,4) } finally { $stream.Dispose() }
        if ([Convert]::ToHexString($magic) -ne 'D00DFEED') { continue }
        $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -in $protectedHashes) { continue }
        $rows += [pscustomobject]@{ Path=$f.FullName; SHA256=$hash; Bytes=$f.Length; LastWriteUtc=$f.LastWriteTimeUtc.ToString('o') }
    }
    $rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $planPath -Encoding utf8
    [pscustomobject]@{ Images=$rows.Count; Bytes=($rows | Measure-Object Bytes -Sum).Sum }
    exit
}
if (-not (Test-Path -LiteralPath (Join-Path $repo '.migration\remote-verified.json'))) {
    throw 'Verify the repository upload before retiring old firmware outputs'
}
$done = @()
foreach ($entry in @(Get-Content -Raw -LiteralPath $planPath | ConvertFrom-Json)) {
    $path = [IO.Path]::GetFullPath($entry.Path)
    if (-not $path.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($path) -ne '.itb' -or
        $path -match '(?i)recovery|initram|factory|calibration|bootloader|rollback|V6\.87|Daybreak21') {
        throw "Protected/out-of-scope path: $path"
    }
    $f = Get-Item -LiteralPath $path -Force
    if ($f.LastWriteTimeUtc -ge $cutoff -or $f.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Changed file' }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.SHA256 -or $hash -in $protectedHashes) { throw 'Changed/protected image hash' }
    Remove-Item -LiteralPath $path
    $done += $entry
    $done | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $repo '.migration\obsolete-images-removed.json') -Encoding utf8
}
[pscustomobject]@{ RemovedImages=$done.Count; Bytes=($done | Measure-Object Bytes -Sum).Sum }
