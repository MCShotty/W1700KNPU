$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-quiescence\provider'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-quiescence\ghidra-provider'
$input = Join-Path $repo '.local\npu-quiescence\artifacts\airoha_npu.o'
if (Test-Path -LiteralPath (Join-Path $project 'CurrentMailbox.gpr')) { throw 'Do not overwrite prior Ghidra project' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $input).Hash.ToLowerInvariant() -ne '5b025cfa3ae234909ff4164f42a789b08390248de471cbf803afecad65374a68') {
    throw 'Provider object hash mismatch'
}
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$pattern = Join-Path $repo 'tools\ghidra\provider-mailbox.pattern'
$arguments = @($project,'CurrentMailbox','-max-cpu','2','-analysisTimeoutPerFile','300',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$input,'-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-postScript','ExportMailboxContract.java',$out,$pattern)
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out 'airoha_npu.o.txt')
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') { throw 'Incomplete provider decompilation' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Auto-analysis timed out' }
'PASS: full provider auto-analysis and mailbox function export'
