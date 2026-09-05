$ErrorActionPreference = 'Stop'
$profile = [IO.Path]::GetFullPath('C:\Users\captain')
if ((Get-Item -LiteralPath $profile -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Profile root is a reparse point' }
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$relativeRoots = @(
    'AppData\Local\NVIDIA\DXCache', 'AppData\Local\NVIDIA\GLCache',
    'AppData\Local\D3DSCache', 'AppData\Local\Steam\htmlcache\Cache',
    'AppData\Local\Steam\htmlcache\Code Cache', 'AppData\Local\Steam\htmlcache\GPUCache',
    'AppData\Roaming\discord\Cache', 'AppData\Roaming\discord\Code Cache',
    'AppData\Roaming\discord\GPUCache', 'AppData\Roaming\Cursor\Cache',
    'AppData\Roaming\Cursor\Code Cache', 'AppData\Roaming\Cursor\GPUCache',
    'AppData\Local\Microsoft\Edge\User Data\Default\Cache',
    'AppData\Local\Microsoft\Edge\User Data\Default\Code Cache',
    'AppData\Local\Microsoft\Edge\User Data\Default\GPUCache',
    'AppData\Local\Google\Chrome\User Data\Default\Cache',
    'AppData\Local\Google\Chrome\User Data\Default\Code Cache',
    'AppData\Local\Google\Chrome\User Data\Default\GPUCache'
)
$results = @()
foreach ($relative in $relativeRoots) {
    $root = [IO.Path]::GetFullPath((Join-Path $profile $relative))
    if (-not $root.StartsWith($profile + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Outside profile' }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    $ancestor = Get-Item -LiteralPath $root -Force
    while ($ancestor.FullName -ne $profile) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Cache ancestor is a reparse point: $root" }
        $ancestor = $ancestor.Parent
        if (-not $ancestor) { throw 'Unexpected path ancestor' }
    }
    $stack = [Collections.Generic.Stack[string]]::new()
    $stack.Push($root)
    $files = 0; $bytes = [long]0; $skipped = 0
    while ($stack.Count) {
        $directory = $stack.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $directory -Force -ErrorAction SilentlyContinue) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $skipped++; continue }
            $path = [IO.Path]::GetFullPath($item.FullName)
            if (-not $path.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Outside exact cache root' }
            if ($item.PSIsContainer) { $stack.Push($path); continue }
            try {
                $size = $item.Length
                Remove-Item -LiteralPath $path -Force -ErrorAction Stop
                $files++; $bytes += $size
            } catch { $skipped++ }
        }
    }
    $results += [pscustomobject]@{ Cache=$relative; RemovedFiles=$files; RemovedLogicalBytes=$bytes; LockedOrSkipped=$skipped }
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $repo '.local\cleanup-20260905\windows-cache-removals.json') -Encoding utf8
}
[pscustomobject]@{ RemovedFiles=($results | Measure-Object RemovedFiles -Sum).Sum; RemovedLogicalBytes=($results | Measure-Object RemovedLogicalBytes -Sum).Sum; Skipped=($results | Measure-Object LockedOrSkipped -Sum).Sum }
