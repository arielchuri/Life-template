# Life Workspace — Task & Workflow Shell Aliases
# Sourced automatically or added to your ~/.zshrc or ~/.bashrc:
#   source "/path/to/Life/tasks/aliases.sh"

LIFE_TASKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
LIFE_ROOT="$(cd "$LIFE_TASKS_DIR/.." && pwd)"

# Ensure default editor exists
if [ -z "$EDITOR" ]; then
  if command -v hx >/dev/null 2>&1; then
    export EDITOR="hx"
  elif command -v nvim >/dev/null 2>&1; then
    export EDITOR="nvim"
  elif command -v nano >/dev/null 2>&1; then
    export EDITOR="nano"
  else
    export EDITOR="vi"
  fi
fi

# Set TODO_DIR environment variable
export TODO_DIR="$LIFE_TASKS_DIR"

# Core GTD Task Aliases
alias task="todo list"
alias t="clear && date && echo '' && todo list"
alias n="rg -m=1 '\- \[[A-Z\s]\]' \"$LIFE_TASKS_DIR/tasks.md\" 2>/dev/null || rg -m=1 '\- \[[A-Z\s]\]' \"$LIFE_TASKS_DIR/today.md\""
alias tg="rg --glob '*.md' -i"

# Quick Editor Split Openers
alias ei="$EDITOR \"$LIFE_TASKS_DIR/inbox.md\""
alias et="$EDITOR \"$LIFE_TASKS_DIR/oneoffs.md\" \"$LIFE_TASKS_DIR/projects.md\" \"$LIFE_TASKS_DIR/tags.md\""
alias eo="$EDITOR \"$LIFE_TASKS_DIR/tomorrow.md\" \"$LIFE_TASKS_DIR/someday.md\" \"$LIFE_TASKS_DIR/waiting.md\""
alias ea="$EDITOR \"$LIFE_TASKS_DIR/today.md\" \"$LIFE_TASKS_DIR/inbox.md\" \"$LIFE_TASKS_DIR/oneoffs.md\" \"$LIFE_TASKS_DIR/projects.md\""

# Notes & Knowledge Base Aliases (knowledge/_Memory/notes/)
ng() {
  local search_dir="$LIFE_ROOT/knowledge/_Memory/notes"
  if [ -d "$search_dir" ]; then
    rg -iN --color=always --heading -C 2 "$@" "$search_dir"
  else
    echo "Notes directory not found at $search_dir"
  fi
}

ne() {
  local notes_dir="$LIFE_ROOT/knowledge/_Memory/notes"
  if command -v fzf >/dev/null 2>&1; then
    local selected
    selected=$(find "$notes_dir" -name "*.md" 2>/dev/null | fzf --prompt="Select Note: ")
    [ -n "$selected" ] && $EDITOR "$selected"
  else
    $EDITOR "$notes_dir"
  fi
}

nt() {
  local notes_dir="$LIFE_ROOT/knowledge/_Memory/notes"
  if command -v fzf >/dev/null 2>&1; then
    local selected
    selected=$(find "$notes_dir" -name "*.md" 2>/dev/null | fzf --prompt="Select Note for Tasks: ")
    [ -n "$selected" ] && rg "\- \[[^xX\-]\]" "$selected"
  else
    rg "\- \[[^xX\-]\]" "$notes_dir"
  fi
}

alias ns="cat \"$LIFE_ROOT/knowledge/_Memory/notes/notesshortcuts.md\" 2>/dev/null || echo 'Run \"cat \$LIFE_ROOT/knowledge/_Memory/notes/notesshortcuts.md\" or check README.md for shortcuts.'"
