param(
    [string]$Workspace = 'C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand',
    [string]$FinalResult = 'C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult'
)

$ErrorActionPreference = 'Stop'
$bundleName = 'W1700K-V6.87-Corrective-Engineering-20260901'
$imageName = 'w1700k-v6.87-corrective-20260901-sysupgrade.itb'
$bundle = Join-Path $FinalResult $bundleName
$staging = "$bundle.staging"
$expectedImageHash = '502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56'
$buildEvidence = '\\wsl.localhost\Ubuntu\home\captain\w1700k-openwrt-build\v687-release-73a8983-20260901\build-a-evidence'

if (Test-Path -LiteralPath $bundle) {
    throw "release bundle already exists: $bundle"
}
if (Test-Path -LiteralPath $staging) {
    throw "stale release staging directory exists: $staging"
}

function Add-ReleaseFile {
    param(
        [Parameter(Mandatory = $true)] [string]$Source,
        [Parameter(Mandatory = $true)] [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "release input is missing: $Source"
    }
    $target = Join-Path $staging $Destination
    if (Test-Path -LiteralPath $target) {
        throw "duplicate release destination: $Destination"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $target
}

function Add-ReleaseDirectory {
    param(
        [Parameter(Mandatory = $true)] [string]$Source,
        [Parameter(Mandatory = $true)] [string]$Destination,
        [string[]]$Exclude = @()
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "release input directory is missing: $Source"
    }
    foreach ($item in Get-ChildItem -LiteralPath $Source -Recurse -File | Sort-Object FullName) {
        $relative = $item.FullName.Substring($Source.Length).TrimStart('\')
        if ($Exclude -contains $relative) {
            continue
        }
        Add-ReleaseFile -Source $item.FullName -Destination (Join-Path $Destination $relative)
    }
}

New-Item -ItemType Directory -Path $staging | Out-Null
try {
    $targetArtifacts = Join-Path $Workspace 'work\analysis\v687-build-a-20260901\target-artifacts'
    Add-ReleaseFile `
        -Source (Join-Path $targetArtifacts 'openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb') `
        -Destination $imageName
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'openwrt-airoha-an7581-gemtek_w1700k-ubi.manifest') -Destination 'image-rootfs-manifest.txt'
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'profiles.json') -Destination 'target\profiles.json'
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'sha256sums') -Destination 'target\BUILD-TARGET-SHA256SUMS.txt'
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'config.buildinfo') -Destination 'target\config.buildinfo'
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'feeds.buildinfo') -Destination 'target\feeds.buildinfo'
    Add-ReleaseFile -Source (Join-Path $targetArtifacts 'version.buildinfo') -Destination 'target\version.buildinfo'

    Add-ReleaseDirectory -Source $buildEvidence -Destination 'build-evidence'
    Add-ReleaseDirectory `
        -Source (Join-Path $Workspace 'work\analysis\v687-build-a-20260901\verification-20260901T172656Z') `
        -Destination 'verification'
    Add-ReleaseDirectory `
        -Source (Join-Path $Workspace 'work\tests\v687-hostapd-mlo-country-20260901') `
        -Destination 'evidence\static'
    Add-ReleaseDirectory `
        -Source (Join-Path $Workspace 'work\router-tests\v687-live-hotfix2-20260901T171208Z') `
        -Destination 'evidence\live-hotfix'
    Add-ReleaseDirectory `
        -Source (Join-Path $Workspace 'work\router-tests\v687-preflash-20260901T172804Z') `
        -Destination 'evidence\flash-and-installed-validation' `
        -Exclude @('candidate.itb', 'v687-preflash-config.tar.gz')

    Add-ReleaseFile -Source (Join-Path $Workspace 'work\analysis\v687-build-a-20260901\REPORT.md') -Destination 'README.md'
    Add-ReleaseFile -Source (Join-Path $Workspace 'work\analysis\v686-build-a-20260901\REPORT.md') -Destination 'reports\V6.86-SUPERSEDED.md'
    Add-ReleaseFile -Source (Join-Path $Workspace 'work\W1700K_STOCK_PORT_CURRENT_REFERENCE.md') -Destination 'reports\W1700K_STOCK_PORT_CURRENT_REFERENCE.md'
    Add-ReleaseFile -Source (Join-Path $Workspace 'work\W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md') -Destination 'reports\W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md'
    Add-ReleaseFile -Source (Join-Path $Workspace 'work\W1700K_STOCK_PORT_LEDGER.md') -Destination 'reports\W1700K_STOCK_PORT_LEDGER.md'
    Add-ReleaseFile -Source (Join-Path $Workspace 'work\patches\v687-corrective-source.patch') -Destination 'source\v687-corrective-source.patch'

    foreach ($tool in @(
        'generate_v687_corrective_patch.sh',
        'package_w1700k_v687_release.ps1',
        'run_v687_build_a_wsl.sh',
        'sync_v687_build_overlay.sh',
        'verify_w1700k_v687_engineering.sh',
        'w1700k_unattended_synthetic_test.sh',
        'w1700k_v687_live_hotfix_test.sh',
        'w1700k_v687_postflash_baseline.sh'
    )) {
        Add-ReleaseFile -Source (Join-Path $Workspace "tools\$tool") -Destination "tools\$tool"
    }

    $image = Join-Path $staging $imageName
    $imageHash = (Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($imageHash -ne $expectedImageHash) {
        throw "packaged image hash mismatch: $imageHash"
    }

    $textExtensions = @('.md', '.txt', '.log', '.json', '.js', '.sh', '.ps1', '.patch', '.buildinfo')
    $sensitivePatterns = @(
        '(?im)^\s*option\s+(key|password)\s+',
        '(?i)authorization:\s*bearer\s+',
        '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
        '(?i)api[_-]?key\s*[:=]\s*[A-Za-z0-9]',
        '(?i)password\s*[:=]\s*[^\s*]'
    )
    $sensitiveHits = @()
    foreach ($item in Get-ChildItem -LiteralPath $staging -Recurse -File) {
        if ($textExtensions -notcontains $item.Extension) {
            continue
        }
        $content = Get-Content -LiteralPath $item.FullName -Raw -ErrorAction SilentlyContinue
        foreach ($pattern in $sensitivePatterns) {
            if ($content -match $pattern) {
                $sensitiveHits += $item.FullName
                break
            }
        }
    }
    if ($sensitiveHits.Count -gt 0) {
        throw "credential-payload scan matched retained files: $($sensitiveHits -join ', ')"
    }

    $payload = Get-ChildItem -LiteralPath $staging -Recurse -File |
        Where-Object { $_.Name -notin @('SHA256SUMS.txt', 'FILE-MANIFEST.txt') } |
        Sort-Object FullName
    $manifestLines = @()
    $shaLines = @()
    foreach ($item in $payload) {
        $relative = $item.FullName.Substring($staging.Length).TrimStart('\').Replace('\', '/')
        $manifestLines += "{0}`t{1}" -f $relative, $item.Length
        $hash = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $shaLines += '{0}  {1}' -f $hash, $relative
    }

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines((Join-Path $staging 'FILE-MANIFEST.txt'), $manifestLines, $utf8NoBom)
    [System.IO.File]::WriteAllLines((Join-Path $staging 'SHA256SUMS.txt'), $shaLines, $utf8NoBom)

    foreach ($line in $manifestLines) {
        $parts = $line -split "`t", 2
        $path = Join-Path $staging ($parts[0].Replace('/', '\'))
        if ((Get-Item -LiteralPath $path).Length -ne [int64]$parts[1]) {
            throw "manifest size replay failed: $($parts[0])"
        }
    }
    foreach ($line in $shaLines) {
        $parts = $line -split '  ', 2
        $path = Join-Path $staging ($parts[1].Replace('/', '\'))
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $parts[0]) {
            throw "hash replay failed: $($parts[1])"
        }
    }

    Move-Item -LiteralPath $staging -Destination $bundle
    [pscustomobject]@{
        Bundle = $bundle
        Image = Join-Path $bundle $imageName
        ImageSHA256 = $imageHash
        PayloadFiles = $payload.Count
        PayloadBytes = ($payload | Measure-Object -Property Length -Sum).Sum
        ManifestReplayFailures = 0
        HashReplayFailures = 0
        CredentialPayloadMatches = 0
        RouterBackupIncluded = $false
        ChainloaderIncluded = $false
    } | ConvertTo-Json -Depth 4
} catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}
