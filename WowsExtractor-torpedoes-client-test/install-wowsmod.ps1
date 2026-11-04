[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$Build,

    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [switch]$DryRun,

    # Explicit opt-in for an ATM-present test. The default stays "disable ATM"
    # so a normal install cannot silently leave an unverified third-party
    # producer in the load path. KeepAtm is accepted as an alias for scripts.
    [Alias('KeepAtm')]
    [switch]$WithAtm,

    [switch]$Elevated
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:PythonFiles = @(
    'Main.py',
    'battle_identity.py',
    'damage_tracker.py',
    'emit_guard.py',
    'ui_health.py',
    'torpedo_telemetry.py',
    'submarine_telemetry.py',
    'map_calibration.py',
    'performance_profiler.py'
)
$script:CopyFiles = @($script:PythonFiles + 'config.example.ini')
$script:Manifest = @{}

# ATM means AndrewTaro/AdvancedTorpedoMarker. These are the only files that
# make ATM load. A fixed allow-list is used so that no other Torpedo mod is
# moved by a wildcard match. The shared TTaroModUtils files are deliberately
# not in this list because other TTaro mods use them.
$script:AtmDefinitions = @(
    [pscustomobject]@{
        RelativePath = 'PnFMods\AdvancedTorpedoMarkerPy'
        Kind = 'Directory'
        Label = 'ATM body (PnFMods)'
    },
    [pscustomobject]@{
        RelativePath = 'gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound'
        Kind = 'File'
        Label = 'ATM battle UI (Unbound)'
    },
    [pscustomobject]@{
        RelativePath = 'gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound'
        Kind = 'File'
        Label = 'ATM minimap UI (Unbound)'
    }
)
$script:AtmBackupPath = $null
$script:AtmManifestPath = $null

function Write-Info {
    param([string]$Message)
    Write-Host "[..] $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message"
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Exit-Installer {
    param([int]$Code)
    if ($Elevated -and -not $DryRun) {
        try {
            Write-Host ""
            [void](Read-Host "Press Enter to close this window")
        } catch {
        }
    }
    exit $Code
}

function Test-IsAdmin {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object -TypeName Security.Principal.WindowsPrincipal -ArgumentList $identity
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Test-UnderProgramFiles {
    param([string]$Path)
    $bases = @()
    $bases += [Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFiles)
    $bases += [Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFilesX86)
    foreach ($base in $bases) {
        if ([string]::IsNullOrWhiteSpace($base)) {
            continue
        }
        $prefix = $base.TrimEnd('\') + '\'
        if ($Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function ConvertTo-SingleQuoted {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Invoke-ElevatedSelf {
    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $psExe -PathType Leaf)) {
        $psExe = 'powershell.exe'
    }

    $command = '& ' + (ConvertTo-SingleQuoted $PSCommandPath) +
        ' -Build ' + (ConvertTo-SingleQuoted $Build) +
        ' -GameRoot ' + (ConvertTo-SingleQuoted $GameRoot)
    if ($WithAtm) {
        $command += ' -WithAtm'
    }
    $command += ' -Elevated'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $process = Start-Process -FilePath $psExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) `
        -Verb RunAs -Wait -PassThru -ErrorAction Stop
    return $process.ExitCode
}

function Get-UniquePath {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $Path
    }
    $parent = Split-Path -Parent $Path
    $leaf = Split-Path -Leaf $Path
    for ($index = 2; $index -lt 1000; $index++) {
        $candidate = Join-Path $parent ("{0}-{1}" -f $leaf, $index)
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    throw "Could not choose a unique backup path near: $Path"
}

function Get-AtmItems {
    param([string]$ResModsPath)
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($definition in $script:AtmDefinitions) {
        $source = Join-Path $ResModsPath $definition.RelativePath
        $item = Get-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) {
            continue
        }
        if ($definition.Kind -eq 'Directory') {
            if (-not $item.PSIsContainer) {
                throw "ATM path exists but is not a folder: $source"
            }
        } else {
            if ($item.PSIsContainer) {
                throw "ATM path exists but is not a file: $source"
            }
        }
        $items.Add([pscustomobject]@{
            RelativePath = [string]$definition.RelativePath
            Source = [string]$source
            Kind = [string]$definition.Kind
            Label = [string]$definition.Label
        })
    }
    return $items.ToArray()
}

function Write-AtmManifest {
    param(
        [string]$Path,
        [object[]]$Items,
        [string]$ResModsPath,
        [string]$BuildNumber,
        [string]$GameRootPath,
        [string]$Status
    )
    $entries = @()
    foreach ($item in $Items) {
        $entries += [pscustomobject]@{
            relativePath = $item.RelativePath
            kind = $item.Kind
            label = $item.Label
        }
    }
    $manifest = [pscustomobject]@{
        schema = 1
        tool = 'WowsExtractor installer ATM disable'
        status = $Status
        build = $BuildNumber
        gameRoot = $GameRootPath
        resMods = $ResModsPath
        createdAt = (Get-Date).ToString('o')
        items = @($entries)
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Disable-Atm {
    param(
        [object[]]$Items,
        [string]$BackupRoot,
        [string]$ResModsPath,
        [string]$BuildNumber,
        [string]$GameRootPath,
        [string]$Timestamp
    )
    if ($Items.Count -eq 0) {
        return $null
    }

    $backupPath = Get-UniquePath (Join-Path $BackupRoot ("ATM_disabled_{0}" -f $Timestamp))
    [void][IO.Directory]::CreateDirectory($backupPath)
    $manifestPath = Join-Path $backupPath 'atm-disable-manifest.json'
    $script:AtmBackupPath = $backupPath
    $script:AtmManifestPath = $manifestPath
    Write-AtmManifest -Path $manifestPath -Items $Items -ResModsPath $ResModsPath `
        -BuildNumber $BuildNumber -GameRootPath $GameRootPath -Status 'disabling'

    $moved = New-Object System.Collections.Generic.List[object]
    foreach ($item in $Items) {
        $destination = Join-Path $backupPath $item.RelativePath
        $destinationParent = Split-Path -Parent $destination
        [void][IO.Directory]::CreateDirectory($destinationParent)
        if (Test-Path -LiteralPath $destination) {
            throw "ATM backup path already exists: $destination"
        }
        Move-Item -LiteralPath $item.Source -Destination $destination -ErrorAction Stop
        $moved.Add($item)
        Write-Ok ("ATM moved out of load path: {0}" -f $item.RelativePath)
    }

    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    $manifest | Add-Member -NotePropertyName status -NotePropertyValue 'disabled' -Force
    $manifest | Add-Member -NotePropertyName disabledAt -NotePropertyValue ((Get-Date).ToString('o')) -Force
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    return [pscustomobject]@{
        BackupPath = $backupPath
        ManifestPath = $manifestPath
        Moved = $moved.ToArray()
    }
}

function Restore-AtmFromManifest {
    param(
        [string]$ManifestPath,
        [string]$ResModsPath
    )
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "ATM manifest was not found: $ManifestPath"
    }
    $manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
    $itemsProperty = $manifest.PSObject.Properties['items']
    if ($null -eq $itemsProperty) {
        throw "ATM manifest has no items: $ManifestPath"
    }
    $entries = @($itemsProperty.Value)
    if ($entries.Count -eq 0) {
        throw "ATM manifest has no items: $ManifestPath"
    }

    $backupPath = Split-Path -Parent $ManifestPath
    $allowedPaths = @($script:AtmDefinitions | ForEach-Object { $_.RelativePath })
    $planned = @()
    $seenPaths = @{}
    foreach ($entry in $entries) {
        $relativeProperty = $entry.PSObject.Properties['relativePath']
        if ($null -eq $relativeProperty) {
            throw "ATM manifest item has no relativePath: $ManifestPath"
        }
        $relative = ([string]$relativeProperty.Value).Replace('/', '\').TrimEnd('\')
        if ([string]::IsNullOrWhiteSpace($relative)) {
            throw "ATM manifest item has an empty relativePath: $ManifestPath"
        }
        if ([IO.Path]::IsPathRooted($relative)) {
            throw "ATM manifest item is rooted: $relative"
        }
        if (($relative -split '\\') -contains '..') {
            throw "ATM manifest item contains '..': $relative"
        }
        if (-not ($allowedPaths -contains $relative)) {
            throw "ATM manifest item is not a known ATM path: $relative"
        }
        $pathKey = $relative.ToLowerInvariant()
        if ($seenPaths.ContainsKey($pathKey)) {
            throw "ATM manifest contains a duplicate ATM path: $relative"
        }
        $seenPaths[$pathKey] = $true
        $source = Join-Path $ResModsPath $relative
        $backup = Join-Path $backupPath $relative
        $backupExists = Test-Path -LiteralPath $backup
        $sourceExists = Test-Path -LiteralPath $source
        if ($backupExists -and $sourceExists) {
            throw "Refusing to overwrite an existing ATM path: $source"
        }
        if (-not $backupExists -and -not $sourceExists) {
            throw "ATM backup item is missing: $backup"
        }
        $planned += [pscustomobject]@{
            RelativePath = $relative
            Source = $source
            Backup = $backup
            Restore = $backupExists
        }
    }

    $messages = New-Object System.Collections.Generic.List[string]
    foreach ($item in $planned) {
        if (-not $item.Restore) {
            $messages.Add("ATM item already present, not moved: $($item.RelativePath)")
            continue
        }
        $parent = Split-Path -Parent $item.Source
        [void][IO.Directory]::CreateDirectory($parent)
        Move-Item -LiteralPath $item.Backup -Destination $item.Source -ErrorAction Stop
        $messages.Add("Restored ATM item: $($item.RelativePath)")
    }

    $manifest | Add-Member -NotePropertyName restoredAt -NotePropertyValue ((Get-Date).ToString('o')) -Force
    $manifest | Add-Member -NotePropertyName status -NotePropertyValue 'restored' -Force
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
    return $messages.ToArray()
}

function Initialize-Manifest {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "SHA256SUMS.txt was not found: $Path"
    }
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding ASCII) {
        if ($line -match '^([0-9A-Fa-f]{64})[ \t]+\*?(.+?)[ \t]*$') {
            $relative = $matches[2].Replace('/', '\')
            $map[$relative] = $matches[1].ToLowerInvariant()
        }
    }
    if ($map.Count -eq 0) {
        throw "SHA256SUMS.txt has no usable entries: $Path"
    }
    $script:Manifest = $map
}

function Get-ExpectedHash {
    param([string]$RelativePath)
    $key = $RelativePath.Replace('/', '\')
    if (-not $script:Manifest.ContainsKey($key)) {
        throw "No SHA-256 entry in SHA256SUMS.txt for: $RelativePath"
    }
    return $script:Manifest[$key]
}

function Assert-SourceFile {
    param(
        [string]$FullPath,
        [string]$RelativePath,
        [switch]$AllowEmpty
    )
    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        throw "Missing source file: $FullPath"
    }
    $item = Get-Item -LiteralPath $FullPath -Force
    if (-not $AllowEmpty -and $item.Length -le 0) {
        throw "Source file is empty: $FullPath"
    }
    $expected = Get-ExpectedHash $RelativePath
    $actual = (Get-FileHash -LiteralPath $FullPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "SHA-256 mismatch for $RelativePath. Re-extract the distribution package."
    }
}

function Assert-SourceIntegrity {
    param([string]$SourceResMods)
    $sourceMod = Join-Path $SourceResMods 'PnFMods\WowsExtractor'
    if (-not (Test-Path -LiteralPath $sourceMod -PathType Container)) {
        throw "Source mod folder was not found: $sourceMod"
    }
    foreach ($name in $script:PythonFiles) {
        Assert-SourceFile -FullPath (Join-Path $sourceMod $name) `
            -RelativePath ('res_mods/PnFMods/WowsExtractor/' + $name)
    }
    Assert-SourceFile -FullPath (Join-Path $sourceMod 'config.example.ini') `
        -RelativePath 'res_mods/PnFMods/WowsExtractor/config.example.ini'
    Assert-SourceFile -FullPath (Join-Path $SourceResMods 'PnFModsLoader.py') `
        -RelativePath 'res_mods/PnFModsLoader.py' -AllowEmpty
    Write-Ok "Source integrity verified: $($script:PythonFiles.Count) Python files, config.example.ini, PnFModsLoader.py"
}

function Assert-TargetBuild {
    param([string]$GameRootPath, [string]$BuildNumber)
    if (-not (Test-Path -LiteralPath $GameRootPath -PathType Container)) {
        throw "Game root was not found: $GameRootPath"
    }
    $targetPath = Join-Path (Join-Path $GameRootPath 'bin') $BuildNumber
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        throw "Target build folder was not found: $targetPath"
    }
    return $targetPath
}

function Get-RunningGameProcesses {
    $names = @('WorldOfWarships', 'WorldOfWarships64', 'WoWSLauncher')
    $result = @()
    foreach ($name in $names) {
        $processes = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
        foreach ($process in $processes) {
            $result += $process
        }
    }
    return $result
}

function Stop-IfGameRunning {
    $processes = @(Get-RunningGameProcesses)
    if ($processes.Count -gt 0) {
        $description = ($processes | ForEach-Object {
            $_.ProcessName + ' (PID ' + $_.Id + ')'
        }) -join ', '
        Write-Err "The game or launcher is running: $description"
        Write-Err "Close it completely, then run this installer again."
        Exit-Installer 3
    }
}

function Copy-And-Verify {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )
    Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop
    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant()
    $destinationHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -ne $destinationHash) {
        throw "Copy verification failed for: $Label"
    }
    Write-Ok "Copied: $Label"
}

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
    Write-Err "Could not determine the script folder."
    exit 6
}

$gameRootFull = [IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
$target = Join-Path (Join-Path $gameRootFull 'bin') $Build
$resMods = Join-Path $target 'res_mods'
$pnfMods = Join-Path $resMods 'PnFMods'
$targetMod = Join-Path $pnfMods 'WowsExtractor'
$targetLoader = Join-Path $resMods 'PnFModsLoader.py'
$sourceResMods = Join-Path $scriptDir 'res_mods'
$sourceMod = Join-Path $sourceResMods 'PnFMods\WowsExtractor'
$sourceLoader = Join-Path $sourceResMods 'PnFModsLoader.py'
$manifestPath = Join-Path $scriptDir 'SHA256SUMS.txt'
$backupRoot = Join-Path $resMods '_wowsmod_backups'

try {
    Initialize-Manifest $manifestPath
    Assert-SourceIntegrity $sourceResMods
    $target = Assert-TargetBuild $gameRootFull $Build
    $modItem = Get-Item -LiteralPath $targetMod -Force -ErrorAction SilentlyContinue
    if ($null -ne $modItem -and -not $modItem.PSIsContainer) {
        throw "This path exists but is not a folder: $targetMod"
    }
    $loaderItem = Get-Item -LiteralPath $targetLoader -Force -ErrorAction SilentlyContinue
    if ($null -ne $loaderItem -and $loaderItem.PSIsContainer) {
        throw "This path exists but is not a file: $targetLoader"
    }
    $atmItems = @(Get-AtmItems -ResModsPath $resMods)
} catch {
    Write-Err $_.Exception.Message
    Write-Err "Preflight failed. No files were changed."
    Exit-Installer 2
}

Stop-IfGameRunning

$modExists = $null -ne $modItem
$loaderExists = $null -ne $loaderItem
$oldConfig = Join-Path $targetMod 'config.ini'
$configExists = $modExists -and (Test-Path -LiteralPath $oldConfig -PathType Leaf)
$needsAdmin = Test-UnderProgramFiles $target
$isAdmin = Test-IsAdmin
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$plannedBackup = Join-Path $backupRoot ("WowsExtractor_{0}" -f $timestamp)

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN - read-only preflight. No files will be written."
    Write-Host "  Target build   : $target"
    Write-Host "  Mod folder     : $targetMod"
    if ($modExists) {
        Write-Host "  Existing mod   : yes - it would be moved to:"
        Write-Host "                   $(Get-UniquePath $plannedBackup)"
    } else {
        Write-Host "  Existing mod   : no"
    }
    if ($configExists) {
        Write-Host "  config.ini     : yes - it would be carried into the new folder"
    } else {
        Write-Host "  config.ini     : no - defaults would be used"
    }
    if ($loaderExists) {
        Write-Host "  PnFModsLoader  : yes - it would be left untouched"
    } else {
        Write-Host "  PnFModsLoader  : no - the bundled file would be copied (0 bytes is normal)"
    }
    if ($WithAtm) {
        Write-Host "  ATM mode       : keep (explicit -WithAtm)"
        if ($atmItems.Count -gt 0) {
            Write-Host "  ATM disable    : no - these ATM-only load files would stay in place:"
            foreach ($atmItem in $atmItems) {
                Write-Host ("                   {0}" -f $atmItem.RelativePath)
            }
            Write-Host "  ATM restore    : not needed for this install"
        } else {
            Write-Host "  ATM disable    : no ATM load files detected - nothing would be moved or kept"
        }
        Write-Host "  ATM shared     : PnFModsLoader.py and TTaroModUtils would be left untouched"
    } elseif ($atmItems.Count -gt 0) {
        $plannedAtmBackup = Get-UniquePath (Join-Path $backupRoot ("ATM_disabled_{0}" -f $timestamp))
        Write-Host "  ATM mode       : disable (default)"
        Write-Host "  ATM disable    : yes - these ATM-only load files would be moved:"
        foreach ($atmItem in $atmItems) {
            Write-Host ("                   {0}" -f $atmItem.RelativePath)
            Write-Host ("                     -> {0}" -f (Join-Path $plannedAtmBackup $atmItem.RelativePath))
        }
        Write-Host "  ATM keep       : PnFModsLoader.py, TTaroModUtils, ATM schema and images"
        Write-Host "  ATM restore    : restore-atm-13357625.bat (after the no-ATM test)"
    } else {
        Write-Host "  ATM mode       : disable (default)"
        Write-Host "  ATM disable    : no ATM load files detected - nothing to move"
    }
    if (Test-Path -LiteralPath $resMods -PathType Container) {
        Write-Host "  res_mods       : exists"
    } else {
        Write-Host "  res_mods       : would be created"
    }
    if ($isAdmin) {
        Write-Host "  Administrator  : yes"
    } elseif ($needsAdmin) {
        Write-Host "  Administrator  : no - the real install would request elevation (UAC)"
    } else {
        Write-Host "  Administrator  : no - elevation is normally not required for this path"
    }
    Write-Host ""
    Write-Ok "DRY RUN OK - preflight checks passed. No changes were made."
    Exit-Installer 0
}

if ($needsAdmin -and -not $isAdmin) {
    if ($Elevated) {
        Write-Err "Administrator rights are still not available."
        Write-Err "Right-click install-13357625.bat and choose 'Run as administrator'."
        Exit-Installer 4
    }
    Write-Info "Administrator rights are required for the target folder."
    Write-Info "Requesting elevation (UAC prompt)..."
    try {
        $childExitCode = Invoke-ElevatedSelf
    } catch {
        Write-Err "Elevation was cancelled or failed: $($_.Exception.Message)"
        Write-Err "Right-click install-13357625.bat and choose 'Run as administrator'."
        Exit-Installer 4
    }
    Exit-Installer $childExitCode
}

$movedOld = $false
$createdMod = $false
$createdLoader = $false
$backupPath = $null
$failedPath = $null
$loaderBeforeHash = $null
$configBeforeHash = $null
$atmBackupPath = $null
$atmManifestPath = $null
$atmDetected = $false
$atmKept = $false

try {
    Stop-IfGameRunning
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Target build folder disappeared: $target"
    }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:AtmBackupPath = $null
    $script:AtmManifestPath = $null

    $modItemNow = Get-Item -LiteralPath $targetMod -Force -ErrorAction SilentlyContinue
    if ($null -ne $modItemNow -and -not $modItemNow.PSIsContainer) {
        throw "This path exists but is not a folder: $targetMod"
    }
    $modExistsNow = $null -ne $modItemNow
    $oldConfigNow = Join-Path $targetMod 'config.ini'
    $carryConfig = $modExistsNow -and (Test-Path -LiteralPath $oldConfigNow -PathType Leaf)

    $loaderItemNow = Get-Item -LiteralPath $targetLoader -Force -ErrorAction SilentlyContinue
    if ($null -ne $loaderItemNow -and $loaderItemNow.PSIsContainer) {
        throw "This path exists but is not a file: $targetLoader"
    }
    $loaderExistsNow = $null -ne $loaderItemNow
    if ($loaderExistsNow) {
        $loaderBeforeHash = (Get-FileHash -LiteralPath $targetLoader -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($carryConfig) {
        $configBeforeHash = (Get-FileHash -LiteralPath $oldConfigNow -Algorithm SHA256).Hash.ToLowerInvariant()
    }

    $atmItemsNow = @(Get-AtmItems -ResModsPath $resMods)
    $atmDetected = $atmItemsNow.Count -gt 0
    if ($WithAtm) {
        if ($atmDetected) {
            $atmKept = $true
            Write-Info "-WithAtm: ATM load files were left in place. They were not moved or modified."
        } else {
            Write-Info "-WithAtm was given, but no ATM load files were detected. Nothing was kept or moved."
        }
    } elseif ($atmDetected) {
        $atmResult = Disable-Atm -Items $atmItemsNow -BackupRoot $backupRoot `
            -ResModsPath $resMods -BuildNumber $Build -GameRootPath $gameRootFull `
            -Timestamp $timestamp
        $atmBackupPath = $atmResult.BackupPath
        $atmManifestPath = $atmResult.ManifestPath
        Write-Info "ATM files were moved out of the load paths. They were not deleted."
    }

    if ($modExistsNow) {
        $backupPath = Get-UniquePath (Join-Path $backupRoot ("WowsExtractor_{0}" -f $timestamp))
        [void][IO.Directory]::CreateDirectory($backupRoot)
        Move-Item -LiteralPath $targetMod -Destination $backupPath -ErrorAction Stop
        $movedOld = $true
        Write-Ok "Existing WowsExtractor moved outside PnFMods: $backupPath"
    }

    if (Test-Path -LiteralPath $targetMod) {
        throw "The mod folder appeared during installation. Aborting before overwriting it: $targetMod"
    }
    [void][IO.Directory]::CreateDirectory($targetMod)
    $createdMod = $true

    foreach ($name in $script:CopyFiles) {
        Copy-And-Verify -Source (Join-Path $sourceMod $name) `
            -Destination (Join-Path $targetMod $name) `
            -Label ('WowsExtractor\' + $name)
    }

    if ($carryConfig) {
        $configSource = Join-Path $backupPath 'config.ini'
        if (-not (Test-Path -LiteralPath $configSource -PathType Leaf)) {
            throw "The previous config.ini could not be found in the backup: $configSource"
        }
        Copy-And-Verify -Source $configSource `
            -Destination (Join-Path $targetMod 'config.ini') `
            -Label 'WowsExtractor\config.ini (carried over)'
    }

    if (-not (Test-Path -LiteralPath $targetLoader)) {
        Copy-And-Verify -Source $sourceLoader `
            -Destination $targetLoader `
            -Label 'PnFModsLoader.py (bundled copy)'
        $createdLoader = $true
    } else {
        if (-not $loaderExistsNow) {
            Write-Warn "PnFModsLoader.py appeared during installation; leaving it untouched."
            $loaderBeforeHash = (Get-FileHash -LiteralPath $targetLoader -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        $loaderAfterHash = (Get-FileHash -LiteralPath $targetLoader -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($loaderAfterHash -ne $loaderBeforeHash) {
            throw "Existing PnFModsLoader.py changed unexpectedly. It was not supposed to be overwritten."
        }
        Write-Ok "Existing PnFModsLoader.py left untouched."
    }

    foreach ($name in $script:CopyFiles) {
        $relative = 'res_mods/PnFMods/WowsExtractor/' + $name
        $expected = Get-ExpectedHash $relative
        $actual = (Get-FileHash -LiteralPath (Join-Path $targetMod $name) -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) {
            throw "Installed file verification failed: $relative"
        }
    }

    if ($carryConfig) {
        $configAfterHash = (Get-FileHash -LiteralPath (Join-Path $targetMod 'config.ini') -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($configAfterHash -ne $configBeforeHash) {
            throw "The carried-over config.ini did not match the previous file."
        }
    }

    if ($createdLoader) {
        $expectedLoader = Get-ExpectedHash 'res_mods/PnFModsLoader.py'
        $actualLoader = (Get-FileHash -LiteralPath $targetLoader -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualLoader -ne $expectedLoader) {
            throw "Installed PnFModsLoader.py verification failed."
        }
    } else {
        $actualLoader = (Get-FileHash -LiteralPath $targetLoader -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualLoader -ne $loaderBeforeHash) {
            throw "Existing PnFModsLoader.py verification failed."
        }
    }

    Write-Host ""
    Write-Ok "Installation completed successfully."
    Write-Host "  Mod folder    : $targetMod"
    if ($movedOld) {
        Write-Host "  Backup        : $backupPath"
    } else {
        Write-Host "  Backup        : none (no previous WowsExtractor folder)"
    }
    if ($carryConfig) {
        Write-Host "  config.ini    : carried over from the previous install"
    } else {
        Write-Host "  config.ini    : not present (defaults will be used)"
    }
    if ($createdLoader) {
        Write-Host "  PnFModsLoader : bundled copy installed (0 bytes is normal)"
    } else {
        Write-Host "  PnFModsLoader : existing file left untouched"
    }
    if ($atmBackupPath) {
        Write-Host "  ATM           : disabled - ATM-only load files were moved out"
        Write-Host "  ATM backup    : $atmBackupPath"
        Write-Host "  ATM restore   : restore-atm-13357625.bat (run after the no-ATM test)"
        Write-Host "  ATM shared    : PnFModsLoader.py and TTaroModUtils were left untouched"
    } elseif ($atmKept) {
        Write-Host "  ATM           : kept - explicit -WithAtm (ATM load files were not moved)"
        Write-Host "  ATM restore   : not needed for this install"
        Write-Host "  ATM shared    : PnFModsLoader.py and TTaroModUtils were left untouched"
        Write-Host "  ATM note      : ATM presence is not proof of a state producer; values stay derived/unverified"
    } elseif ($WithAtm) {
        Write-Host "  ATM           : no ATM load files detected (-WithAtm had nothing to keep)"
        Write-Host "  ATM shared    : PnFModsLoader.py and TTaroModUtils were left untouched"
    } else {
        Write-Host "  ATM           : no ATM load files detected (nothing moved)"
        Write-Host "  ATM shared    : PnFModsLoader.py and TTaroModUtils were left untouched"
    }
    Write-Host "  Next          : start the game and check state.json / meta.json in the mod folder."
    Write-Host ""
    Exit-Installer 0
} catch {
    Write-Err $_.Exception.Message
    Write-Err "Installation failed. Attempting rollback; no success is reported."

    $rollbackMessages = New-Object System.Collections.Generic.List[string]

    if ($null -ne $script:AtmManifestPath -and (Test-Path -LiteralPath $script:AtmManifestPath -PathType Leaf)) {
        try {
            $atmRestoreMessages = @(Restore-AtmFromManifest -ManifestPath $script:AtmManifestPath -ResModsPath $resMods)
            foreach ($message in $atmRestoreMessages) {
                $rollbackMessages.Add($message)
            }
        } catch {
            $rollbackMessages.Add("Could not restore ATM automatically: $($_.Exception.Message)")
            $rollbackMessages.Add("ATM backup is safe at: $script:AtmBackupPath")
        }
    }

    if ($createdMod -and (Test-Path -LiteralPath $targetMod)) {
        try {
            $failedPath = Get-UniquePath (Join-Path $backupRoot ("WowsExtractor_failed_{0}" -f $timestamp))
            [void][IO.Directory]::CreateDirectory($backupRoot)
            Move-Item -LiteralPath $targetMod -Destination $failedPath -ErrorAction Stop
            $rollbackMessages.Add("Moved partial new mod to: $failedPath")
        } catch {
            $rollbackMessages.Add("Could not move the partial new mod: $($_.Exception.Message)")
        }
    }

    if ($createdLoader -and (Test-Path -LiteralPath $targetLoader -PathType Leaf)) {
        try {
            [void][IO.Directory]::CreateDirectory($backupRoot)
            $failedLoader = Join-Path $backupRoot ("PnFModsLoader_failed_{0}.py" -f $timestamp)
            $failedLoader = Get-UniquePath $failedLoader
            Move-Item -LiteralPath $targetLoader -Destination $failedLoader -ErrorAction Stop
            $rollbackMessages.Add("Moved newly created loader to: $failedLoader")
        } catch {
            $rollbackMessages.Add("Could not move the newly created loader: $($_.Exception.Message)")
        }
    }

    if ($movedOld) {
        if (Test-Path -LiteralPath $targetMod) {
            $rollbackMessages.Add("Original mod remains at the backup because the target folder is occupied: $backupPath")
        } else {
            try {
                Move-Item -LiteralPath $backupPath -Destination $targetMod -ErrorAction Stop
                $rollbackMessages.Add("Restored the original mod from: $backupPath")
            } catch {
                $rollbackMessages.Add("Original mod is safe at: $backupPath (restore it manually)")
            }
        }
    }

    if ($rollbackMessages.Count -eq 0) {
        $rollbackMessages.Add("No rollback action was needed.")
    }
    foreach ($message in $rollbackMessages) {
        Write-Info $message
    }
    Write-Err "If access was denied, right-click install-13357625.bat and choose 'Run as administrator'."
    Exit-Installer 5
}
