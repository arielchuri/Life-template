# ==============================================================================
# Life Workspace Bootstrap & Dependency Checker (Windows PowerShell)
# ==============================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Life Workspace — Setup & Dependency Checker (Windows)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TasksDir = Join-Path $ScriptDir "tasks"
$ScriptsDir = Join-Path $TasksDir "scripts"

$Missing = @()

# 1. Check Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "  [OK] Python ($pyVer)" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Python is missing." -ForegroundColor Red
    $Missing += "python"
}

# 2. Check Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Git" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Git is missing." -ForegroundColor Red
    $Missing += "git"
}

# 3. Check Ripgrep
if (Get-Command rg -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Ripgrep (rg)" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Ripgrep (rg) is missing." -ForegroundColor Yellow
    $Missing += "ripgrep"
}

# 4. Check Editor
if ($env:EDITOR) {
    Write-Host "  [OK] Editor ($env:EDITOR)" -ForegroundColor Green
} elseif (Get-Command hx -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Editor (Helix: hx)" -ForegroundColor Green
} elseif (Get-Command notepad -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Editor (Notepad)" -ForegroundColor Green
}

Write-Host ""

# Instructions if missing
if ($Missing.Count -gt 0) {
    Write-Host "-----------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host " Missing Dependencies Detected. Install with winget:" -ForegroundColor Yellow
    Write-Host "-----------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host ""
    if ($Missing -contains "python") { Write-Host "  winget install Python.Python.3.12" }
    if ($Missing -contains "git")    { Write-Host "  winget install Git.Git" }
    if ($Missing -contains "ripgrep"){ Write-Host "  winget install BurntSushi.ripgrep.MSVC" }
    Write-Host ""
}

# Setup Python environment for pytodo
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " Setting up PyTodo Task Manager CLI..." -ForegroundColor Cyan
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan

$VenvDir = Join-Path $ScriptsDir ".venv"
python -m venv $VenvDir
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
& $PipExe install --upgrade pip
& $PipExe install -e $ScriptsDir

Write-Host "  [OK] pytodo installed into virtualenv." -ForegroundColor Green
Write-Host ""

# PowerShell Profile integration
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " Shell Aliases Setup" -ForegroundColor Cyan
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "To enable shortcuts (task, t, n, ei, et, eo, ea, tg), add this line"
Write-Host "to your PowerShell profile ($PROFILE):"
Write-Host ""
$SourceLine = ". `"$TasksDir\aliases.ps1`""
Write-Host "  $SourceLine" -ForegroundColor White
Write-Host ""

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Setup complete! Next steps:" -ForegroundColor Cyan
Write-Host " 1. Start your AI assistant (e.g. Claude Code / Antigravity)."
Write-Host " 2. The assistant will detect your fresh setup and guide you"
Write-Host "    through the onboarding interview."
Write-Host "=================================================================" -ForegroundColor Cyan
