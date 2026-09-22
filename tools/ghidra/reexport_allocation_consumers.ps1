$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$project = Join-Path $repo 'scratch\npu-admission\current-rv32-mailbox'
$out = Join-Path $repo 'research\checkpoints\2026-09-09-npu-memory-budget\ghidra-allocation'
$input = Join-Path $repo '.local\npu-quiescence\firmware\en7581_MT7996_npu_rv32.bin'
if (-not (Test-Path -LiteralPath (Join-Path $project 'CurrentNpu.gpr'))) {
    throw 'The analyzed native program is unavailable'
}
if ((Get-FileHash -LiteralPath $input).Hash.ToLowerInvariant() -ne
    'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643') {
    throw 'Firmware identity changed'
}
$export = Join-Path $out 'en7581_MT7996_npu_rv32.bin.txt'
if (Test-Path -LiteralPath $export) { throw 'Allocation export already exists' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$arguments = @($project, 'CurrentNpu', '-readOnly', '-noanalysis', '-max-cpu', '2',
    '-process', 'en7581_MT7996_npu_rv32.bin',
    '-log', (Join-Path $out 'analysis.log'), '-scriptlog', (Join-Path $out 'script.log'),
    '-scriptPath', (Join-Path $repo 'tools\ghidra'), '-postScript', 'ExportMailboxContract.java',
    $out, (Join-Path $repo 'tools\ghidra\allocation-consumers.pattern'), 'callers')
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra export failed: $LASTEXITCODE" }
$text = Get-Content -Raw -LiteralPath $export
if ($text -notmatch 'sha256=e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643' -or
    $text -match 'decompiled=false' -or $text -notmatch 'failed_decompilations=0' -or
    $text -notmatch 'FUNCTION FUN_ram_84001466' -or $text -notmatch 'FUNCTION npu_table_0f4') {
    throw 'Incomplete allocation export'
}
Get-FileHash -Algorithm SHA256 -LiteralPath $export | Select-Object Path, Hash
