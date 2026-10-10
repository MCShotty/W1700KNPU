$ErrorActionPreference = 'Stop'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$here = Join-Path $repo '.local\npu-cold-wire-20261010'
$receipt = Get-Content -Raw -LiteralPath (Join-Path $repo '.local\merge-nonoc-20260923\cold-wire-20261010-offline\result.json') | ConvertFrom-Json
$row = $receipt.selected_modules.'airoha_npu.ko'
$inputFile = Join-Path $repo ($row.path -replace '/', '\')
if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256) { throw 'Packaged provider differs' }
$project = Join-Path $repo 'scratch\npu-cold-wire-20261010'
$out = Join-Path $here 'ghidra-full'
if (Test-Path -LiteralPath $project) { throw 'Preserve existing Ghidra project' }
New-Item -ItemType Directory -Path $project,$out | Out-Null
$arguments = @($project,'ColdWire','-max-cpu','2','-analysisTimeoutPerFile','900',
    '-log',(Join-Path $out 'analysis.log'),'-scriptlog',(Join-Path $out 'script.log'),
    '-import',$inputFile,'-scriptPath',(Join-Path $repo 'tools\ghidra'),
    '-postScript','ExportMailboxContract.java',$out,(Join-Path $here 'all.pattern'))
& 'C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat' @arguments *> (Join-Path $out 'console.log')
if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $LASTEXITCODE" }
$text = Get-Content -Raw -LiteralPath (Join-Path $out 'airoha_npu.ko.txt')
if ($text -notmatch ('sha256=' + $row.sha256) -or $text -match 'decompiled=false' -or $text -notmatch 'failed_decompilations=0') { throw 'Export incomplete' }
if ((Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.log')) -match 'Analysis timed out') { throw 'Analysis timeout' }
'PASS: exact packaged provider cold-wire export'
