$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$target = 'C:\Tools\ghidra_12.1.2_PUBLIC\Ghidra\Processors\RISCV\data\languages'
foreach ($name in @('w1700k_npu.slaspec','w1700k_npu.ldefs')) {
    $source = Join-Path $repo "tools\ghidra\language\$name"
    $destination = Join-Path $target $name
    if (Test-Path -LiteralPath $destination) {
        if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
            throw 'Existing custom language differs; review before replacing'
        }
    } else { Copy-Item -LiteralPath $source -Destination $destination }
}
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\sleigh.bat' (Join-Path $target 'w1700k_npu.slaspec') (Join-Path $target 'w1700k_npu.sla')
if ($LASTEXITCODE -ne 0) { throw "SLEIGH compilation failed: $LASTEXITCODE" }
Get-FileHash -LiteralPath (Join-Path $target 'w1700k_npu.sla')
