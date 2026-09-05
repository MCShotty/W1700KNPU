$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-quiescence\stock-kernel'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-reset\ghidra-kernel'
if (!(Test-Path -LiteralPath (Join-Path $project 'StockMailbox.gpr'))) { throw 'Analyzed stock kernel project missing' }
if (Test-Path -LiteralPath (Join-Path $out 'stock-kernel.vmlinux.elf.txt')) { throw 'Do not overwrite previous export' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$arguments = @($project,'StockMailbox','-noanalysis','-readOnly',
    '-log',(Join-Path $out 'reexport.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-process','stock-kernel.vmlinux.elf','-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\kernel-npu-all.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out 'stock-kernel.vmlinux.elf.txt')
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0' -or
    $report -notmatch 'sha256=a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e') {
    throw 'Incomplete or mismatched kernel NPU export'
}
'PASS: read-only export from fully analyzed stock kernel'
