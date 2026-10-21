param([string]$Destination='', [switch]$AcceptLicenses, [switch]$NoBrowser)
$ErrorActionPreference='Stop'
$source=Split-Path -Parent $PSScriptRoot
function Hash([string]$path) {
    $stream=[IO.File]::OpenRead($path); $algorithm=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose();$stream.Dispose() }
}
try {
    if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Build -lt 10240 -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'Windows 10/11 x64 is required; ARM is not supported.' }
    if (-not (Test-Path -LiteralPath (Join-Path $source 'config/offline.json'))) { throw 'This entrypoint requires the full OFFLINE USB package.' }
    $manifest=[IO.File]::ReadAllLines((Join-Path $source 'MANIFEST.sha256'))
    Write-Host 'Checking complete USB package...'
    foreach ($line in $manifest) {
        $pair=$line -split '  ',2
        if ((Hash (Join-Path $source $pair[1])) -ne $pair[0]) { throw ('USB integrity failed: '+$pair[1]) }
    }
    $identity=(Hash (Join-Path $source 'MANIFEST.sha256')).Substring(0,12)
    if (-not $Destination) {
        $preferred=[IO.Path]::GetPathRoot($env:SystemRoot)
        if ([IO.Directory]::Exists('D:\') -and [IO.DriveInfo]::new('D:\').DriveType -eq 'Fixed') { $preferred='D:\' }
        $default=Join-Path $preferred ('UrbanCommute-USB-'+$identity)
        Write-Host ('Deploy to a writable local NTFS folder, preferably on a tested data drive. Default: '+$default)
        $answer=Read-Host 'Local destination (Enter for default; do not select the USB drive)'
        $Destination=if ($answer) { $answer.Trim('"') } else { $default }
    }
    if (-not [IO.Path]::IsPathRooted($Destination)) { throw 'Use an absolute local destination path.' }
    $Destination=[IO.Path]::GetFullPath($Destination).TrimEnd('\')
    $sourceFull=[IO.Path]::GetFullPath($source).TrimEnd('\')
    if ($Destination.Length -gt 100 -or $Destination.Length -lt 5) { throw 'Choose a separate local folder with a path under 100 characters.' }
    if ($Destination.Equals($sourceFull,[StringComparison]::OrdinalIgnoreCase) -or $Destination.StartsWith($sourceFull+'\',[StringComparison]::OrdinalIgnoreCase) -or $sourceFull.StartsWith($Destination+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Source and destination must be separate folders, not ancestors.' }
    $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($Destination))
    if ($drive.DriveType -ne 'Fixed' -or $drive.DriveFormat -ne 'NTFS') { throw 'Deploy to a local fixed NTFS drive. Do not initialize MySQL on the USB or a network share.' }
    if ($drive.AvailableFreeSpace -lt 5GB) { throw 'At least 5 GiB free space is required for the full offline copy, runtime extraction and new databases.' }
    $receipt=Join-Path $Destination 'USB-DEPLOYMENT.json'
    if ([IO.Directory]::Exists($Destination)) {
        if (-not [IO.File]::Exists($receipt)) { throw 'Destination already exists without this package deployment receipt. Choose a new empty destination; existing files retained.' }
        $prior=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
        if ($prior.manifest -ne $identity) { throw 'Destination belongs to a different package. Use another folder; no upgrade or overwrite performed.' }
    } else {
        [IO.Directory]::CreateDirectory($Destination) | Out-Null
        [IO.File]::WriteAllText($receipt,('{"manifest":"'+$identity+'","purpose":"owned offline deployment"}'))
    }
    Write-Host 'Copying verified files to local disk; existing initialized state is never copied from USB.'
    foreach ($line in $manifest) {
        $pair=$line -split '  ',2; $target=Join-Path $Destination $pair[1]
        if ($target.Length -gt 245) { throw 'Choose a shorter local destination; preserved license paths must fit Windows PowerShell file APIs.' }
        if ([IO.File]::Exists($target)) {
            if ((Hash $target) -ne $pair[0]) { throw ('Existing deployment file differs: '+$pair[1]+'. Data retained; use a new destination.') }
        } else {
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
            [IO.File]::Copy((Join-Path $source $pair[1]),$target,$false)
        }
    }
    $targetManifest=Join-Path $Destination 'MANIFEST.sha256'
    if (-not [IO.File]::Exists($targetManifest)) { [IO.File]::Copy((Join-Path $source 'MANIFEST.sha256'),$targetManifest,$false) }
    if ((Hash $targetManifest) -ne (Hash (Join-Path $source 'MANIFEST.sha256'))) { throw 'Destination manifest differs; use a new folder.' }
    $bootstrap=Join-Path $Destination 'launcher/bootstrap.ps1'
    $powershell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    & $powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $bootstrap -Action check
    if ($LASTEXITCODE -ne 0) { throw 'Local environment check failed. See the message above; no global setting changed.' }
    $setupArgs=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$bootstrap,'-Action','setup')
    if ($AcceptLicenses) { $setupArgs+='-AcceptLicenses' }
    & $powershell @setupArgs
    if ($LASTEXITCODE -ne 0) { throw 'Offline setup failed. Keep this installation for diagnosis; no unknown process stopped.' }
    & $powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $bootstrap -Action start
    if ($LASTEXITCODE -ne 0) { throw 'Start refused or failed. Inspect the local state logs; do not remove existing data.' }
    $running=Get-Content -LiteralPath (Join-Path $Destination 'state/running.json') -Raw | ConvertFrom-Json
    Write-Host ('Local installation: '+$Destination)
    Write-Host ('Open '+$running.url+' ; privately run CREDENTIALS.bat in the local installation to view this computer''s random passwords.')
    Write-Host 'STOP.bat in that local installation stops the system. Do not share initialized state or this computer''s MySQL data.'
    if (-not $NoBrowser) { Start-Process $running.url }
    exit 0
} catch { Write-Host ('ERROR: '+$_.Exception.Message); exit 1 }
