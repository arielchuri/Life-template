#!/usr/bin/env bash
# ==============================================================================
# Life Workspace Bootstrap & Dependency Checker
# Compatible with macOS and Linux (Debian, Ubuntu, Arch, Fedora)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
SCRIPTS_DIR="$TASKS_DIR/scripts"

echo "================================================================="
echo " Life Workspace — Setup & Dependency Checker"
echo "================================================================="
echo ""

# 1. Detect Operating System
OS="$(uname -s)"
DISTRO=""
if [ "$OS" = "Linux" ]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO="$ID"
    fi
fi

MISSING_DEPS=()

# 2. Check Prerequisites
echo "Checking system prerequisites..."

# Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "  [OK] Python 3 ($PY_VER)"
else
    echo "  [FAIL] Python 3 is missing."
    MISSING_DEPS+=("python3")
fi

# Git
if command -v git >/dev/null 2>&1; then
    echo "  [OK] Git"
else
    echo "  [FAIL] Git is missing."
    MISSING_DEPS+=("git")
fi

# Ripgrep (rg)
if command -v rg >/dev/null 2>&1; then
    echo "  [OK] Ripgrep (rg)"
else
    echo "  [WARN] Ripgrep (rg) is missing (strongly recommended for fast search)."
    MISSING_DEPS+=("ripgrep")
fi

# Editor
if [ -n "$EDITOR" ] && command -v "$EDITOR" >/dev/null 2>&1; then
    echo "  [OK] Editor (\$EDITOR=$EDITOR)"
elif command -v hx >/dev/null 2>&1; then
    echo "  [OK] Editor (Helix: hx)"
elif command -v nvim >/dev/null 2>&1; then
    echo "  [OK] Editor (Neovim: nvim)"
elif command -v nano >/dev/null 2>&1; then
    echo "  [OK] Editor (Nano: nano)"
else
    echo "  [WARN] No default terminal editor detected."
    MISSING_DEPS+=("editor")
fi

echo ""

# 3. If dependencies are missing, output installation instructions
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "-----------------------------------------------------------------"
    echo " Missing Dependencies Detected:"
    echo "-----------------------------------------------------------------"
    
    if [ "$OS" = "Darwin" ]; then
        echo "On macOS with Homebrew (brew.sh), install missing tools with:"
        echo ""
        INSTALL_CMDS="brew install"
        for dep in "${MISSING_DEPS[@]}"; do
            case "$dep" in
                python3) INSTALL_CMDS="$INSTALL_CMDS python@3.12" ;;
                git)     INSTALL_CMDS="$INSTALL_CMDS git" ;;
                ripgrep) INSTALL_CMDS="$INSTALL_CMDS ripgrep" ;;
                editor)  INSTALL_CMDS="$INSTALL_CMDS helix" ;;
            esac
        done
        echo "  $INSTALL_CMDS"
        echo ""
    elif [ "$OS" = "Linux" ]; then
        case "$DISTRO" in
            ubuntu|debian|pop)
                echo "On Debian/Ubuntu, run:"
                echo "  sudo apt update && sudo apt install -y python3 python3-pip python3-venv git ripgrep"
                ;;
            arch|manjaro)
                echo "On Arch Linux, run:"
                echo "  sudo pacman -S --needed python python-pip git ripgrep helix"
                ;;
            fedora)
                echo "On Fedora, run:"
                echo "  sudo dnf install -y python3 python3-pip git ripgrep helix"
                ;;
            *)
                echo "Please install ${MISSING_DEPS[*]} using your package manager."
                ;;
        esac
        echo ""
    fi
fi

# 4. Install pytodo task CLI
echo "-----------------------------------------------------------------"
echo " Setting up PyTodo Task Manager CLI..."
echo "-----------------------------------------------------------------"

VENV_DIR="$SCRIPTS_DIR/.venv"

if command -v uv >/dev/null 2>&1; then
    echo "Using uv to set up virtual environment..."
    uv venv "$VENV_DIR" --python python3
    uv pip install --python "$VENV_DIR/bin/python" -e "$SCRIPTS_DIR"
elif command -v python3 >/dev/null 2>&1; then
    echo "Using standard python3 -m venv..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -e "$SCRIPTS_DIR"
fi

# Link binary to ~/.local/bin if directory exists
mkdir -p "$HOME/.local/bin"
if [ -f "$VENV_DIR/bin/todo" ]; then
    ln -sf "$VENV_DIR/bin/todo" "$HOME/.local/bin/todo"
    echo "  [OK] 'todo' CLI linked to $HOME/.local/bin/todo"
fi

echo ""
echo "-----------------------------------------------------------------"
echo " Shell Aliases Setup"
echo "-----------------------------------------------------------------"
echo "To enable shortcuts (task, t, n, ei, et, eo, ea, tg), add this line"
echo "to your ~/.zshrc or ~/.bashrc:"
echo ""
echo "  source \"$TASKS_DIR/aliases.sh\""
echo ""

CURRENT_SHELL="$(basename "$SHELL")"
RC_FILE="$HOME/.${CURRENT_SHELL}rc"
if [ -f "$RC_FILE" ]; then
    if grep -q "tasks/aliases.sh" "$RC_FILE" 2>/dev/null; then
        echo "  [OK] Aliases already present in $RC_FILE"
    else
        read -p "Would you like to automatically append this to $RC_FILE? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "" >> "$RC_FILE"
            echo "# Life Workspace GTD Aliases" >> "$RC_FILE"
            echo "source \"$TASKS_DIR/aliases.sh\"" >> "$RC_FILE"
            echo "  [OK] Appended to $RC_FILE. Run 'source $RC_FILE' to load."
        fi
    fi
fi

echo ""
echo "================================================================="
echo " Setup complete! Next steps:"
echo " 1. Start your AI assistant (e.g. Claude Code / Antigravity)."
echo " 2. The assistant will detect your fresh setup and guide you"
echo "    through the onboarding interview."
echo "================================================================="
