param([ValidateSet('setup','start','stop','check','credentials')][string]$Action='check',
      [ValidateSet('model','warehouse')][string]$Scenario='model', [switch]$AcceptLicenses)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
function File-Sha256([string]$Path) {
    $stream=[IO.File]::OpenRead($Path)
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose(); $stream.Dispose() }
}
try {
    Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
    Import-Module Microsoft.PowerShell.Management -ErrorAction Stop
    Import-Module Microsoft.PowerShell.Archive -ErrorAction Stop
    if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Build -lt 10240) {
        throw 'Windows 10/11 x64 is required.'
    }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'Windows ARM is not supported.' }
    if ($root.Length -gt 100) { throw 'Extract to a shorter writable path (under 100 characters). Chinese characters and spaces are supported.' }
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $root 'MANIFEST.sha256'))) {
        $parts=$line -split '  ',2
        $actual=File-Sha256 (Join-Path $root $parts[1])
        if ($actual -ne $parts[0]) { throw "Package integrity failed: $($parts[1]). Extract a fresh ZIP." }
    }
    $python=Join-Path $root 'runtime/python/python.exe'
    if ($Action -eq 'setup') {
        if (-not $AcceptLicenses) {
            Write-Host 'Read README-FIRST.txt and licenses/DEPENDENCIES.txt before continuing.'
            Write-Host 'Setup downloads official portable Java, CPython, MySQL and locked dependencies into this folder.'
            Write-Host 'No Windows service, PATH, firewall, or global execution policy is changed.'
            if ((Read-Host 'Type ACCEPT to continue') -cne 'ACCEPT') { throw 'Setup cancelled; no vendor download or database initialization performed.' }
        }
        $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
        if ($drive.AvailableFreeSpace -lt 3GB) { throw 'At least 3 GiB free space is required.' }
        $lock=Get-Content -LiteralPath (Join-Path $root 'config/components.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $component=$lock.components | Where-Object kind -eq 'python'
        $cache=Join-Path $root 'runtime/downloads'
        [IO.Directory]::CreateDirectory($cache) | Out-Null
        $archive=Join-Path $cache $component.filename
        if (-not (Test-Path -LiteralPath $archive)) {
            [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
            $temp=$archive+'.partial'
            Invoke-WebRequest -UseBasicParsing -Uri $component.url -OutFile $temp
            if ((File-Sha256 $temp) -ne $component.sha256) { throw 'Python download checksum mismatch; do not bypass verification.' }
            Move-Item -LiteralPath $temp -Destination $archive
        }
        if ((File-Sha256 $archive) -ne $component.sha256) { throw 'Cached Python checksum mismatch. Retain it for diagnosis and extract a fresh ZIP.' }
        if (-not (Test-Path -LiteralPath $python)) {
            $destination=Join-Path $root 'runtime/python'
            Expand-Archive -LiteralPath $archive -DestinationPath $destination
            [IO.File]::WriteAllText((Join-Path $destination ('.'+$component.filename+'.verified')), $component.sha256)
            [IO.File]::WriteAllText((Join-Path $destination 'python311._pth'), "python311.zip`n.`nLib/site-packages`nimport site`n",[Text.Encoding]::ASCII)
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        if ($Action -eq 'check') {
            $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
            if ($drive.AvailableFreeSpace -lt 3GB) { throw 'At least 3 GiB free space is required.' }
            Write-Host 'Platform/path/package integrity/disk checks passed. Run FIRST-SETUP.bat to acquire portable runtimes.'
            exit 0
        }
        throw 'Run FIRST-SETUP.bat first. No global Python is used.'
    }
    & $python -I (Join-Path $root 'launcher/portable.py') $Action --scenario $Scenario
    exit $LASTEXITCODE
} catch {
    Write-Host ('ERROR: '+$_.Exception.Message)
    exit 1
}
