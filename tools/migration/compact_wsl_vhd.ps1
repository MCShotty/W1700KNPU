param(
    [string]$ReportPath = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU\docs\migration\vhd-compaction-receipt.json',
    [string]$LocalReceiptPath = 'C:\Users\captain\Downloads\FW\W1700KNPU-LocalArchives\vhd-compaction-receipt.json'
)
$ErrorActionPreference = 'Stop'
$target = 'D:\WSL\Ubuntu\ext4.vhdx'
$repo = '\\wsl.localhost\Ubuntu\home\captain\W1700KNPU'
$ReportPath = [IO.Path]::GetFullPath($ReportPath)
$LocalReceiptPath = [IO.Path]::GetFullPath($LocalReceiptPath)
if (-not $ReportPath.StartsWith($repo + '\docs\',[StringComparison]::OrdinalIgnoreCase) -or
    -not $LocalReceiptPath.StartsWith('C:\Users\captain\Downloads\FW\W1700KNPU-LocalArchives\',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Receipt outside approved report locations'
}
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null
$registration = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
    ForEach-Object { Get-ItemProperty $_.PSPath } | Where-Object DistributionName -eq 'Ubuntu')
if ($registration.Count -ne 1) { throw 'Ubuntu registration is ambiguous' }
$registered = [IO.Path]::GetFullPath((Join-Path $registration[0].BasePath 'ext4.vhdx'))
if ($registered.StartsWith('\\?\')) { $registered = $registered.Substring(4) }
if ($registered -ne $target) { throw "Registered VHD differs from approved target: $registered" }
if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class W1700KVhd {
    [StructLayout(LayoutKind.Sequential)]
    public struct StorageType { public uint DeviceId; public Guid VendorId; }
    [StructLayout(LayoutKind.Sequential)]
    public struct OpenV2 { public uint Version, GetInfoOnly, ReadOnly; public Guid ResiliencyGuid; }
    [StructLayout(LayoutKind.Sequential)]
    public struct CompactV1 { public uint Version, Reserved; }
    [DllImport("virtdisk.dll", CharSet=CharSet.Unicode)]
    public static extern uint OpenVirtualDisk(ref StorageType storage, string path,
        uint access, uint flags, ref OpenV2 parameters, out IntPtr handle);
    [DllImport("virtdisk.dll")]
    public static extern uint CompactVirtualDisk(IntPtr handle, uint flags,
        ref CompactV1 parameters, IntPtr overlapped);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
    public static uint Compact(string path) {
        var storage = new StorageType();
        var open = new OpenV2 { Version=2 };
        IntPtr handle;
        uint status = OpenVirtualDisk(ref storage, path, 0, 0, ref open, out handle);
        if (status != 0) return status;
        try {
            var compact = new CompactV1 { Version=1 };
            return CompactVirtualDisk(handle, 0, ref compact, IntPtr.Zero);
        } finally { CloseHandle(handle); }
    }
}
'@
$before = (Get-Item -LiteralPath $target).Length
$result = [ordered]@{ Target=$target; BeforeBytes=$before; Method='Microsoft CompactVirtualDisk V2 open / V1 compact'; SparseEnabled=$false }
try {
    wsl.exe -d Ubuntu -u root --exec /usr/sbin/fstrim -v /
    if ($LASTEXITCODE -ne 0) { throw 'Trim failed; compaction not attempted' }
    wsl.exe -d Ubuntu --exec /bin/sync
    if ($LASTEXITCODE -ne 0) { throw 'Sync failed; compaction not attempted' }
    $distros = @(((wsl.exe --list --quiet | Out-String) -replace "`0",'') -split "`r?`n" |
        ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($distros.Count -ne 1 -or $distros[0] -ne 'Ubuntu') { throw 'Other WSL distributions present; global shutdown refused' }
    wsl.exe --shutdown
    if ($LASTEXITCODE -ne 0) { throw 'WSL did not stop; compaction not attempted' }
    Start-Sleep -Seconds 3
    $result.Win32Status = [W1700KVhd]::Compact($target)
    $result.Message = ([ComponentModel.Win32Exception]::new([int]$result.Win32Status)).Message
} catch {
    $result.Error = $_.Exception.Message
} finally {
    wsl.exe -d Ubuntu --exec /bin/true
    $result.RestartExitCode = $LASTEXITCODE
    $result.AfterBytes = (Get-Item -LiteralPath $target).Length
    $result.ReclaimedBytes = $before - $result.AfterBytes
    $json = $result | ConvertTo-Json -Depth 4
    $json | Set-Content -LiteralPath $LocalReceiptPath -Encoding utf8
    if ($result.RestartExitCode -eq 0) {
        $json | Set-Content -LiteralPath $ReportPath -Encoding utf8
    }
    $json
}
