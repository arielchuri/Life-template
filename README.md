# Life Workspace Template

A modular personal life, GTD task management, and knowledge governor workspace designed for collaboration with AI coding assistants (Claude Code, Antigravity, Cursor, etc.).

---

## Quickstart

### 1. Run the Setup & Dependency Checker

**On macOS & Linux:**
```bash
./install.sh
```

**On Windows (PowerShell):**
```powershell
.\install.ps1
```

The script will:
- Check for system dependencies (`python >= 3.10`, `git`, `ripgrep`, `$EDITOR`).
- Display copy-paste commands if any required tools are missing.
- Install the `pytodo` task manager CLI into a local virtualenv.
- Offer to configure your shell aliases (`task`, `t`, `n`, `ei`, `et`, `ea`, `tg`).

---

### 2. Launch Your AI Assistant

Open the repository in your terminal and launch your assistant (e.g. `claude` or `agy`):

```bash
claude
```

The AI reads `CLAUDE.md` and detects that this is a fresh setup. It will automatically initiate a guided **onboarding interview** to configure:
1. Your identity, location, and background.
2. Your daily schedule blocks in `tasks/schedule.md`.
3. Your initial active projects in `projects/` and `tasks/projects.md`.
4. Your tool and communication preferences.

---

## GTD Workflow & Shell Shortcuts

Once `tasks/aliases.sh` (or `tasks/aliases.ps1`) is sourced in your shell profile:

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| **`task`** | `todo list` | Displays active tasks filtered by priority. |
| **`t`** | `todo list` (with date) | Clears terminal, displays current date and active tasks. |
| **`n`** | Next action | Instantly outputs the single next uncompleted action. |
| **`ei`** | Edit Inbox | Opens `tasks/inbox.md` in your `$EDITOR`. |
| **`et`** | Edit Tasks | Opens primary task files (`oneoffs.md`, `projects.md`, `tags.md`). |
| **`eo`** | Edit Other | Opens `tomorrow.md`, `someday.md`, and `waiting.md`. |
| **`ea`** | Edit All | Opens all primary task files in split editor buffers. |
| **`tg`** | Task Grep | Searches markdown task lists using `ripgrep`. |

---

## Directory Overview

```text
Life/
├── CLAUDE.md                   # AI governor rules and onboarding prompt
├── .agent_rules                # Cross-agent operational rules
├── install.sh / install.ps1    # Bootstrap script for all platforms
├── homepage.html               # Starter browser dashboard
├── routines/                   # Daily, weekly, and monthly rhythm templates
├── tasks/                      # GTD task lists and pytodo CLI tool
├── ongoing/                    # Perpetual life areas lacking termination
├── projects/                   # Finite workspaces (personal/ and work/)
├── knowledge/_Memory/          # Durable long-term memory store
├── tools/                      # Local utilities catalog
├── logs/                       # Daily append-only activity records
└── .tmp/                       # Gitignored scratch space
```
