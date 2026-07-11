# deploy.ps1 -- copy TeXLib's Sublime integration into Sublime Text's Packages/User.
#
# Why this exists: Sublime/LaTeXTools loads the builder + settings from
# Packages/User, NOT from this repo folder. After editing any file here you must
# copy it across and restart Sublime, or the change has no effect. This script
# does the copy (and a safety syntax-check of the Python builder) in one step.
#
# Run:  right-click > "Run with PowerShell", or from a terminal:
#         powershell -ExecutionPolicy Bypass -File deploy.ps1
# Then: RESTART Sublime Text so the updated Python builder reloads.

$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot   # the repo's Sublime/ folder (where this script lives)

# --- locate Packages/User (Sublime Text 4 first, then legacy ST3) -------------
$candidates = @(
    (Join-Path $env:APPDATA 'Sublime Text\Packages\User'),
    (Join-Path $env:APPDATA 'Sublime Text 3\Packages\User')
)
$dest = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $dest) {
    Write-Host "ERROR: could not find Sublime Text's Packages\User folder. Looked in:" -ForegroundColor Red
    $candidates | ForEach-Object { Write-Host "  $_" }
    exit 1
}

# --- files to deploy (builder + build system + settings) ----------------------
# Dev-only files (README.md, test_texlib_builder.py, this script) are NOT copied.
$files = @(
    'texlib_builder.py',
    'texlib_pdfpost.py',
    'TeXLib.sublime-build',
    'LaTeXTools.sublime-settings',
    'LaTeX.sublime-settings',
    'Preferences.sublime-settings',
    'Default (Windows).sublime-keymap',
    'Default.sublime-commands',
    'Package Control.sublime-settings'
)

# --- safety: syntax-check the Python files before copying a broken one --------
$pyfiles = @('texlib_builder.py', 'texlib_pdfpost.py')
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if ($py) {
    foreach ($f in $pyfiles) {
        $path = Join-Path $src $f
        if (Test-Path $path) {
            & $py.Source -m py_compile $path
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: $f failed py_compile -- NOT deploying." -ForegroundColor Red
                exit 1
            }
            Write-Host "syntax OK: $f"
        }
    }
} else {
    Write-Host "note: python not found; skipping syntax check." -ForegroundColor Yellow
}

# --- copy ---------------------------------------------------------------------
Write-Host "Deploying TeXLib Sublime integration -> $dest"
foreach ($f in $files) {
    $from = Join-Path $src $f
    if (Test-Path -LiteralPath $from) {
        Copy-Item -LiteralPath $from -Destination (Join-Path $dest $f) -Force
        Write-Host "  copied  $f"
    } else {
        Write-Host "  skip    $f (not in repo)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Done. RESTART Sublime Text so the updated Python builder loads." -ForegroundColor Green
