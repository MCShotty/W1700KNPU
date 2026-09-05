$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$root = [IO.Path]::GetFullPath('C:\Users\captain\Downloads')
if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Downloads root is a reparse point' }
$plan = Get-Content -Raw -LiteralPath (Join-Path $repo '.local\cleanup-20260905\installer-duplicates.json') | ConvertFrom-Json
$archive = [IO.Path]::GetFullPath($plan.archive)
if ($archive -ne (Join-Path $root 'Downloads.zip')) { throw 'Unexpected backup archive' }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $plan.archive_sha256) { throw 'Backup archive changed' }
$running = @(Get-CimInstance Win32_Process | Select-Object -ExpandProperty ExecutablePath -ErrorAction SilentlyContinue)
$result = @(); $skipped = @()
foreach ($entry in $plan.verified_duplicates) {
    $path = [IO.Path]::GetFullPath($entry.path)
    if (-not $path.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Outside Downloads' }
    $relative = $path.Substring($root.Length + 1)
    $allowed = (([IO.Path]::GetDirectoryName($path) -eq $root) -and
        (([IO.Path]::GetExtension($path) -eq '.exe' -and $relative -match '(?i)setup|installer|^git-\d|^python-\d|^gfx_win_|^jdk-\d') -or
         [IO.Path]::GetExtension($path) -in @('.msi','.msu') -or
         $relative -eq 'ghidra_12.1.2_PUBLIC_20260605.zip')) -or
        $relative -in @('DaVinci.Resolve.Studio.v20.0.0.49.KpoJIuK\DaVinci.Resolve.Studio.v20.0.0.49.part1.exe',
                       'DaVinci.Resolve.Studio.v20.0.0.49.KpoJIuK\DaVinci.Resolve.Studio.v20.0.0.49.part2.rar')
    if (-not $path.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase) -or -not $allowed -or $path -eq $archive) {
        throw 'Installer cleanup scope mismatch'
    }
    if ($path -in $running) { $skipped += $path; continue }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
    $parent = $item.Directory
    while ($parent.FullName -ne $root) {
        if ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse ancestor refused' }
        $parent = $parent.Parent
        if (-not $parent) { throw 'Outside Downloads' }
    }
    if ($item.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw 'Installer changed after verification'
    }
    try {
        Remove-Item -LiteralPath $path -Force
        $result += $entry
    } catch { $skipped += $path }
    [pscustomobject]@{Archive=$archive; ArchiveSHA256=$plan.archive_sha256; Removed=$result; Skipped=$skipped} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $repo '.local\cleanup-20260905\installer-removals.json') -Encoding utf8
}
[pscustomobject]@{ RemovedFiles=$result.Count; RemovedBytes=($result | Measure-Object bytes -Sum).Sum; Skipped=$skipped.Count }
