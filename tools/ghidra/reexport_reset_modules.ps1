$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-reset\stock-modules'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-reset\ghidra-modules-all'
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach ($name in @('mtk_hwifi.ko','mtk_pci.ko')) {
    if (Test-Path -LiteralPath (Join-Path $out ($name + '.txt'))) { throw 'Do not overwrite previous export' }
    $arguments = @($project,'StockReset','-noanalysis','-readOnly',
        '-log',(Join-Path $out ($name + '.reexport.log')),
        '-scriptlog',(Join-Path $out ($name + '.script.log')),
        '-process',$name,'-scriptPath',(Join-Path $repo 'tools\ghidra'),
        '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\all-functions.pattern'))
    & 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
    if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
    $report = Get-Content -Raw -LiteralPath (Join-Path $out ($name + '.txt'))
    if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') {
        throw "Incomplete export: $name"
    }
    "PASS: read-only full export from analyzed $name"
}
