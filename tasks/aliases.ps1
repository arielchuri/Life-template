# Life Workspace — Task & Workflow PowerShell Aliases & Functions
# Sourced in your $PROFILE:
#   . "/path/to/Life/tasks/aliases.ps1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LifeRoot = Split-Path -Parent $ScriptDir
$env:TODO_DIR = $ScriptDir

if (-not $env:EDITOR) {
    if (Get-Command hx -ErrorAction SilentlyContinue) {
        $env:EDITOR = "hx"
    } elseif (Get-Command nvim -ErrorAction SilentlyContinue) {
        $env:EDITOR = "nvim"
    } elseif (Get-Command notepad -ErrorAction SilentlyContinue) {
        $env:EDITOR = "notepad"
    }
}

# Core Task Functions
function task { todo list @args }
function t { Clear-Host; Get-Date; Write-Host ""; todo list @args }
function n {
    if (Test-Path "$env:TODO_DIR\tasks.md") {
        rg -m 1 '\- \[[A-Z\s]\]' "$env:TODO_DIR\tasks.md"
    } elseif (Test-Path "$env:TODO_DIR\today.md") {
        rg -m 1 '\- \[[A-Z\s]\]' "$env:TODO_DIR\today.md"
    }
}
function tg { rg --glob '*.md' -i @args }

# Editor Openers
function ei { & $env:EDITOR "$env:TODO_DIR\inbox.md" }
function et { & $env:EDITOR "$env:TODO_DIR\oneoffs.md", "$env:TODO_DIR\projects.md", "$env:TODO_DIR\tags.md" }
function eo { & $env:EDITOR "$env:TODO_DIR\tomorrow.md", "$env:TODO_DIR\someday.md", "$env:TODO_DIR\waiting.md" }
function ea { & $env:EDITOR "$env:TODO_DIR\today.md", "$env:TODO_DIR\inbox.md", "$env:TODO_DIR\oneoffs.md", "$env:TODO_DIR\projects.md" }

# Notes Functions (knowledge/_Memory/notes/)
function ng {
    $notesDir = Join-Path $LifeRoot "knowledge\_Memory\notes"
    if (Test-Path $notesDir) {
        rg -iN --heading -C 2 @args $notesDir
    } else {
        Write-Host "Notes directory not found at $notesDir" -ForegroundColor Yellow
    }
}

function ne {
    $notesDir = Join-Path $LifeRoot "knowledge\_Memory\notes"
    if (Get-Command fzf -ErrorAction SilentlyContinue) {
        $file = Get-ChildItem -Path $notesDir -Filter "*.md" -Recurse | Select-Object -ExpandProperty FullName | fzf --prompt="Select Note: "
        if ($file) { & $env:EDITOR $file }
    } else {
        & $env:EDITOR $notesDir
    }
}

function nt {
    $notesDir = Join-Path $LifeRoot "knowledge\_Memory\notes"
    if (Get-Command fzf -ErrorAction SilentlyContinue) {
        $file = Get-ChildItem -Path $notesDir -Filter "*.md" -Recurse | Select-Object -ExpandProperty FullName | fzf --prompt="Select Note for Tasks: "
        if ($file) { rg '\- \[[^xX\-]\]' $file }
    } else {
        rg '\- \[[^xX\-]\]' $notesDir
    }
}

function ns {
    $shortcuts = Join-Path $LifeRoot "knowledge\_Memory\notes\notesshortcuts.md"
    if (Test-Path $shortcuts) {
        Get-Content $shortcuts
    } else {
        Write-Host "Shortcut cheat sheet: see README.md for available task and note shortcuts."
    }
}
