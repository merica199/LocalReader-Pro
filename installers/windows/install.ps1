# Install LocalReader Pro on Windows. Run by double-clicking
# "Install on Windows.bat" at the top of the repository.
#
# What it does, in order:
#   1. Python 3.12, from python.org, for this Windows user only (no
#      administrator password), unless a Python 3.12 is already installed.
#   2. The app in %LOCALAPPDATA%\Programs\LocalReader Pro, the standard place
#      for programs installed for one user. The code there is its own git clone
#      of this repository, following the same branch on GitHub, which is what
#      lets the app update itself (Help > Check for Updates, or the Updates
#      panel). This folder can be deleted afterwards.
#   3. Your library and settings in %APPDATA%\LocalReader Pro, outside the app,
#      so reinstalling or uninstalling never touches them.
#   4. The Python libraries, in a private environment inside the app.
#   5. The voice model (about 115 MB) and FFmpeg (for MP3 export).
#   6. Start Menu and Desktop shortcuts, and an entry in Settings > Apps to
#      uninstall it.
#
# Running it again is safe: it repairs what is missing and moves an existing
# install forward to this folder's version, and it never deletes your library.
#
# For tests: LOCALREADER_APP and LOCALREADER_DATA override the two locations,
# LOCALREADER_UNATTENDED=1 answers yes to every question and does not open the
# app at the end, LOCALREADER_NO_SHORTCUTS=1 skips shortcuts and the Settings >
# Apps entry, and LOCALREADER_FORCE_PYTHON_DOWNLOAD=1 ignores any Python already
# installed (test machines have one, which would leave the download untested).
#
# Written for Windows PowerShell 5.1 (built into Windows 10 and 11): no newer
# syntax, and ASCII only, since 5.1 reads a file without a byte order mark as
# the system code page.

param([switch]$Unattended)

$ErrorActionPreference = 'Stop'
# Invoke-WebRequest in 5.1 is many times slower while drawing its progress bar.
$ProgressPreference = 'SilentlyContinue'

$AppName = 'LocalReader Pro'
$Src = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ($env:LOCALREADER_APP) { $AppDir = $env:LOCALREADER_APP } else { $AppDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName" }
if ($env:LOCALREADER_DATA) { $DataDir = $env:LOCALREADER_DATA } else { $DataDir = Join-Path $env:APPDATA $AppName }
if ($env:LOCALREADER_UNATTENDED -eq '1') { $Unattended = $true }
$NoShortcuts = ($env:LOCALREADER_NO_SHORTCUTS -eq '1')
$ForcePythonDownload = ($env:LOCALREADER_FORCE_PYTHON_DOWNLOAD -eq '1')

# The last 3.12 release python.org built a Windows installer for. The hash is
# python.org's own, from python-3.12.10-amd64.exe.spdx.json.
$PythonVersion = '3.12.10'
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$PythonSha256 = '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalReaderPro'

function Step($message) { Write-Host ''; Write-Host "==> $message" -ForegroundColor Cyan }
function Note($message) { Write-Host "    $message" }
function Fail($message) {
    Write-Host ''
    Write-Host "Install stopped: $message" -ForegroundColor Red
    exit 1
}
function Ask($question) {
    if ($Unattended) { return $true }
    $reply = Read-Host "$question [Y/n]"
    return -not ($reply -match '^[nN]')
}
# Native programs report failure by exit code, which -ErrorAction never sees.
function Check($what) {
    if ($LASTEXITCODE -ne 0) { Fail "$what failed (exit code $LASTEXITCODE). See the messages above." }
}
# Every native program runs through this. Windows PowerShell 5.1 turns a
# native program's stderr into PowerShell errors when it is redirected, and
# with ErrorActionPreference at Stop the first one ends the script, even for
# git's progress messages. Here it is Continue, and success is judged by
# $LASTEXITCODE alone.
function Run {
    $ErrorActionPreference = 'Continue'
    $exe = $args[0]
    $rest = @()
    if ($args.Count -gt 1) { $rest = $args[1..($args.Count - 1)] }
    & $exe @rest
}
function Is-Link($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    $item = Get-Item -LiteralPath $path -Force
    return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}
# Removes a junction without touching what it points to. Windows PowerShell
# 5.1's Remove-Item -Recurse follows a junction and deletes the files behind it,
# so links are always taken out this way before any folder is deleted.
function Remove-Link($path) {
    if (Is-Link $path) { [IO.Directory]::Delete($path) }
}

trap {
    Write-Host ''
    Write-Host "Install stopped by an unexpected error: $_" -ForegroundColor Red
    exit 1
}

if ($env:OS -ne 'Windows_NT') { Fail 'this installer is for Windows. On a Mac, use "Install on Mac.command".' }

Write-Host "$AppName installer"
Write-Host "Installing from: $Src"
Note "App: $AppDir"
Note "Your library and settings: $DataDir"

# --- Git -----------------------------------------------------------------------
function Find-Git {
    $cmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @(
            (Join-Path $env:ProgramFiles 'Git\cmd\git.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe'))) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}
$Git = Find-Git
if (-not $Git) {
    Step 'Installing Git (needed to install and to update the app)'
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { Fail 'Git is not installed. Install it from https://git-scm.com/download/win and run this again.' }
    Run $winget.Source install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements
    Check 'Installing Git'
    $Git = Find-Git
    if (-not $Git) { Fail 'Git was installed but could not be found. Restart the computer and run this again.' }
}
Run $Git -C $Src rev-parse --git-dir 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail 'this folder is not a git clone, so the installed app could not update itself. Download it with: git clone https://github.com/merica199/LocalReader-Pro.git'
}

# --- 1. Python 3.12 --------------------------------------------------------------
Step 'Checking for Python 3.12'
function Find-Python($onlyOurs) {
    $found = @()
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py -and -not $onlyOurs) {
        $exe = Run $py.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { $found += $exe.Trim() }
    }
    $found += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    if (-not $onlyOurs) { $found += (Join-Path $env:ProgramFiles 'Python312\python.exe') }
    foreach ($exe in $found) {
        # The Microsoft Store's python.exe is a stub that opens the Store.
        if ($exe -like '*\WindowsApps\*') { continue }
        if (Test-Path -LiteralPath $exe) { return $exe }
    }
    return $null
}
$Python = $null
if (-not $ForcePythonDownload) { $Python = Find-Python $false }
if ($Python) {
    Note "Found $Python"
} else {
    Note "Downloading Python $PythonVersion from python.org (about 27 MB)"
    $installer = Join-Path $env:TEMP "python-$PythonVersion-amd64.exe"
    Invoke-WebRequest -Uri $PythonUrl -OutFile $installer -UseBasicParsing
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $PythonSha256) {
        Remove-Item -LiteralPath $installer -Force
        Fail "the Python download did not match python.org's published fingerprint, so it was not run."
    }
    Note 'Installing Python for this Windows user'
    $pyArgs = @('/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0',
        'Include_test=0', 'Include_doc=0', 'Shortcuts=0', 'AssociateFiles=0')
    $proc = Start-Process -FilePath $installer -ArgumentList $pyArgs -Wait -PassThru
    Remove-Item -LiteralPath $installer -Force
    if ($proc.ExitCode -ne 0) { Fail "the Python installer failed (exit code $($proc.ExitCode))." }
    $Python = Find-Python $true
    if (-not $Python) { Fail 'Python was installed but could not be found.' }
    Note "Installed $Python"
}

# --- 2. The code -------------------------------------------------------------------
Step 'Placing the app'
$inPlace = $false
if (Test-Path -LiteralPath $AppDir) {
    $inPlace = ((Resolve-Path -LiteralPath $AppDir).Path.TrimEnd('\') -eq $Src.TrimEnd('\'))
}
if ($inPlace) {
    Note 'Already installed here; refreshing this install.'
} elseif (Test-Path -LiteralPath (Join-Path $AppDir '.git')) {
    Note "Found an existing install; moving it forward to this folder's version."
    $changed = Run $Git -C $AppDir status --porcelain --untracked-files=no
    if ($changed) { Fail "files in the installed app have been edited ($AppDir). Uninstall it from Settings > Apps (your library is kept) and run this again." }
    Run $Git -C $AppDir fetch --quiet $Src HEAD; Check 'Reading this folder'
    Run $Git -C $AppDir merge-base --is-ancestor FETCH_HEAD HEAD
    if ($LASTEXITCODE -eq 0) {
        Note 'The installed app is already this version or newer.'
    } else {
        Run $Git -C $AppDir merge --ff-only --quiet FETCH_HEAD
        if ($LASTEXITCODE -ne 0) { Fail 'the installed app and this folder have different changes. Uninstall it from Settings > Apps (your library is kept) and run this again.' }
    }
} else {
    if (Test-Path -LiteralPath $AppDir) {
        # Left by an install that was interrupted.
        $userdata = Join-Path $AppDir 'dist\userdata'
        if ((Test-Path -LiteralPath $userdata) -and -not (Is-Link $userdata)) {
            Fail "$AppDir holds a library from an older install. Move $userdata somewhere safe and run this again."
        }
        Remove-Link $userdata
        Remove-Link (Join-Path $AppDir 'dist\app\models')
        Remove-Item -LiteralPath $AppDir -Recurse -Force
    }
    $branch = (Run $Git -C $Src rev-parse --abbrev-ref HEAD | Select-Object -First 1).Trim()
    if ($branch -eq 'HEAD') { Fail "this clone is not on a branch. Run: git -C `"$Src`" checkout main" }
    $origin = (Run $Git -C $Src remote get-url origin 2>$null | Select-Object -First 1)
    if (-not $origin) { Fail "this clone has no 'origin' remote to update from." }
    $origin = $origin.Trim()
    New-Item -ItemType Directory -Force -Path (Split-Path $AppDir) | Out-Null
    Run $Git clone --quiet --branch $branch $Src $AppDir; Check 'Copying the code'
    # Updates come from where this folder was cloned from, not from this folder.
    Run $Git -C $AppDir remote set-url origin $origin; Check 'Setting the update source'
    Note "Copied the code ($branch, following $origin)."
}

# --- 3. Library and settings, outside the app ------------------------------------
Step 'Connecting your library'
function Link-Data($inside, $outside) {
    New-Item -ItemType Directory -Force -Path $outside | Out-Null
    if (Is-Link $inside) {
        if ((Get-Item -LiteralPath $inside -Force).Target -eq $outside) { return }
        Remove-Link $inside
    } elseif (Test-Path -LiteralPath $inside) {
        # A real folder here holds data from before the split: move it out once.
        if (Get-ChildItem -LiteralPath $outside -Force) {
            Fail "both $inside and $outside contain data. Move one of them aside and run this again."
        }
        Get-ChildItem -LiteralPath $inside -Force | Move-Item -Destination $outside
        Remove-Item -LiteralPath $inside -Force
    }
    New-Item -ItemType Junction -Path $inside -Target $outside | Out-Null
}
Link-Data (Join-Path $AppDir 'dist\userdata') (Join-Path $DataDir 'userdata')
Link-Data (Join-Path $AppDir 'dist\app\models') (Join-Path $DataDir 'models')
Note "Library: $(Join-Path $DataDir 'userdata')"

# --- 4. Python libraries -------------------------------------------------------------
Step 'Installing Python libraries (the first time takes several minutes)'
$venv = Join-Path $AppDir 'venv'
$vpy = Join-Path $venv 'Scripts\python.exe'
$reuse = $false
if (Test-Path -LiteralPath $vpy) {
    Run $vpy -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' 2>$null | Out-Null
    $reuse = ($LASTEXITCODE -eq 0)
}
if ($reuse) {
    Note 'Using the existing environment.'
} else {
    if ((Test-Path -LiteralPath $venv) -and -not (Test-Path -LiteralPath (Join-Path $venv 'pyvenv.cfg'))) {
        Fail "$venv exists and is not a Python environment."
    }
    if (Test-Path -LiteralPath $venv) { Remove-Item -LiteralPath $venv -Recurse -Force }
    Run $Python -m venv $venv; Check 'Creating the Python environment'
}
Run $vpy -m pip install --quiet --disable-pip-version-check --upgrade pip; Check 'Updating pip'
Run $vpy -m pip install --disable-pip-version-check -r (Join-Path $AppDir 'dist\requirements.txt') |
    Where-Object { $_ -notmatch '^(Requirement already satisfied|  Using cached)' }
Check 'Installing the Python libraries'
Run $vpy -c 'import kokoro_onnx, webview, fastapi'; Check 'Checking the Python libraries'
# The speech engine (espeak-ng) keeps the path to its data in a fixed-size
# buffer and cuts anything longer, after which every sentence fails. A long
# account name can push the install folder past it.
$espeakLen = [int](Run $vpy -c 'import espeakng_loader; print(len(str(espeakng_loader.get_data_path()).encode()))')
if ($espeakLen -ge 150) { Fail "the app's folder path is too long for the speech engine ($espeakLen characters to its data, limit 150). Set LOCALREADER_APP to a shorter folder and run this again." }

# --- 5. Voice model and FFmpeg ----------------------------------------------------------
$appCode = Join-Path $AppDir 'dist\app'
Step 'Voice model'
$models = Join-Path $DataDir 'models'
if ((Test-Path -LiteralPath (Join-Path $models 'kokoro.int8.onnx')) -and (Test-Path -LiteralPath (Join-Path $models 'voices.bin'))) {
    Note 'Already downloaded.'
} else {
    Note 'Downloading (about 115 MB)...'
    Push-Location $appCode
    try {
        # Python's own quotes are single quotes (doubled inside this PowerShell
        # string): Windows PowerShell 5.1 strips double quotes from arguments
        # it passes to a program, which turned "cpu" into a bare name.
        Run $vpy -c 'from logic.downloader import download_kokoro_model; download_kokoro_model(''cpu'')'
        Check 'Downloading the voice model'
    } finally { Pop-Location }
}

Step 'FFmpeg (for MP3 export)'
if (Test-Path -LiteralPath (Join-Path $AppDir 'dist\bin\ffmpeg.exe')) {
    Note 'Already installed.'
} else {
    Note 'Downloading (about 100 MB)...'
    Push-Location $appCode
    try {
        Run $vpy -c 'import sys; from logic.dependency_manager import FFMPEGInstaller; ok, err = FFMPEGInstaller().install(); print(err or ''FFmpeg installed''); sys.exit(0 if ok else 1)'
        # Not fatal: the app offers the same download on first export.
        if ($LASTEXITCODE -ne 0) { Note 'FFmpeg did not install; the app will offer it the first time you export.' }
    } finally { Pop-Location }
}

# --- 6. Shortcuts and Settings > Apps ----------------------------------------------------
$pythonw = Join-Path $venv 'Scripts\pythonw.exe'
$mainPy = Join-Path $AppDir 'dist\main.py'
$icon = Join-Path $AppDir 'assets\icon.ico'
if (-not $NoShortcuts) {
    Step 'Shortcuts'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
        $link = $shell.CreateShortcut((Join-Path $folder "$AppName.lnk"))
        $link.TargetPath = $pythonw
        $link.Arguments = "`"$mainPy`""
        $link.WorkingDirectory = (Join-Path $AppDir 'dist')
        $link.IconLocation = "$icon,0"
        $link.Description = 'Read documents aloud with a voice that runs on this computer'
        $link.Save()
        Note "Added $(Join-Path $folder "$AppName.lnk")"
    }

    $version = '1.0'
    $match = Select-String -LiteralPath $mainPy -Pattern '_APP_VERSION = "([^"]+)"'
    if ($match) { $version = $match.Matches[0].Groups[1].Value }
    New-Item -Path $UninstallKey -Force | Out-Null
    $uninstaller = Join-Path $AppDir 'installers\windows\uninstall.ps1'
    $values = @{
        DisplayName     = $AppName
        DisplayVersion  = $version
        Publisher       = 'merica199'
        InstallLocation = $AppDir
        DisplayIcon     = $icon
        UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`""
    }
    foreach ($name in $values.Keys) { Set-ItemProperty -Path $UninstallKey -Name $name -Value $values[$name] }
    Set-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -Type DWord
    Set-ItemProperty -Path $UninstallKey -Name NoRepair -Value 1 -Type DWord
    Note 'Added to Settings > Apps, where it can be uninstalled.'
}

Step 'Done'
Note "$AppName is installed in $AppDir"
if (-not $inPlace) { Note "This folder ($Src) is no longer needed and can be deleted." }
Note 'Updates: in the app, Help > Check for Updates, or the Updates panel in the sidebar.'
$running = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($running) {
    Note "$AppName is running. Close it and open it again to use this version."
} elseif (-not $Unattended -and (Ask "Open $AppName now?")) {
    Start-Process -FilePath $pythonw -ArgumentList "`"$mainPy`"" -WorkingDirectory (Join-Path $AppDir 'dist')
}
exit 0
