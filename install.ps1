param(
    [string]$App,
    [string]$Repository = 'https://github.com/btsouth/t3code-customize.git',
    [string]$Branch = 'main'
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required. Install Git for Windows and run this again.'
}
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw 'Python 3.10 or newer is required, with python.exe on PATH.' }
& $pythonCommand.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or newer is required.' }
$customizeRepo = Join-Path $env:LOCALAPPDATA 't3code-customize\repo'
if (Test-Path -LiteralPath (Join-Path $customizeRepo '.git')) {
    $remote = & git -C $customizeRepo remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote -ne $Repository) {
        throw "Existing checkout has a different origin: $customizeRepo"
    }
    & git -C $customizeRepo pull --ff-only
} elseif (Test-Path -LiteralPath $customizeRepo) {
    throw "Destination already exists and is not a checkout: $customizeRepo"
} else {
    & git -c core.longpaths=true -c core.autocrlf=false clone --branch $Branch $Repository $customizeRepo
}
if ($LASTEXITCODE -ne 0) { throw 'Could not download the customization repository.' }
$buildArgs = @((Join-Path $customizeRepo 't3code-customize'), 'build')
if ($App) { $buildArgs += @('--app', $App) }
& $pythonCommand.Source @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE). See the log printed above." }
