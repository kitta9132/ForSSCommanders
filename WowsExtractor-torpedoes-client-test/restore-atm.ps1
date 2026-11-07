[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$Build,

    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [string]$BackupDir,

    [switch]$DryRun,

    [switch]$Elevated
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# This is the same fixed allow-list as install-wowsmod.ps1. Restore never
# moves a path that the installer would not have moved as ATM.
$script:AllowedAtmPaths = @(
    'PnFMods\AdvancedTorpedoMarkerPy',
    'gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound',
    'gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound'
)

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

function Exit-Restore {
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
    param([string]$BackupDirectory)
    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $psExe -PathType Leaf)) {
        $psExe = 'powershell.exe'
    }

    $command = '& ' + (ConvertTo-SingleQuoted $PSCommandPath) +
        ' -Build ' + (ConvertTo-SingleQuoted $Build) +
        ' -GameRoot ' + (ConvertTo-SingleQuoted $GameRoot)
    if (-not [string]::IsNullOrWhiteSpace($BackupDirectory)) {
        $command += ' -BackupDir ' + (ConvertTo-SingleQuoted $BackupDirectory)
    }
    $command += ' -Elevated'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $process = Start-Process -FilePath $psExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) `
        -Verb RunAs -Wait -PassThru -ErrorAction Stop
    return $process.ExitCode
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
        Write-Err "Close it completely, then run the ATM restore again."
        Exit-Restore 3
    }
}

function Read-AtmManifest {
    param([string]$Path)
    $manifest = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    $itemsProperty = $manifest.PSObject.Properties['items']
    if ($null -eq $itemsProperty) {
        throw "Manifest has no items: $Path"
    }
    $entries = @($itemsProperty.Value)
    if ($entries.Count -eq 0) {
        throw "Manifest has no items: $Path"
    }

    $items = @()
    $seen = @{}
    foreach ($entry in $entries) {
        $relativeProperty = $entry.PSObject.Properties['relativePath']
        if ($null -eq $relativeProperty) {
            throw "Manifest item has no relativePath: $Path"
        }
        $relative = ([string]$relativeProperty.Value).Replace('/', '\').TrimEnd('\')
        if ([string]::IsNullOrWhiteSpace($relative)) {
            throw "Manifest item has an empty relativePath: $Path"
        }
        if ([IO.Path]::IsPathRooted($relative)) {
            throw "Manifest item is rooted: $relative"
        }
        if (($relative -split '\\') -contains '..') {
            throw "Manifest item contains '..': $relative"
        }
        if (-not ($script:AllowedAtmPaths -contains $relative)) {
            throw "Manifest item is not a known ATM path: $relative"
        }
        $key = $relative.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            throw "Manifest contains a duplicate ATM path: $relative"
        }
        $seen[$key] = $true
        $items += [pscustomobject]@{ RelativePath = $relative }
    }

    $status = ''
    $statusProperty = $manifest.PSObject.Properties['status']
    if ($null -ne $statusProperty) {
        $status = [string]$statusProperty.Value
    }
    $buildNumber = ''
    $buildProperty = $manifest.PSObject.Properties['build']
    if ($null -ne $buildProperty) {
        $buildNumber = [string]$buildProperty.Value
    }
    $resModsPath = ''
    $resModsProperty = $manifest.PSObject.Properties['resMods']
    if ($null -ne $resModsProperty) {
        $resModsPath = [string]$resModsProperty.Value
    }

    return [pscustomobject]@{
        Status = $status
        Build = $buildNumber
        ResMods = $resModsPath
        Items = @($items)
        ManifestPath = $Path
    }
}

function Get-AtmBackupCandidates {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return @()
    }
    return @(
        Get-ChildItem -LiteralPath $Root -Directory -Filter 'ATM_disabled_*' -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending
    )
}

function Find-ActiveAtmBackup {
    param([string]$Root)
    $candidates = @(Get-AtmBackupCandidates -Root $Root)
    foreach ($candidate in $candidates) {
        $manifestPath = Join-Path $candidate.FullName 'atm-disable-manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            continue
        }
        try {
            $manifest = Read-AtmManifest -Path $manifestPath
        } catch {
            continue
        }
        if ($manifest.Status -eq 'restored') {
            continue
        }
        foreach ($entry in $manifest.Items) {
            if (Test-Path -LiteralPath (Join-Path $candidate.FullName $entry.RelativePath)) {
                return [pscustomobject]@{
                    Directory = $candidate.FullName
                    ManifestPath = $manifestPath
                    Manifest = $manifest
                }
            }
        }
    }
    return $null
}

function Get-RestorePlan {
    param(
        [string]$ResModsPath,
        [string]$BackupPath,
        [object[]]$Items
    )
    $plan = @()
    foreach ($entry in $Items) {
        $source = Join-Path $ResModsPath $entry.RelativePath
        $backup = Join-Path $BackupPath $entry.RelativePath
        $backupExists = Test-Path -LiteralPath $backup
        $sourceExists = Test-Path -LiteralPath $source
        if ($backupExists -and $sourceExists) {
            throw "Refusing to overwrite an existing ATM path: $source"
        }
        if (-not $backupExists -and -not $sourceExists) {
            throw "ATM backup item is missing: $backup"
        }
        $plan += [pscustomobject]@{
            RelativePath = $entry.RelativePath
            Source = $source
            Backup = $backup
            Restore = $backupExists
        }
    }
    return @($plan)
}

function Restore-AtmItems {
    param([object[]]$Plan)
    $messages = New-Object System.Collections.Generic.List[string]
    foreach ($item in $Plan) {
        if (-not $item.Restore) {
            $messages.Add("ATM item already present, not moved: $($item.RelativePath)")
            continue
        }
        $parent = Split-Path -Parent $item.Source
        [void][IO.Directory]::CreateDirectory($parent)
        Move-Item -LiteralPath $item.Backup -Destination $item.Source -ErrorAction Stop
        $messages.Add("Restored ATM item: $($item.RelativePath)")
    }
    return $messages.ToArray()
}

function Mark-AtmManifestRestored {
    param([string]$ManifestPath)
    $manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
    $manifest | Add-Member -NotePropertyName status -NotePropertyValue 'restored' -Force
    $manifest | Add-Member -NotePropertyName restoredAt -NotePropertyValue ((Get-Date).ToString('o')) -Force
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
    Write-Err "Could not determine the script folder."
    exit 6
}

$gameRootFull = [IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
$target = Join-Path (Join-Path $gameRootFull 'bin') $Build
$resMods = Join-Path $target 'res_mods'
$backupRoot = Join-Path $resMods '_wowsmod_backups'
$backupDirFull = $null
if (-not [string]::IsNullOrWhiteSpace($BackupDir)) {
    $backupDirFull = [IO.Path]::GetFullPath($BackupDir).TrimEnd('\')
}

try {
    $target = Assert-TargetBuild $gameRootFull $Build
    if (-not (Test-Path -LiteralPath $resMods -PathType Container)) {
        throw "res_mods folder was not found: $resMods"
    }
} catch {
    Write-Err $_.Exception.Message
    Write-Err "Preflight failed. No files were changed."
    Exit-Restore 2
}

$selected = $null
if ($null -ne $backupDirFull) {
    $manifestPath = Join-Path $backupDirFull 'atm-disable-manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        Write-Err "ATM manifest was not found in the specified backup folder: $manifestPath"
        Exit-Restore 2
    }
    try {
        $manifest = Read-AtmManifest -Path $manifestPath
    } catch {
        Write-Err $_.Exception.Message
        Write-Err "Preflight failed. No files were changed."
        Exit-Restore 2
    }
    $selected = [pscustomobject]@{
        Directory = $backupDirFull
        ManifestPath = $manifestPath
        Manifest = $manifest
    }
} else {
    $selected = Find-ActiveAtmBackup -Root $backupRoot
}

if ($null -eq $selected) {
    Write-Info "No active ATM disable backup was found under: $backupRoot"
    Write-Info "Nothing to restore. ATM may already be enabled, or it was never disabled."
    Exit-Restore 0
}

$manifest = $selected.Manifest
if (-not [string]::IsNullOrWhiteSpace($manifest.Build) -and $manifest.Build -ne $Build) {
    Write-Err "The ATM backup is for build $($manifest.Build), not build $Build."
    Write-Err "Use the restore script for the matching build. No files were changed."
    Exit-Restore 2
}
if (-not [string]::IsNullOrWhiteSpace($manifest.ResMods)) {
    try {
        $manifestResMods = [IO.Path]::GetFullPath($manifest.ResMods).TrimEnd('\')
    } catch {
        $manifestResMods = $manifest.ResMods
    }
    if (-not [string]::Equals($manifestResMods, $resMods.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        Write-Err "The ATM backup was made for a different res_mods folder."
        Write-Err "  Manifest: $manifestResMods"
        Write-Err "  Current : $resMods"
        Write-Err "Use the restore script for the matching game folder. No files were changed."
        Exit-Restore 2
    }
}

try {
    $plan = @(Get-RestorePlan -ResModsPath $resMods -BackupPath $selected.Directory -Items $manifest.Items)
} catch {
    Write-Err $_.Exception.Message
    Write-Err "Preflight failed. No files were changed."
    Exit-Restore 2
}

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN - read-only preflight. No files will be moved."
    Write-Host "  Target build   : $target"
    Write-Host "  ATM backup     : $($selected.Directory)"
    Write-Host "  Manifest       : $($selected.ManifestPath)"
    foreach ($item in $plan) {
        if ($item.Restore) {
            Write-Host "  Restore        : $($item.RelativePath)"
            Write-Host "                   -> $($item.Source)"
        } else {
            Write-Host "  Already there  : $($item.RelativePath)"
        }
    }
    Write-Host "  Shared deps    : PnFModsLoader.py and TTaroModUtils are not touched"
    Write-Host ""
    Write-Ok "DRY RUN OK - the ATM restore plan is valid. No changes were made."
    Exit-Restore 0
}

Stop-IfGameRunning

$needsAdmin = Test-UnderProgramFiles $target
$isAdmin = Test-IsAdmin
if ($needsAdmin -and -not $isAdmin) {
    if ($Elevated) {
        Write-Err "Administrator rights are still not available."
        Write-Err "Right-click restore-atm.bat and choose 'Run as administrator'."
        Exit-Restore 4
    }
    Write-Info "Administrator rights are required for the target folder."
    Write-Info "Requesting elevation (UAC prompt)..."
    try {
        $childExitCode = Invoke-ElevatedSelf -BackupDirectory $backupDirFull
    } catch {
        Write-Err "Elevation was cancelled or failed: $($_.Exception.Message)"
        Write-Err "Right-click restore-atm.bat and choose 'Run as administrator'."
        Exit-Restore 4
    }
    Exit-Restore $childExitCode
}

try {
    Stop-IfGameRunning
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Target build folder disappeared: $target"
    }
    $plan = @(Get-RestorePlan -ResModsPath $resMods -BackupPath $selected.Directory -Items $manifest.Items)
    $messages = @(Restore-AtmItems -Plan $plan)
    foreach ($message in $messages) {
        if ($message.StartsWith('Restored', [StringComparison]::OrdinalIgnoreCase)) {
            Write-Ok $message
        } else {
            Write-Info $message
        }
    }
    Mark-AtmManifestRestored -ManifestPath $selected.ManifestPath

    Write-Host ""
    Write-Ok "ATM restore completed successfully."
    Write-Host "  Target build   : $target"
    Write-Host "  ATM backup     : $($selected.Directory)"
    Write-Host "  Manifest       : $($selected.ManifestPath) (marked restored)"
    Write-Host "  Shared deps    : PnFModsLoader.py and TTaroModUtils were left untouched"
    Write-Host "  Note           : WowsExtractor files were not changed."
    Write-Host ""
    Exit-Restore 0
} catch {
    Write-Err $_.Exception.Message
    Write-Err "ATM restore failed. No success is reported."
    Write-Err "The remaining ATM files are still in: $($selected.Directory)"
    Write-Err "If a target path is occupied, move it away manually, then run this restore again."
    Exit-Restore 5
}
