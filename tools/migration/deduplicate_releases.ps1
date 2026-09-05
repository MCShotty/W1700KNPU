param([ValidateSet('Audit','Apply')][string]$Mode = 'Audit')
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath('C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult')
$repository = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$receiptDir = Join-Path $repository '.migration'
$planPath = Join-Path $receiptDir 'release-dedup-plan.json'
if ($Mode -eq 'Audit') {
    $rows = @()
    $files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.itb' |
        Where-Object { $_.Length -gt 1MB -and -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) })
    foreach ($group in ($files | Group-Object Length | Where-Object Count -gt 1)) {
        $hashes = @{}
        foreach ($file in ($group.Group | Sort-Object FullName)) {
            $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hashes.ContainsKey($hash)) {
                $rows += [pscustomobject]@{ Path=$file.FullName; Canonical=$hashes[$hash]; SHA256=$hash; Bytes=$file.Length }
            } else { $hashes[$hash] = $file.FullName }
        }
    }
    $rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $planPath -Encoding utf8
    [pscustomobject]@{ DuplicateImages=$rows.Count; PotentialBytes=($rows | Measure-Object Bytes -Sum).Sum }
    exit
}
$results = @()
foreach ($entry in @(Get-Content -Raw -LiteralPath $planPath | ConvertFrom-Json)) {
    $paths = @($entry.Path, $entry.Canonical)
    foreach ($p in $paths) {
        $full = [IO.Path]::GetFullPath($p)
        if (-not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetExtension($full) -ne '.itb') { throw "Outside release-image scope: $p" }
        $item = Get-Item -LiteralPath $full -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
        if ((Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.SHA256) {
            throw "Changed duplicate: $p"
        }
    }
    $temp = $entry.Path + '.dedup-link-' + [guid]::NewGuid().ToString('N')
    $backup = $temp + '.original'
    New-Item -ItemType HardLink -Path $temp -Target $entry.Canonical | Out-Null
    try {
        Move-Item -LiteralPath $entry.Path -Destination $backup
        Move-Item -LiteralPath $temp -Destination $entry.Path
        if ((Get-FileHash -LiteralPath $entry.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.SHA256) {
            throw 'Hardlink verification failed; original backup retained'
        }
        Remove-Item -LiteralPath $backup
        $results += $entry
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp }
    }
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $receiptDir 'release-dedup-completed.json') -Encoding utf8
}
[pscustomobject]@{ LinkedImages=$results.Count; LogicalDuplicateBytes=($results | Measure-Object Bytes -Sum).Sum }
