# Projects — Scoped Workspaces

This file governs everything under `projects/`. It applies whenever an agent operates inside a project.

## Isolation Principle

Projects are **self-contained scoped workspaces**. Each project directory holds its own `README.md`, `tasks.md`, notes, decisions, and code. Most work inside a project should stay inside that project — do not drag project-local detail into global memory, and do not spray project state across the workspace.

## Domain Split

Projects are organized by domain, mirroring the memory wiki:
- **`projects/personal/<name>/`** — Personal side projects, research, creative endeavors, personal tooling.
- **`projects/work/<name>/`** — Professional, employment, client, or career workbenches.

## Project Structure Conventions

- **Short Projects (Single File in `tasks/projects/`):** If a project has only tasks and a simple plan, map it to a single file under `tasks/projects/<project-slug>.md` containing `## Plan` and `## Tasks`.
- **Major Projects (Directory-Based):** If a project contains detailed reference guides or multiple notes, promote it to a directory holding:
  - `README.md` (high-level plan, status, goal)
  - `tasks.md` (checklist actions)
  - `reference/` (reference inputs and background docs)
  - `artifacts/` (deliverables, code, or generated assets)

## Required `README.md` Format

```markdown
# [Project Name]

- **Status**: active | planning | paused | completed
- **Started**: YYYY-MM-DD
- **Goal**: [one-liner — why this exists]

## Description
[What this project is. Context. Why it matters.]

## Notes
[Anything relevant that doesn't fit elsewhere.]
```
