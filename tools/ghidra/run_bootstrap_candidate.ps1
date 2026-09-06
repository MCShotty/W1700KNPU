param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedHash)
$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$out = Join-Path $repo 'research\checkpoints\2026-09-06-npu-bootstrap\ghidra'
$project = Join-Path $repo 'scratch\npu-bootstrap\candidate'
$metadata = Get-Content -Raw -LiteralPath (Join-Path $repo 'research\checkpoints\2026-09-06-npu-bootstrap\analysis-input.json') | ConvertFrom-Json
$inputFile = Join-Path $repo $metadata.elf
if ($metadata.elf_sha256 -ne $ExpectedHash -or
    (Get-FileHash -LiteralPath $inputFile).Hash.ToLowerInvariant() -ne $ExpectedHash) { throw 'ELF identity mismatch' }
if (Test-Path -LiteralPath (Join-Path $project 'BootstrapCandidate.gpr')) { throw 'Prior project exists; do not overwrite its evidence' }
$seeds = @()
foreach ($seed in $metadata.seeds) {
    $seeds += @($seed.name, $seed.start, $seed.end)
}
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$arguments = @($project,'BootstrapCandidate','-max-cpu','2','-analysisTimeoutPerFile','300',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$inputFile,'-processor','RISCV:LE:32:W1700KNPU','-cspec','gcc',
    '-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-preScript','SetupStartupCandidateMap.java',$ExpectedHash,
    '-postScript','SeedBootstrapCandidate.java',$ExpectedHash) + $seeds + @(
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\bootstrap-candidate.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out ((Split-Path -Leaf $inputFile) + '.txt'))
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') { throw 'Incomplete export' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Analysis timeout' }
'PASS: bootstrap candidate ELF analysis and export'
