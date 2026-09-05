$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath('C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work')
$archiveRoot = [IO.Path]::GetFullPath('C:\Users\captain\Downloads\FW\W1700KNPU-LocalArchives\ghidra')
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$allowed = @('ghidra-v619-ownership-20260717','ghidra-v629-fasttx-direct-20260718',
    'ghidra-v626-fasttx-reason22-20260718','ghidra-v641-airoha-ownership-20260805',
    'ghidra-v646-rro-session-teardown-20260806','ghidra-v662-mib-ring-accounting-20260829',
    'ghidra-v642-hostadpt-tx-headroom-20260805','ghidra-final-20260710')
if (Get-Process java,javaw -ErrorAction SilentlyContinue) { throw 'Ghidra/Java is running; archive removal postponed' }
$result = @()
foreach ($name in $allowed) {
    $receiptPath = Join-Path $archiveRoot ($name + '.tar.receipt.json')
    $r = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
    if ($r.original_deleted) { continue }
    $source = [IO.Path]::GetFullPath($r.source)
    $archive = [IO.Path]::GetFullPath($r.archive)
    if ($source -ne (Join-Path $root $name) -or
        -not $source.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase) -or
        $archive -ne (Join-Path $archiveRoot ($name + '.tar.gz'))) { throw 'Archive/source boundary mismatch' }
    if (-not $r.verified -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $r.archive_sha256) {
        throw 'Archive hash/verification mismatch'
    }
    $items = @(Get-ChildItem -LiteralPath $source -Recurse -Force)
    if ($items.Count -ne $r.entries.Count -or ((Get-Item -LiteralPath $source).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Source inventory/root changed'
    }
    foreach ($e in $r.entries) {
        $p = [IO.Path]::GetFullPath((Join-Path $source ($e.path -replace '/', '\')))
        if (-not $p.StartsWith($source + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Entry outside source' }
        $item = Get-Item -LiteralPath $p -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
        if ($e.type -eq 'file' -and ($item.Length -ne $e.bytes -or
            (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $e.sha256)) {
            throw "Source changed since archive: $p"
        }
    }
    Remove-Item -LiteralPath $source -Recurse -Force
    $r.original_deleted = $true
    $r | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $result += $r | Select-Object source,archive,archive_sha256,archive_bytes,source_bytes,verified,original_deleted
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $repo 'docs\migration\windows-archived-cache-removals.json') -Encoding utf8
}
$result | Select-Object source,source_bytes,archive_bytes,original_deleted
