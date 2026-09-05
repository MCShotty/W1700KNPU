param([ValidateSet('stock','candidate')][string]$Variant = 'stock', [switch]$Reexport)
$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$headless = 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat'
$project = Join-Path $repo "scratch\npu-attach\ghidra\$Variant"
$output = Join-Path $repo "research\checkpoints\2026-09-05-npu-attach\ghidra-$Variant"
if ($Variant -eq 'stock') {
    $inputs = @('stock_hostadpt.ko','stock_npu.ko') | ForEach-Object { Join-Path $repo "research\stock\elf\$_" }
    $selection = 'all'
} else {
    $inputs = @(Join-Path $repo '.local\npu-attach\artifacts\npu-enabled\mt7996e.ko')
    $selection = 'current'
}
foreach ($path in $inputs) { if (-not (Test-Path -LiteralPath $path)) { throw "Missing ELF: $path" } }
if ((Test-Path -LiteralPath (Join-Path $project 'NpuLifecycle.gpr')) -and -not $Reexport) { throw 'Prior project exists; use -Reexport for an analyzed project' }
New-Item -ItemType Directory -Path $project,$output -Force | Out-Null
$env:GHIDRA_HEADLESS_MAXMEM = '2G'
$arguments = @($project,'NpuLifecycle','-max-cpu','2','-analysisTimeoutPerFile','900',
    '-log',(Join-Path $output 'analysis.log'),'-scriptlog',(Join-Path $output 'script.log'))
if ($Reexport) { $arguments += @('-process','*.ko','-noanalysis') }
else { $arguments += @('-import') + $inputs }
$arguments += @('-scriptPath',(Join-Path $repo 'tools\ghidra'),'-postScript','ExportNpuLifecycle.java',$output,$selection)
& $headless @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
foreach ($path in $inputs) {
    $report = Join-Path $output ((Split-Path -Leaf $path) + '.txt')
    if (-not (Test-Path -LiteralPath $report)) { throw "Missing decompilation: $report" }
    $text = Get-Content -Raw -LiteralPath $report
    if ($text -match 'decompiled=false' -or $text -notmatch 'failed_decompilations=0') { throw 'Incomplete decompilation' }
}
if ((Get-Content -Raw -LiteralPath (Join-Path $output 'analysis.log')) -match 'Analysis timed out') { throw 'Analysis timed out' }
if ($Reexport) { Write-Output "PASS: $selection lifecycle re-export from existing analyzed project" }
else { Write-Output "PASS: full Ghidra analysis and $selection lifecycle exports" }
