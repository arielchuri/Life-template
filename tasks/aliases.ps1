# Life Workspace — Task & Workflow PowerShell Aliases & Functions
# Sourced in your $PROFILE:
#   . "/path/to/Life/tasks/aliases.ps1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
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

function task { todo list @args }
function t { Clear-Host; Get-Date; Write-Host ""; todo list @args }
function ei { & $env:EDITOR "$env:TODO_DIR\inbox.md" }
function et { & $env:EDITOR "$env:TODO_DIR\oneoffs.md", "$env:TODO_DIR\projects.md", "$env:TODO_DIR\tags.md" }
function eo { & $env:EDITOR "$env:TODO_DIR\tomorrow.md", "$env:TODO_DIR\someday.md", "$env:TODO_DIR\waiting.md" }
function ea { & $env:EDITOR "$env:TODO_DIR\today.md", "$env:TODO_DIR\inbox.md", "$env:TODO_DIR\oneoffs.md", "$env:TODO_DIR\projects.md" }
function tg { rg --glob '*.md' -i @args }
