$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-reset\stock-modules'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-reset\ghidra-modules'
$inputs = Join-Path $repo '.local\npu-reset\inputs'
$targets = Join-Path $repo 'research\checkpoints\2026-09-05-npu-quiescence\inventory\ghidra_targets.tsv'
if (Test-Path -LiteralPath (Join-Path $project 'StockReset.gpr')) { throw 'Do not overwrite prior Ghidra project' }
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
foreach ($name in @('mtk_pci.ko','mtk_hwifi.ko','mt7990.ko','mt_wifi.ko')) {
    $arguments = @($project,'StockReset','-max-cpu','2','-analysisTimeoutPerFile','1800',
        '-log',(Join-Path $out ($name + '.analysis.log')),
        '-scriptlog',(Join-Path $out ($name + '.script.log')),
        '-import',(Join-Path $inputs $name),'-scriptPath',(Join-Path $repo 'tools\ghidra'),
        '-preScript','SeedResetTargets.java',$targets,
        '-postScript','ExportResetTargets.java',$out,$targets,
        (Join-Path $repo 'tools\ghidra\reset-coordinator.pattern'))
    & 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
    if ($LASTEXITCODE -ne 0) { throw "Ghidra failed for ${name}: $LASTEXITCODE" }
    $report = Get-Content -Raw -LiteralPath (Join-Path $out ($name + '.txt'))
    if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') {
        throw "Incomplete reset decompilation: $name"
    }
    if ((Get-Content -Raw -LiteralPath (Join-Path $out ($name + '.analysis.log'))) -match 'Analysis timed out') {
        throw "Auto-analysis timeout: $name"
    }
    "PASS: full $name auto-analysis and reset target export"
}
