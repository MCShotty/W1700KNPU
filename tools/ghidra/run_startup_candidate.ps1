param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedHash)
$ErrorActionPreference = 'Stop'
if ($ExpectedHash -ne '16d330eb21f84e47a7bc9f0e5ff49d2c1552cef241455d48770768ded211850a') {
    throw 'Re-audit the fixed symbol-span seeds for a changed ELF'
}
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-startup\candidate-fixed'
$out = Join-Path $repo 'research\checkpoints\2026-09-06-npu-startup\ghidra-default'
$inputFile = Join-Path $repo '.local\npu-barrier\admission-platform-startup-gdma-gdma-65536.elf'
if (Test-Path -LiteralPath (Join-Path $project 'StartupCandidate.gpr')) { throw 'Prior project exists' }
if ((Get-FileHash -LiteralPath $inputFile).Hash.ToLowerInvariant() -ne $ExpectedHash) { throw 'ELF hash mismatch' }
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$arguments = @($project,'StartupCandidate','-max-cpu','2','-analysisTimeoutPerFile','300',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$inputFile,'-processor','RISCV:LE:32:W1700KNPU','-cspec','gcc',
    '-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-preScript','SetupStartupCandidateMap.java',$ExpectedHash,
    '-postScript','SeedStartupCandidate.java',$ExpectedHash,'8404274a','84042805','84042696','84042749',
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\startup-candidate.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$report = Get-Content -Raw -LiteralPath (Join-Path $out 'admission-platform-startup-gdma-gdma-65536.elf.txt')
if ($report -match 'decompiled=false' -or $report -notmatch 'failed_decompilations=0') { throw 'Incomplete decompilation' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Analysis timeout' }
'PASS: startup candidate ELF analysis and export'
