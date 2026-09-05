$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-quiescence\stock-kernel'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-quiescence\ghidra-kernel'
$input = Join-Path $repo 'research\stock\elf\stock-kernel.vmlinux.elf'
if (Test-Path -LiteralPath (Join-Path $project 'StockMailbox.gpr')) { throw 'Do not overwrite prior Ghidra project' }
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$pattern = Join-Path $repo 'tools\ghidra\kernel-mailbox.pattern'
$arguments = @($project,'StockMailbox','-max-cpu','2','-analysisTimeoutPerFile','1800',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$input,'-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-postScript','ExportMailboxContract.java',$out,$pattern)
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out 'stock-kernel.vmlinux.elf.txt')
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') { throw 'Incomplete mailbox decompilation' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Auto-analysis timed out' }
'PASS: full stock kernel auto-analysis and mailbox function export'
