# Projects Router

This file routes project tags (`+project`) to their task lists for the task runner script (`pytodo` / `todo`).

Format:
- Major projects: `## +name → [../projects/<domain>/<name>/tasks.md](../projects/<domain>/<name>/tasks.md)`
- Short projects: `## +name → [projects/<name>.md](projects/<name>.md)`
- Completed: `## [x] +name → ...`
- Paused / On Hold: `## [h] +name → ...`

## +starter-project → [projects/starter-project.md](projects/starter-project.md)
