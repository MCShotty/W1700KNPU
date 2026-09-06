param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedHash)
$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-preflight\provider'
$out = Join-Path $repo 'research\checkpoints\2026-09-06-npu-preflight\ghidra-provider'
$inputFile = Join-Path $repo '.local\npu-preflight\airoha_npu.o'
if (Test-Path -LiteralPath (Join-Path $project 'MemoryPreflight.gpr')) { throw 'Do not overwrite prior Ghidra project' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $inputFile).Hash.ToLowerInvariant() -ne $ExpectedHash) {
    throw 'Provider object hash mismatch'
}
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$arguments = @($project,'MemoryPreflight','-max-cpu','2','-analysisTimeoutPerFile','300',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$inputFile,'-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\all-functions.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out 'airoha_npu.o.txt')
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') {
    throw 'Incomplete provider decompilation'
}
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') {
    throw 'Auto-analysis timed out'
}
'PASS: full provider auto-analysis and function export'
