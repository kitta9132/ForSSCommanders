# Read-only resolver for the WoWS client build that was actually launched.
#
# Priority:
#   1. -Build (explicit, still checked against <GameRoot>\bin\<build>)
#   2. <GameRoot>\preferences.xml <last_server_version>
#   3. Latest "WorldOfWarships..." start line in <GameRoot>\profile\python.log
#
# Only the resolved build is written to stdout so batch callers can capture it
# with FOR /F. Diagnostics go to stderr. There is deliberately no "highest
# build number" fallback: an unconfirmed build is an error.

[CmdletBinding()]
param(
    [string]$GameRoot = 'C:\Program Files (x86)\Steam\steamapps\common\World of Warships',
    [string]$Build = ''
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    [Console]::Error.WriteLine('[ERROR] ' + $Message)
    exit 1
}

function Read-SharedText([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $stream = $null
    $reader = $null
    try {
        # The game keeps python.log open while it runs. Allow concurrent
        # readers and writers instead of failing with a sharing violation.
        $stream = New-Object System.IO.FileStream(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        $reader = New-Object System.IO.StreamReader(
            $stream,
            [System.Text.Encoding]::UTF8,
            $true
        )
        return $reader.ReadToEnd()
    } catch {
        Fail ('Could not read ' + $Path + ': ' + $_.Exception.Message)
    } finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }
        if ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

function Get-BuildFromPreferences([string]$Text) {
    $match = [regex]::Match(
        $Text,
        '<last_server_version>\s*([0-9][0-9,\s]*?)\s*</last_server_version>',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if (-not $match.Success) {
        return $null
    }

    $raw = $match.Groups[1].Value
    $parts = @($raw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($parts.Count -eq 0) {
        return $null
    }

    $candidate = $parts[$parts.Count - 1]
    if ($candidate -notmatch '^\d+$') {
        return $null
    }
    return $candidate
}

function Get-BuildFromPythonLog([string]$Text) {
    $regex = [regex]::new(
        'WorldOfWarships(?:64)?\s+(\d+(?:\s*,\s*\d+){3})\b.*\bstarting\b',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    $found = $regex.Matches($Text)
    if ($found.Count -eq 0) {
        return $null
    }

    # The log appends, so the last start line is the latest launch.
    $raw = $found[$found.Count - 1].Groups[1].Value
    $parts = @($raw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($parts.Count -eq 0) {
        return $null
    }

    $candidate = $parts[$parts.Count - 1]
    if ($candidate -notmatch '^\d+$') {
        return $null
    }
    return $candidate
}

function Test-InstalledBuild([string]$Root, [string]$Candidate) {
    $binPath = [System.IO.Path]::Combine($Root, 'bin', $Candidate)
    if (-not (Test-Path -LiteralPath $binPath -PathType Container)) {
        Fail ('Detected build ' + $Candidate + ' has no installed bin folder: ' + $binPath + '. Update the game, or set WOWS_BUILD to an installed build.')
    }
}

try {
    $root = [System.IO.Path]::GetFullPath($GameRoot)
} catch {
    Fail ('Invalid game root: ' + $GameRoot)
}

if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    Fail ('Game root was not found: ' + $root)
}

$explicit = $Build.Trim()
if ($explicit -ne '') {
    if ($explicit -notmatch '^\d+$') {
        Fail ('The explicit build must contain digits only: ' + $explicit)
    }
    Test-InstalledBuild -Root $root -Candidate $explicit
    Write-Output $explicit
    exit 0
}

$preferencesPath = [System.IO.Path]::Combine($root, 'preferences.xml')
$preferencesText = Read-SharedText -Path $preferencesPath
$preferencesBuild = $null
if ($null -ne $preferencesText) {
    $preferencesBuild = Get-BuildFromPreferences -Text $preferencesText
}

$logPath = [System.IO.Path]::Combine($root, 'profile', 'python.log')
$logText = Read-SharedText -Path $logPath
$logBuild = $null
if ($null -ne $logText) {
    $logBuild = Get-BuildFromPythonLog -Text $logText
}

if (($null -ne $preferencesBuild) -and ($null -ne $logBuild) -and ($preferencesBuild -ne $logBuild)) {
    Fail ('Launch evidence disagrees: preferences.xml says ' + $preferencesBuild + ', but the latest python.log start says ' + $logBuild + '. Start the game once so both records update, or set WOWS_BUILD to the intended build.')
}

$resolved = $null
if ($null -ne $preferencesBuild) {
    $resolved = $preferencesBuild
} elseif ($null -ne $logBuild) {
    $resolved = $logBuild
}

if ($null -eq $resolved) {
    Fail ('No launch build could be confirmed. Expected <last_server_version> in ' + $preferencesPath + ' or a WorldOfWarships start line in ' + $logPath + '. Start the game once, then retry. Do not guess a build.')
}

Test-InstalledBuild -Root $root -Candidate $resolved
Write-Output $resolved
exit 0