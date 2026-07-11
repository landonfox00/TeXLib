# deploy-plugin.ps1 -- junction this package into Sublime Text's Packages folder.
#
# Unlike the copy-based Sublime/deploy.ps1 (which serves the LaTeXTools builder
# in Packages/User), this links the whole native package in place, so edits to
# texlib.py hot-reload on save -- no redeploy, and a restart only the first time.
#
# Directory junctions (mklink /J) need NO admin rights, unlike symlinks.

$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot

# py_compile-gate the plugin, mirroring deploy.ps1's guard on the builder.
$py = (Get-Command python -ErrorAction SilentlyContinue)
if ($py) {
    & $py.Source -m py_compile (Join-Path $src 'texlib.py')
    if ($LASTEXITCODE -ne 0) { throw "texlib.py failed py_compile -- aborting deploy." }
    Write-Host "py_compile OK: texlib.py"
} else {
    Write-Host "python not found; skipping py_compile check."
}

$packages = Join-Path $env:APPDATA 'Sublime Text\Packages'
if (-not (Test-Path $packages)) { throw "Sublime Packages folder not found: $packages" }

$link = Join-Path $packages 'TeXLib'
if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.LinkType -eq 'Junction') {
        Write-Host "Replacing existing junction: $link"
        cmd /c rmdir "`"$link`""
    } else {
        throw "$link exists and is NOT a junction -- refusing to clobber real files."
    }
}

cmd /c mklink /J "`"$link`"" "`"$src`"" | Write-Host
Write-Host ""
Write-Host "Linked: $link -> $src"
Write-Host "Restart Sublime once. After that, texlib.py edits hot-reload on save."
Write-Host "Undo with:  cmd /c rmdir `"$link`""
