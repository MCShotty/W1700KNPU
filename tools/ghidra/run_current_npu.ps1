$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-quiescence\current-rv32-decoded'
$out = Join-Path $repo 'research\checkpoints\2026-09-05-npu-quiescence\ghidra-current-rv32-decoded'
$input = Join-Path $repo '.local\npu-quiescence\firmware\en7581_MT7996_npu_rv32.bin'
$data = Join-Path $repo '.local\npu-quiescence\firmware\en7581_MT7996_npu_data.bin'
if (Test-Path -LiteralPath (Join-Path $project 'CurrentNpu.gpr')) { throw 'Prior project exists' }
if ((Get-FileHash -LiteralPath $input).Hash.ToLowerInvariant() -ne 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643' -or
    (Get-FileHash -LiteralPath $data).Hash.ToLowerInvariant() -ne '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1') { throw 'Firmware version changed; revisit mapping' }
New-Item -ItemType Directory -Path $project,$out -Force | Out-Null
$arguments = @($project,'CurrentNpu','-max-cpu','2','-analysisTimeoutPerFile','1800',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$input,'-processor','RISCV:LE:32:W1700KNPU','-cspec','gcc',
    '-loader','BinaryLoader','-loader-baseAddr','0x84000000',
    '-scriptPath',(Join-Path $repo 'tools\ghidra'),'-preScript','SetupCurrentNpuMap.java',$data,
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $repo 'tools\ghidra\all-functions.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$text = Get-Content -Raw -LiteralPath (Join-Path $out 'en7581_MT7996_npu_rv32.bin.txt')
if ($text -match 'decompiled=false' -or $text -notmatch 'failed_decompilations=0') { throw 'Incomplete firmware export' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Analysis timeout' }
'PASS: current NPU full auto-analysis and function export'
