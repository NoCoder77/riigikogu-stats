# Build Windows one-folder exe (API + UI). Run from project root.
# Requires: Python 3.10+, Node.js/npm for the UI build.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    $Root = $PSScriptRoot
    if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
        throw "Run from riigikogu_stats project (pyproject.toml not found)."
    }
}
Set-Location $Root

Write-Host "Installing Python package (dev extras)..."
python -m pip install -e ".[dev]" -q

$ui = Join-Path $Root "ui"
if (-not (Test-Path (Join-Path $ui "package.json"))) {
    throw "ui/package.json not found"
}
Write-Host "Building UI (relative API base)..."
Push-Location $ui
try {
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    $env:VITE_API_BASE_URL = ""
    npm run build
} finally {
    Pop-Location
}

$distUi = Join-Path $ui "dist"
if (-not (Test-Path (Join-Path $distUi "index.html"))) {
    throw "UI build failed: ui/dist/index.html missing"
}

Write-Host "Running PyInstaller..."
$specArgs = @(
    "--noconfirm",
    "--clean",
    "--name", "riigikogu_stats",
    "--onedir",
    "--console",
    "--paths", (Join-Path $Root "src"),
    "--add-data", "sql;sql",
    "--add-data", "ui/dist;ui_dist",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols",
    "--hidden-import", "uvicorn.protocols.http",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.lifespan",
    "--hidden-import", "uvicorn.lifespan.on",
    (Join-Path $Root "src\run_riigikogu_stats.py")
)
python -m PyInstaller @specArgs

$outDir = Join-Path $Root "dist\riigikogu_stats"
if (-not (Test-Path $outDir)) {
    # PyInstaller may nest under dist/riigikogu_stats/riigikogu_stats
    $alt = Join-Path $Root "dist\riigikogu_stats"
    if (Test-Path $alt) { $outDir = $alt }
}
$envExample = Join-Path $Root ".env.example"
if ((Test-Path $envExample) -and (Test-Path $outDir)) {
    Copy-Item $envExample (Join-Path $outDir ".env.example") -Force
}

Write-Host "Done. Output: $outDir"
