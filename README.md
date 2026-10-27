# Life Workspace Template

An AI-governed personal life management operating system. Built for continuous collaboration with agentic AI assistants (Antigravity, Claude Code, Cursor) acting as your personal governor, executive assistant, and memory keeper.

---

## What is the Life Workspace?

This workspace is not a code repository—it is a **central nervous system for your everyday life, family, home, and projects**. 

Instead of fragmenting your life across disconnected apps, everything lives in human-readable Markdown files that you and your AI agent co-maintain:

- 📬 **Email Briefings & Communications**: Daily automated email scans across personal and work accounts, distilling inbox clutter into actionable summaries and flagging contractor/vendor follow-ups.
- 🏫 **Family & Kids' Schooling**: Academic progress monitoring, automated Google Classroom / SIS scraping, and generation of printable daily/weekly student action sheets and study aids.
- 🏡 **Household & Life Maintenance (`ongoing/`)**: Continuous management for home repairs, contractor bids (HVAC, floor refinishing, windows), appliance warranties, cars, and medical/health routines.
- ✈️ **Multi-Project Management (`projects/`)**: Dedicated workbenches for finite personal, legal, professional, and creative endeavors (from international family travel itineraries and apostille legal filings to course syllabi and creative zines).
- 🧠 **Durable Memory & Notes (`knowledge/`)**: An Obsidian-compatible personal wiki that keeps your background, preferences, decisions, and reference notes permanently grounded for the AI.
- ✅ **GTD Task Engine (`tasks/`)**: Fast, lightweight task prioritization powered by `pytodo` with instant terminal visibility.

---

## Daily Workflow & Shell Shortcuts

Add `tasks/aliases.sh` (or `tasks/aliases.ps1`) to your shell profile to manage tasks and notes instantly:

### 📝 Notes & Knowledge (`knowledge/_Memory/notes/`)
| Shortcut | Action | Description |
| :--- | :--- | :--- |
| **`ne`** | Note Edit | Fuzzy-find any markdown note and open it directly in your `$EDITOR`. |
| **`ng <query>`** | Note Grep | Instantly search across all personal knowledge notes using `ripgrep`. |
| **`nt`** | Note Tasks | Fuzzy-find notes and print any uncompleted action items inside them. |
| **`ns`** | Note Shortcuts | Display the full notes and tasks shortcuts cheat sheet. |

### 📋 GTD Tasks (`tasks/`)
| Shortcut | Action | Description |
| :--- | :--- | :--- |
| **`task`** | `todo list` | View active tasks prioritized and grouped by domain/tag. |
| **`t`** | Quick Dashboard | Clears screen, displays today's date, and outputs active tasks. |
| **`n`** | Next Action | Outputs the single next immediate uncompleted action. |
| **`tg <query>`** | Task Grep | Searches across all task markdown files with `ripgrep`. |
| **`ei`** | Edit Inbox | Opens `tasks/inbox.md` for rapid capture. |
| **`et`** | Edit Tasks | Opens primary task files (`oneoffs.md`, `projects.md`, `tags.md`). |
| **`eo`** | Edit Other | Opens backlog files (`tomorrow.md`, `someday.md`, `waiting.md`). |
| **`ea`** | Edit All | Opens all active task lists in split editor panes. |

---

## Workspace Structure

```text
Life/
├── AGENTS.md                   # AI governor rules, behavioral conventions, and onboarding (symlinked to CLAUDE.md)
├── install.sh / install.ps1    # One-click bootstrap script for macOS, Linux, and Windows
├── routines/                   # Recurring rhythms (daily action sheets, weekly resets, monthly reviews)
├── ongoing/                    # Perpetual life tracks (family, home-improvement, health, vehicles)
├── projects/                   # Finite projects across personal, home, school, work, and creative domains
├── knowledge/_Memory/          # Durable long-term memory vault, preferences, identity, and reference notes
├── tasks/                      # GTD task lists, pytodo CLI tool, and shell aliases
├── tools/                      # Automation scripts (email checkers, calendar sync, school scrapers)
├── logs/                       # Chronological activity records and daily email briefings
└── .tmp/                       # Gitignored scratchpad for throwaway work
```

---

## Quickstart

### 1. Run Setup
```bash
# macOS & Linux
./install.sh

# Windows (PowerShell)
.\install.ps1
```

### 2. Launch Your AI Assistant
Open the folder in your terminal and run your assistant (e.g. `agy` or `claude`):
```bash
agy
```
The AI reads `AGENTS.md` (or `CLAUDE.md`), recognizes a new setup, and walks you through an onboarding interview to configure your daily rhythms, active projects, and family logistics.
