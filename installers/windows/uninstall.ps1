# Uninstall LocalReader Pro from Windows. Settings > Apps runs this when you
# choose Uninstall on LocalReader Pro.
#
# Removes the app folder, its shortcuts and its Settings > Apps entry. Your
# library and settings (%APPDATA%\LocalReader Pro) are kept unless you say
# otherwise, and Python, installed by the installer as its own program, stays
# in Settings > Apps for you to remove separately if nothing else uses it.
#
# For tests: LOCALREADER_UNATTENDED=1 answers every question with the default
# (keep the library), LOCALREADER_DATA overrides where the library is.
#
# Windows PowerShell 5.1, ASCII only: see install.ps1.

$ErrorActionPreference = 'Stop'
$AppName = 'LocalReader Pro'
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ($env:LOCALREADER_DATA) { $DataDir = $env:LOCALREADER_DATA } else { $DataDir = Join-Path $env:APPDATA $AppName }
$Unattended = ($env:LOCALREADER_UNATTENDED -eq '1')
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalReaderPro'

function Note($message) { Write-Host "    $message" }
function Ask($question, $default) {
    if ($Unattended) { return $default }
    $hint = '[y/N]'
    if ($default) { $hint = '[Y/n]' }
    $reply = Read-Host "$question $hint"
    if (-not $reply) { return $default }
    return ($reply -match '^[yY]')
}
function Is-Link($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    return [bool]((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}

Write-Host "Uninstall $AppName"
Note "App: $AppDir"
if (-not (Ask "Remove $AppName from this computer?" $true)) { exit 0 }

# The app must be closed for its files to be deleted.
$running = Get-Process pythonw, python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($AppDir, [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    if (-not (Ask "$AppName is running. Close it now?" $true)) { exit 1 }
    $running | Stop-Process -Force
    Start-Sleep -Seconds 2
}

foreach ($folder in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    $link = Join-Path $folder "$AppName.lnk"
    if (Test-Path -LiteralPath $link) { Remove-Item -LiteralPath $link -Force; Note "Removed $link" }
}
if (Test-Path $UninstallKey) { Remove-Item -Path $UninstallKey -Recurse -Force; Note 'Removed from Settings > Apps.' }

# The library is reached through junctions inside the app folder. Windows
# PowerShell 5.1's Remove-Item -Recurse follows junctions and would delete the
# library behind them, so they are unlinked first, on their own.
foreach ($inside in @((Join-Path $AppDir 'dist\userdata'), (Join-Path $AppDir 'dist\app\models'))) {
    if (Is-Link $inside) { [IO.Directory]::Delete($inside) }
    elseif (Test-Path -LiteralPath $inside) {
        Write-Host "Stopped: $inside is a real folder, not a link to your library, so the app folder was left in place." -ForegroundColor Red
        exit 1
    }
}
Set-Location $env:TEMP
Remove-Item -LiteralPath $AppDir -Recurse -Force
Note "Removed $AppDir"

if (Test-Path -LiteralPath $DataDir) {
    if (Ask "Also delete your library and settings ($DataDir)? This cannot be undone." $false) {
        Remove-Item -LiteralPath $DataDir -Recurse -Force
        Note "Removed $DataDir"
    } else {
        Note "Kept your library in $DataDir. Installing again picks it up."
    }
}
Write-Host ''
Write-Host "$AppName is uninstalled."
if (-not $Unattended) { Read-Host 'Press Enter to close' | Out-Null }
