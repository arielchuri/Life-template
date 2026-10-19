import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.panel import Panel
import os
import re
import subprocess
import sys
import time
from typing import List, Dict, Optional, Set, Union
from collections import defaultdict
import datetime

from pytodo import parsing
from pytodo import rendering
from pytodo.models import Todo, Project

# --- Configuration ---
BASE_DIR = os.environ.get("TODO_DIR")
if not BASE_DIR:
    # 1. Resolve relative to pytodo package location: tasks/scripts/pytodo/ -> tasks/
    package_tasks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(package_tasks_dir) and (os.path.exists(os.path.join(package_tasks_dir, "projects.md")) or os.path.exists(os.path.join(package_tasks_dir, "inbox.md"))):
        BASE_DIR = package_tasks_dir
    # 2. Check if current working directory has a tasks/ subfolder
    elif os.path.isdir("tasks") and os.path.exists(os.path.join("tasks", "projects.md")):
        BASE_DIR = os.path.abspath("tasks")
    # 3. Fallbacks
    elif os.path.isdir(os.path.expanduser("~/Life/tasks/")):
        BASE_DIR = os.path.expanduser("~/Life/tasks/")
    else:
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ONEOFFS_FILE = os.path.join(BASE_DIR, "oneoffs.md")
PROJECTS_FILE = os.path.join(BASE_DIR, "projects.md")
TAGS_FILE = os.path.join(BASE_DIR, "tags.md")
INBOX_FILE = os.path.join(BASE_DIR, "inbox.md")
TODO_MD_FILE = os.path.join(BASE_DIR, "alltasks.md")
TODO_LIST_FILE = os.path.join(BASE_DIR, "tasks.md")
SOMEDAY_FILE = os.path.join(BASE_DIR, "someday.md")
TOMORROW_FILE = os.path.join(BASE_DIR, "tomorrow.md")
TWOMINUTES_FILE = os.path.join(BASE_DIR, "2minutes.md")
# --- End Configuration ---


app = typer.Typer(
    epilog="Use `[command] --help` for more information on a specific command.",
    add_help_option=True,
    rich_markup_mode="rich"
)


@app.callback()
def main_callback():
    """
    [bold]PyTodo[/bold] - A modern, file-based todo manager.

    Supports dynamic external project routing (e.g. `## +project → \[path](path)`)
    and explicit project activation states (`## \[x] +project` or `## \[-] +project` to mark inactive).

    [bold]External Shell Commands (.bash_aliases):[/bold]
      [bold green]task[/bold green] (.bash_aliases)       Run the todo list script (alias for 'todo')
      [bold green]et[/bold green] (.bash_aliases)         Edit main todo files in Helix (oneoffs, projects, tags)
      [bold green]eo[/bold green] (.bash_aliases)         Edit other todo files in Helix (tomorrow, someday, waiting)
      [bold green]ea[/bold green] (.bash_aliases)         Edit all todo files in Helix
      [bold green]ei[/bold green] (.bash_aliases)         Edit inbox in Helix
      [bold green]t[/bold green] (.bash_aliases)          Show todo list with date
      [bold green]n[/bold green] (.bash_aliases)          Show next uncompleted tasks
      [bold green]tg[/bold green] (.bash_aliases)         Search tasks with ripgrep
      [bold green]process[/bold green] (.bash_aliases)    View the workflow process guide
    """
    pass


console = Console()


def get_all_projects() -> List[Project]:
    projects = get_todos_from_file(PROJECTS_FILE, parsing.parse_projects_file, PROJECTS_FILE)
    resolved_projects = []
    processed_external_files = set()
    for project in projects:
        if not project.is_active:
            continue
        if project.external_file:
            ext_path = os.path.normpath(os.path.join(BASE_DIR, project.external_file))
            if os.path.exists(ext_path):
                if ext_path not in processed_external_files:
                    processed_external_files.add(ext_path)
                    try:
                        with open(ext_path, "r") as f:
                            ext_content = f.read()
                        
                        # Try parsing as a multi-project file first
                        ext_projects = parsing.parse_projects_file(ext_content, ext_path)
                        if ext_projects:
                            resolved_projects.extend([p for p in ext_projects if p.is_active])
                        else:
                            # Otherwise, parse as flat tasks for the current project
                            ext_lines = list(enumerate(ext_content.splitlines()))
                            project.subtasks = parsing.parse_todos_from_lines(ext_lines, ext_path)
                            resolved_projects.append(project)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not read external file {ext_path}: {e}[/yellow]")
                        resolved_projects.append(project)
                else:
                    # External file was already processed, just keep the project shell
                    resolved_projects.append(project)
            else:
                resolved_projects.append(project)
        else:
            resolved_projects.append(project)
    return resolved_projects


def get_all_todos() -> List[Todo]:
    all_todos: Dict[str, Todo] = {}
    projects = get_all_projects()
    oneoff_todos = get_todos_from_file(ONEOFFS_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f), ONEOFFS_FILE)
    tag_todos = get_todos_from_file(TAGS_FILE, parsing.parse_tags_file, TAGS_FILE)

    def assign_project_recursively(todo_list, parent_project):
        for task in todo_list:
            if not task.project:
                task.project = parent_project
            if task.subtasks:
                assign_project_recursively(task.subtasks, parent_project)

    def collect_all_subtasks(todo_list):
        """Recursively collect all subtasks from a list of todos."""
        result = []
        for task in todo_list:
            result.append(task)
            if task.subtasks:
                result.extend(collect_all_subtasks(task.subtasks))
        return result

    project_tasks = []
    for project in projects:
        assign_project_recursively(project.subtasks, project)
        project_tasks.extend(collect_all_subtasks(project.subtasks))

    for task in project_tasks:
        all_todos[task.raw_text] = task

    # Recursively collect all todos from oneoffs and tags files
    other_todos_flat = []
    for todo in oneoff_todos + tag_todos:
        other_todos_flat.extend(collect_all_subtasks([todo]))

    for todo in other_todos_flat:
        if todo.raw_text not in all_todos:
            all_todos[todo.raw_text] = todo
        else:
            existing_todo = all_todos[todo.raw_text]
            existing_tags = {t.name for t in existing_todo.tags}
            for new_tag in todo.tags:
                if new_tag.name not in existing_tags:
                    existing_todo.tags.append(new_tag)

    return list(all_todos.values())


def get_todos_from_file(file_path: str, parser_func, *args):
    try:
        with open(file_path, "r") as f:
            content = f.read()
        return parser_func(content, *args)
    except FileNotFoundError:
        return []

def apply_parent_activation(todos: List[Todo]):
    for todo in todos:
        if not todo.subtasks: continue
        apply_parent_activation(todo.subtasks)
        has_active_child = any(subtask.is_active for subtask in todo.subtasks)
        is_passively_inactive = todo.priority.strip() == '' or todo.priority.upper() in ['D', 'W']
        if has_active_child and is_passively_inactive:
            todo.priority = 'i'

def parse_indices(index_str: str) -> Set[int]:
    indices = set()
    parts = index_str.split()
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            if start.isdigit() and end.isdigit():
                indices.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            indices.add(int(part))
    return indices

def collect_all_tasks_in_group(todo: Todo) -> List[Todo]:
    """Recursively collect all tasks in a group."""
    result = [todo]
    for subtask in todo.subtasks:
        result.extend(collect_all_tasks_in_group(subtask))
    return result

def build_grouped_task_table(all_todos: List[Todo], active_priorities: Set[str], priority_map: Dict[str, int], title: str) -> tuple:
    """
    Build a table of grouped tasks sorted by highest priority.
    Returns (table, all_tasks_flat) where all_tasks_flat is a flat list of all numbered tasks.
    """
    def has_completable_task(todo: Todo) -> bool:
        """Check if a todo or any of its subtasks has a completable priority."""
        if todo.priority in active_priorities and todo.is_active:
            return True
        return any(has_completable_task(subtask) for subtask in todo.subtasks)

    def get_highest_priority(todo: Todo) -> int:
        """Get the highest priority (lowest number) in a todo and its subtasks."""
        priorities = []
        if todo.priority in active_priorities and todo.is_active:
            priorities.append(priority_map.get(todo.priority, 99))
        for subtask in todo.subtasks:
            priorities.append(get_highest_priority(subtask))
        return min(priorities) if priorities else 99

    # Get top-level tasks that have completable priorities
    top_level_todos = [t for t in all_todos if t.level == 0]
    grouped_tasks = [t for t in top_level_todos if has_completable_task(t)]
    grouped_tasks.sort(key=get_highest_priority)

    # Print header with dividers
    console.print("\n" + "═" * 60)
    console.print(f"[bold]{title.upper()}[/bold]")
    console.print("─" * 60 + "\n")

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="bold cyan", no_wrap=True)
    table.add_column("Task")

    # Flat list of all tasks in display order
    all_tasks_flat = []
    task_number = 1

    for task in grouped_tasks:
        # Add parent task
        all_tasks_flat.append(task)
        table.add_row(str(task_number), rendering.format_line(task))
        task_number += 1

        # Add subtasks with indentation and numbers
        def add_subtasks(subtask_list: List[Todo], indent_level: int = 1):
            nonlocal task_number
            for subtask in subtask_list:
                if subtask.is_active:
                    all_tasks_flat.append(subtask)
                    indent = "  " * indent_level
                    formatted = rendering.format_line(subtask)
                    indented_text = Text(indent) + formatted
                    table.add_row(str(task_number), indented_text)
                    task_number += 1
                    if subtask.subtasks:
                        add_subtasks(subtask.subtasks, indent_level + 1)
        add_subtasks(task.subtasks)

    return table, all_tasks_flat

def format_todo_line_for_markdown(raw_text: str, priority: str) -> str:
    """
    Format a todo line with markdown based on priority.
    Only formats the task text, not the prefix or metadata.
    """
    # Match the todo pattern: - [X] task text [metadata]
    # Metadata includes anything starting with +, #, @, (, or <
    match = re.match(r'^(\s*-\s*\[[^\]]*\]\s+)(.+?)(\s+[\+#@(<].*)?$', raw_text.strip())

    if not match:
        return raw_text

    prefix = match.group(1)
    task_text = match.group(2).strip()
    metadata = match.group(3) if match.group(3) else ''

    # Apply formatting based on priority
    if priority in ['x', 'X', '-']:
        # Strikethrough for completed/cancelled
        formatted_text = f"~~{task_text}~~"
    elif priority == '!':
        # Bold + italic + underline for emergency
        formatted_text = f"***<u>{task_text}</u>***"
    elif priority == 'q':
        # Italic for quick
        formatted_text = f"*{task_text}*"
    elif priority.upper() in ['A', 'B', 'C', 'D']:
        # Bold for A-D
        formatted_text = f"**{task_text}**"
    else:
        # No formatting for other priorities
        formatted_text = task_text

    return prefix + formatted_text + metadata

def update_task_in_file(todo: Todo, new_status: str):
    try:
        with open(todo.source_file, "r") as f:
            lines = f.readlines()
        if todo.line_number >= len(lines):
            console.print(f"[yellow]Warning: Line {todo.line_number} out of bounds (file has {len(lines)} lines) for task: {todo.text.strip()}[/yellow]")
            return False

        target_line = lines[todo.line_number]
        open_bracket = target_line.find('[')
        close_bracket = target_line.find(']')
        if not (0 <= open_bracket < close_bracket):
            console.print(f"[yellow]Warning: Could not find brackets in line {todo.line_number}: {target_line.strip()}[/yellow]")
            return False

        updated_line = target_line[:open_bracket+1] + new_status + target_line[close_bracket:]
        lines[todo.line_number] = updated_line
        with open(todo.source_file, "w") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        console.print(f"[bold red]Error updating task '{todo.text.strip()}':[/bold red] {e}")
        return False

def regenerate_tasks_md():
    """Generates the alltasks.md file if changes are detected."""
    unique_todos = get_all_todos()
    apply_parent_activation(unique_todos)
    active_todos = [todo for todo in unique_todos if todo.is_active]

    # Sort by priority
    priority_map = {
        '!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7,
        'i': 8, '?': 9, 't': 10, 's': 11, 'w': 12, ' ': 13
    }

    def get_highest_priority(todo: Todo) -> int:
        """Get the highest priority (lowest number) in a todo and its subtasks."""
        priorities = [priority_map.get(todo.priority, 99)]
        for subtask in todo.subtasks:
            if subtask.is_active:
                priorities.append(get_highest_priority(subtask))
        return min(priorities) if priorities else 99

    # Get top-level todos and sort by highest priority
    top_level_todos = [t for t in active_todos if t.level == 0]
    top_level_todos.sort(key=get_highest_priority)

    def collect_formatted_subtasks(todo: Todo, content_list: List[str], indent: str = ""):
        """Recursively collect todo and subtasks with formatting"""
        formatted_line = indent + format_todo_line_for_markdown(todo.raw_text.strip(), todo.priority)
        content_list.append(formatted_line)

        for subtask in todo.subtasks:
            if subtask.is_active:
                collect_formatted_subtasks(subtask, content_list, indent + "  ")

    # Build content with groups separated by horizontal rules
    header = f"# Tasks\n\nGenerated on {datetime.date.today().isoformat()}\n\n"
    content_lines = []
    prev_highest_priority = None

    for todo in top_level_todos:
        # Get highest priority for this group
        current_highest_priority = get_highest_priority(todo)

        # Insert horizontal rule if priority level changed
        if prev_highest_priority is not None and current_highest_priority != prev_highest_priority:
            content_lines.append("")
            content_lines.append("---")
            content_lines.append("")

        prev_highest_priority = current_highest_priority

        # Collect this group with all its subtasks
        collect_formatted_subtasks(todo, content_lines)

    new_content = header + "\n".join(content_lines) + "\n"

    try:
        with open(TODO_MD_FILE, "r") as f:
            old_content = f.read()
    except FileNotFoundError:
        old_content = ""

    if new_content.strip() != old_content.strip():
        with open(TODO_MD_FILE, "w") as f:
            f.write(new_content)
        console.print("[dim]Updated alltasks.md[/dim]")


def process_tickler():
    tickler_dir = os.path.join(BASE_DIR, "tickler")
    if not os.path.isdir(tickler_dir):
        return

    today = datetime.date.today()
    processed_any = False
    imported_items = []

    try:
        filenames = os.listdir(tickler_dir)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read tickler directory: {e}[/yellow]")
        return

    for filename in sorted(filenames):
        if not filename.endswith(".md"):
            continue
        
        date_str = filename[:-3]
        try:
            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
            
        if file_date <= today:
            file_path = os.path.join(tickler_dir, filename)
            try:
                with open(file_path, "r") as f:
                    content = f.read().strip()
                
                if content:
                    imported_items.append(f"<!-- Tickler: {date_str} -->\n{content}")
                    processed_any = True
                
                os.remove(file_path)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not process tickler file {filename}: {e}[/yellow]")

    if processed_any and imported_items:
        try:
            existing_content = ""
            if os.path.exists(INBOX_FILE):
                with open(INBOX_FILE, "r") as f:
                    existing_content = f.read()
            
            separator = "\n\n" if existing_content and not existing_content.endswith("\n\n") else "\n"
            if existing_content and not existing_content.endswith("\n"):
                separator = "\n\n"
                
            new_inbox_content = separator + "\n\n".join(imported_items) + "\n"
            with open(INBOX_FILE, "a") as f:
                f.write(new_inbox_content)
                
            console.print(f"[green]✓ Tickler: Imported tasks from {len(imported_items)} file(s) into [cyan]{os.path.basename(INBOX_FILE)}[/cyan].[/green]")
        except Exception as e:
            console.print(f"[red]Error writing to inbox: {e}[/red]")


@app.command(name="list")
def generate_and_list_active_todos():
    """
    Lists all active tasks. Automatically processes due/overdue tickler files.

    An active task is a top-level task with a priority of '!', 'q', 'A'-'F', 'i', or '?'.

    When a group or project is shown, only the subtasks with an active priority are shown.
    """
    process_tickler()
    unique_todos = get_all_todos()
    active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
    priority_map = {
        '!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7,
        'i': 8, '?': 9, 't': 10, 's': 11, 'x': 12, 'X': 12, '-': 13
    }

    def has_active_task(todo: Todo) -> bool:
        """Check if a todo or any of its subtasks has an active priority."""
        if todo.priority in active_priorities and todo.is_active:
            return True
        return any(has_active_task(subtask) for subtask in todo.subtasks)

    def get_highest_priority(todo: Todo) -> int:
        """Get the highest priority (lowest number) in a todo and its subtasks."""
        priorities = []
        if todo.priority in active_priorities and todo.is_active:
            priorities.append(priority_map.get(todo.priority, 99))
        for subtask in todo.subtasks:
            priorities.append(get_highest_priority(subtask))
        return min(priorities) if priorities else 99

    # Get top-level tasks that have active priorities
    top_level_todos = [t for t in unique_todos if t.level == 0]
    active_groups = [t for t in top_level_todos if has_active_task(t)]
    active_groups.sort(key=get_highest_priority)

    # Print header with dividers
    console.print("\n" + "═" * 60)
    console.print("[bold]ACTIVE TODO LIST[/bold]")
    console.print("─" * 60 + "\n")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Task")

    # Also collect plain text output for file
    plain_text_lines = [f"# Active Todo List\n\nGenerated on {datetime.date.today().isoformat()}\n"]

    # Track previous highest priority to insert horizontal rules
    prev_highest_priority = None

    for task in active_groups:
        # Get highest priority for this group
        current_highest_priority = get_highest_priority(task)

        # Insert horizontal rule if priority level changed
        if prev_highest_priority is not None and current_highest_priority != prev_highest_priority:
            plain_text_lines.append("")
            plain_text_lines.append("---")
            plain_text_lines.append("")

        prev_highest_priority = current_highest_priority

        # Add parent task to display table
        table.add_row(rendering.format_line(task))

        # Add formatted parent task to file output
        formatted_line = format_todo_line_for_markdown(task.raw_text.strip(), task.priority)
        plain_text_lines.append(formatted_line)

        # Add subtasks with indentation (only active ones for list)
        def add_subtasks(subtask_list: List[Todo], indent_level: int = 1):
            for subtask in subtask_list:
                if subtask.is_active and subtask.priority in active_priorities:
                    indent = "  " * indent_level
                    # Add to display table
                    formatted = rendering.format_line(subtask)
                    indented_text = Text(indent) + formatted
                    table.add_row(indented_text)
                    # Add formatted subtask to file output
                    formatted_line = indent + format_todo_line_for_markdown(subtask.raw_text.strip(), subtask.priority)
                    plain_text_lines.append(formatted_line)
                    if subtask.subtasks:
                        add_subtasks(subtask.subtasks, indent_level + 1)
        add_subtasks(task.subtasks)

    console.print(table)

    # Write to file only if content has changed
    new_content = "\n".join(plain_text_lines) + "\n"
    try:
        with open(TODO_LIST_FILE, "r") as f:
            old_content = f.read()
    except FileNotFoundError:
        old_content = ""

    if new_content.strip() != old_content.strip():
        with open(TODO_LIST_FILE, "w") as f:
            f.write(new_content)


@app.command(name="listall")
def generate_and_list_all_todos():
    """
    Lists all tasks that are not completed or cancelled, grouped by their source file.
    """
    all_todos = get_all_todos()
    
    # Filter for parent tasks that are active
    parent_todos = [todo for todo in all_todos if todo.level == 0 and not (todo.is_completed or todo.is_cancelled)]
    
    # Group by source file
    grouped_todos = {}
    workspace_root = os.path.abspath(os.path.join(BASE_DIR, '..'))
    for todo in parent_todos:
        abs_path = os.path.abspath(todo.source_file)
        if not abs_path.startswith(workspace_root):
            abs_path = os.path.abspath(os.path.join(BASE_DIR, todo.source_file))
        rel_path = os.path.relpath(abs_path, workspace_root)
        if rel_path not in grouped_todos:
            grouped_todos[rel_path] = []
        grouped_todos[rel_path].append(todo)
        
    priority_map = {
        '!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7,
        'i': 8, '?': 9, 't': 10, 's': 11, 'w': 12, ' ': 13
    }
    
    def get_priority_value(todo):
        return priority_map.get(todo.priority, 99)
        
    def format_todo_for_listall(todo, indent=0):
        indent_str = "  " * indent
        formatted = rendering.format_line(todo)
        return Text(indent_str) + formatted
        
    def add_all_active_subtasks(todo_list, indent=1):
        tasks = []
        for task in todo_list:
            if not (task.is_completed or task.is_cancelled):
                tasks.append((task, indent))
                if task.subtasks:
                    tasks.extend(add_all_active_subtasks(task.subtasks, indent + 1))
        return tasks

    console.print("\n" + "═" * 60)
    console.print("[bold]ALL ACTIVE TASKS[/bold]")
    console.print("─" * 60 + "\n")
    
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Task")
    
    # Sort files: tasks/oneoffs.md first, then others alphabetically
    sorted_files = sorted(grouped_todos.keys(), key=lambda x: (0 if "oneoffs.md" in x else 1, x))
    
    for rel_path in sorted_files:
        todos = grouped_todos[rel_path]
        todos.sort(key=get_priority_value)
        
        # Add file header (showing only the last 2 components of the path)
        parts = rel_path.split(os.sep)
        display_path = "/".join(parts[-2:])
        table.add_row(Text(f"{display_path}:", style="bold"))
        
        for todo in todos:
            table.add_row(format_todo_for_listall(todo, 1))
            for subtask, indent in add_all_active_subtasks(todo.subtasks, 2):
                table.add_row(format_todo_for_listall(subtask, indent))
                
    console.print(table)



@app.command()
def projects():
    """
    Lists all projects and their tasks.
    """
    projects_list = get_all_projects()
    rendering.render_projects(console, projects_list)


@app.command()
def listproj(
    project_name: Optional[str] = typer.Argument(
        None, help="Name of the project to show tasks for."
    )
):
    """
    List all tasks (both active and completed) from a project.
    """
    from rich.tree import Tree
    projects_list = get_all_projects()
    if not projects_list:
        console.print("No active projects found.")
        return

    # Merge projects with duplicate names (e.g. defined in projects.md and also having external files)
    merged_projects = []
    project_indices = {}
    for p in projects_list:
        normalized_name = p.text.lower().strip()
        if normalized_name not in project_indices:
            cloned = Project(
                text=p.text,
                subtasks=list(p.subtasks),
                source_file=p.source_file,
                line_number=p.line_number,
                raw_text=p.raw_text,
                is_cancelled=p.is_cancelled,
                is_on_hold=p.is_on_hold,
                external_file=p.external_file
            )
            project_indices[normalized_name] = len(merged_projects)
            merged_projects.append(cloned)
        else:
            idx = project_indices[normalized_name]
            existing = merged_projects[idx]
            # Extend subtasks
            existing.subtasks.extend(p.subtasks)
            if not existing.external_file and p.external_file:
                existing.external_file = p.external_file

    selected_project = None

    if project_name:
        # Perform substring matching
        query = project_name.lower().strip()
        # strip leading '+' if user entered it (e.g. +jobsearch -> jobsearch)
        if query.startswith("+"):
            query = query[1:]
        
        matches = []
        for p in merged_projects:
            match_text = p.text.lower()
            if match_text.startswith("+"):
                match_text = match_text[1:]
            if query in match_text:
                matches.append(p)
        
        if len(matches) == 1:
            selected_project = matches[0]
        elif len(matches) > 1:
            console.print(f"Multiple projects found matching '{project_name}':")
            for idx, p in enumerate(matches, 1):
                console.print(f"  {idx}) {p.text}")
            console.print("")
            choice = typer.prompt("Select a project number", type=int)
            if 1 <= choice <= len(matches):
                selected_project = matches[choice - 1]
            else:
                console.print("[red]Invalid selection.[/red]")
                return
        else:
            console.print(f"[yellow]No active projects found matching '{project_name}'.[/yellow]\n")

    if not selected_project:
        # Show menu of all active projects
        console.print("[bold cyan]Active Projects:[/bold cyan]")
        for idx, p in enumerate(merged_projects, 1):
            console.print(f"  {idx}) [bold]{p.text}[/bold] ({p.active_task_count} active tasks)")
        console.print("")
        choice = typer.prompt("Select a project to list tasks", type=int)
        if 1 <= choice <= len(merged_projects):
            selected_project = merged_projects[choice - 1]
        else:
            console.print("[red]Invalid selection.[/red]")
            return

    # Render all tasks (both active and completed) for the selected project
    console.print(f"\n[bold yellow]Project: {selected_project.text}[/bold yellow]")
    
    # Collect all unique source files for display
    source_files = set()
    if selected_project.source_file:
        source_files.add(selected_project.source_file)
    if selected_project.external_file:
        ext_path = os.path.normpath(os.path.join(BASE_DIR, selected_project.external_file))
        source_files.add(ext_path)
    for task in selected_project.subtasks:
        if task.source_file:
            source_files.add(task.source_file)

    workspace_root = os.path.abspath(os.path.join(BASE_DIR, ".."))
    for src in sorted(source_files):
        try:
            display_path = os.path.relpath(src, workspace_root)
        except ValueError:
            display_path = src
        console.print(f"  [dim]- {display_path}[/dim]")
    console.print("")

    tree = Tree("", hide_root=True, guide_style="dim")
    # Show both active and completed tasks
    rendering.add_project_to_tree(selected_project, tree, filter_completed=False)
    console.print(tree)


@app.command()
def active():
    """
    Lists all active major and short projects.
    """
    # 1. Get parsed projects from projects.md
    parsed_projects = get_all_projects()
    
    # Get all projects in registry to identify explicit inactive states
    all_registry_projects = get_todos_from_file(PROJECTS_FILE, parsing.parse_projects_file, PROJECTS_FILE)
    active_registry_paths = set()
    inactive_registry_paths = set()
    for p in all_registry_projects:
        if p.external_file:
            ext_path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            if p.is_completed or p.is_cancelled or getattr(p, "is_on_hold", False):
                inactive_registry_paths.add(ext_path)
            else:
                active_registry_paths.add(ext_path)
                
    # Map parsed projects by their normalized external file path to get task counts (summing if multiple projects route to the same file)
    project_task_counts = {}
    for p in parsed_projects:
        path = None
        if p.source_file and os.path.basename(p.source_file) != "projects.md":
            path = os.path.normpath(p.source_file)
        elif p.external_file:
            path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            
        if path:
            project_task_counts[path] = project_task_counts.get(path, 0) + p.active_task_count
            
    # 2. Scan projects/ directory for major projects
    projects_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.normpath(BASE_DIR)), "projects"))
    active_major_projects = []
    
    for domain in ["personal", "work"]:
        domain_dir = os.path.join(projects_dir, domain)
        if not os.path.isdir(domain_dir):
            continue
            
        for item in os.listdir(domain_dir):
            item_path = os.path.join(domain_dir, item)
            if not os.path.isdir(item_path) or item.startswith('.'):
                continue
                
            readme_path = os.path.join(item_path, "README.md")
            tasks_path = os.path.join(item_path, "tasks.md")
            
            # Check status in README.md
            status = ""
            goal = ""
            title = item
            
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, "r", encoding="utf-8") as f:
                        readme_content = f.read()
                    
                    title_match = re.search(r"^#\s+(.+)$", readme_content, re.MULTILINE)
                    if title_match:
                        title = title_match.group(1).strip()
                        
                    status_match = re.search(r"^[-*]?\s*\*\*Status\*\*:\s*([a-zA-Z0-9_-]+)", readme_content, re.MULTILINE | re.IGNORECASE)
                    if status_match:
                        status = status_match.group(1).strip().lower()
                    else:
                        status_sec_match = re.search(r"###\s+Status\s*\n\n?([^\n]+)", readme_content, re.IGNORECASE)
                        if status_sec_match:
                            status = "active"
                            
                    goal_match = re.search(r"^[-*]?\s*\*\*Goal\*\*:\s*(.+)$", readme_content, re.MULTILINE | re.IGNORECASE)
                    if goal_match:
                        goal = goal_match.group(1).strip()
                except Exception:
                    pass
            
            # Map tasks count
            task_count = 0
            norm_tasks_path = os.path.normpath(tasks_path)
            if norm_tasks_path in project_task_counts:
                task_count = project_task_counts[norm_tasks_path]
            
            # A major project is active if status is explicitly "active" in README or active in the registry,
            # and it is not explicitly marked inactive in the registry (projects.md)
            is_explicitly_inactive = norm_tasks_path in inactive_registry_paths and norm_tasks_path not in active_registry_paths
            is_active_proj = (status == "active" or norm_tasks_path in active_registry_paths) and not is_explicitly_inactive
            
            if is_active_proj:
                active_major_projects.append({
                    "slug": item,
                    "title": title,
                    "domain": domain,
                    "tasks": task_count,
                    "goal": goal
                })
                
    # 3. Find active short projects (defined in projects.md and ending with projects/<slug>.md)
    active_short_projects = []
    for p in parsed_projects:
        is_short = False
        if p.external_file:
            norm_path = os.path.normpath(p.external_file)
            if "tasks/projects/" in norm_path or (not norm_path.startswith("../") and norm_path.startswith("projects/")):
                is_short = True
                
        if is_short and p.is_active:
            goal = ""
            ext_path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            if os.path.exists(ext_path):
                try:
                    with open(ext_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    plan_match = re.search(r"##\s+Plan\n\n?([^\n]+)", file_content, re.IGNORECASE)
                    if plan_match:
                        goal = plan_match.group(1).strip()
                        if goal.startswith("Reference high-level"):
                            goal = ""
                except Exception:
                    pass
            
            active_short_projects.append({
                "slug": p.text.lstrip("+"),
                "title": p.text.lstrip("+"),
                "domain": "personal",
                "tasks": p.active_task_count,
                "goal": goal
            })
            
    all_active = active_major_projects + active_short_projects
    all_active.sort(key=lambda x: (x["domain"], x["slug"]))
    
    if not all_active:
        console.print("[yellow]No active projects found.[/yellow]")
        return
        
    # Render overall summary panel
    total = len(all_active)
    major_count = len(active_major_projects)
    short_count = len(active_short_projects)
    console.print(Panel(
        f"[bold white]Total Active Projects:[/bold white] [bold yellow]{total}[/bold yellow]  |  "
        f"[bold white]Major Projects:[/bold white] [bold green]{major_count}[/bold green]  |  "
        f"[bold white]Short Projects:[/bold white] [bold cyan]{short_count}[/bold cyan]",
        title="Project Limit Dashboard",
        border_style="magenta",
        expand=False
    ))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="bold yellow", overflow="fold")
    table.add_column("Domain", width=12)
    table.add_column("Type", width=10)
    table.add_column("Tasks", justify="right", width=8)
    table.add_column("Goal/Description", style="white")
    
    for proj in all_active:
        is_major = proj in active_major_projects
        type_str = "[bold green]Major[/bold green]" if is_major else "[bold blue]Short[/bold blue]"
        domain_str = "[cyan]Personal[/cyan]" if proj["domain"] == "personal" else "[orange1]Work[/orange1]"
        task_str = f"[bold red]{proj['tasks']}[/bold red]" if proj['tasks'] > 0 else "[dim]0[/dim]"
        table.add_row(
            f"+{proj['slug']}",
            domain_str,
            type_str,
            task_str,
            proj["goal"] or "[dim]No goal defined[/dim]"
        )
        
    console.print(table)


@app.command()
def inactive():
    """
    Lists all inactive major and short projects (paused, completed, cancelled, or planning).
    """
    all_registry_projects = get_todos_from_file(PROJECTS_FILE, parsing.parse_projects_file, PROJECTS_FILE)
    inactive_registry_paths = set()
    active_registry_paths = set()
    for p in all_registry_projects:
        if p.external_file:
            ext_path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            if p.is_completed or p.is_cancelled or getattr(p, "is_on_hold", False):
                inactive_registry_paths.add(ext_path)
            else:
                active_registry_paths.add(ext_path)

    # Walk projects/ directory for major projects
    projects_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.normpath(BASE_DIR)), "projects"))
    inactive_major_projects = []
    
    for domain in ["personal", "work"]:
        domain_dir = os.path.join(projects_dir, domain)
        if not os.path.isdir(domain_dir):
            continue
            
        for item in os.listdir(domain_dir):
            item_path = os.path.join(domain_dir, item)
            if not os.path.isdir(item_path) or item.startswith('.'):
                continue
                
            readme_path = os.path.join(item_path, "README.md")
            
            # Check status in README.md
            status = "planning"
            goal = ""
            title = item
            
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, "r", encoding="utf-8") as f:
                        readme_content = f.read()
                    
                    title_match = re.search(r"^#\s+(.+)$", readme_content, re.MULTILINE)
                    if title_match:
                        title = title_match.group(1).strip()
                        
                    status_match = re.search(r"^[-*]?\s*\*\*Status\*\*:\s*([a-zA-Z0-9_-]+)", readme_content, re.MULTILINE | re.IGNORECASE)
                    if status_match:
                        status = status_match.group(1).strip().lower()
                    else:
                        status_sec_match = re.search(r"###\s+Status\s*\n\n?([^\n]+)", readme_content, re.IGNORECASE)
                        if status_sec_match:
                            status = status_sec_match.group(1).strip().lower()
                            
                    goal_match = re.search(r"^[-*]?\s*\*\*Goal\*\*:\s*(.+)$", readme_content, re.MULTILINE | re.IGNORECASE)
                    if goal_match:
                        goal = goal_match.group(1).strip()
                except Exception:
                    pass
            
            tasks_path = os.path.join(item_path, "tasks.md")
            norm_tasks_path = os.path.normpath(tasks_path)
            
            is_explicitly_inactive = norm_tasks_path in inactive_registry_paths and norm_tasks_path not in active_registry_paths
            is_active_proj = (status == "active" or norm_tasks_path in active_registry_paths) and not is_explicitly_inactive
            
            if not is_active_proj:
                inactive_major_projects.append({
                    "slug": item,
                    "title": title,
                    "domain": domain,
                    "status": status or "inactive",
                    "goal": goal
                })
                
    # Find inactive short projects
    inactive_short_projects = []
    for p in all_registry_projects:
        is_short = False
        if p.external_file:
            norm_path = os.path.normpath(p.external_file)
            if "tasks/projects/" in norm_path or (not norm_path.startswith("../") and norm_path.startswith("projects/")):
                is_short = True
                
        if is_short and not p.is_active:
            status = "completed" if p.is_completed else "cancelled" if p.is_cancelled else "paused" if p.is_on_hold else "inactive"
            goal = ""
            ext_path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            if os.path.exists(ext_path):
                try:
                    with open(ext_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    plan_match = re.search(r"##\s+Plan\n\n?([^\n]+)", file_content, re.IGNORECASE)
                    if plan_match:
                        goal = plan_match.group(1).strip()
                        if goal.startswith("Reference high-level"):
                            goal = ""
                except Exception:
                    pass
            
            inactive_short_projects.append({
                "slug": p.text.lstrip("+"),
                "title": p.text.lstrip("+"),
                "domain": "personal",
                "status": status,
                "goal": goal
            })
            
    all_inactive = inactive_major_projects + inactive_short_projects
    all_inactive.sort(key=lambda x: (x["domain"], x["slug"]))
    
    if not all_inactive:
        console.print("[yellow]No inactive projects found.[/yellow]")
        return
        
    total = len(all_inactive)
    major_count = len(inactive_major_projects)
    short_count = len(inactive_short_projects)
    console.print(Panel(
        f"[bold white]Total Inactive Projects:[/bold white] [bold yellow]{total}[/bold yellow]  |  "
        f"[bold white]Major Projects:[/bold white] [bold green]{major_count}[/bold green]  |  "
        f"[bold white]Short Projects:[/bold white] [bold cyan]{short_count}[/bold cyan]",
        title="Inactive Projects Dashboard",
        border_style="magenta",
        expand=False
    ))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="bold yellow", overflow="fold")
    table.add_column("Domain", width=12)
    table.add_column("Type", width=10)
    table.add_column("Status", width=12)
    table.add_column("Goal/Description", style="white")
    
    for proj in all_inactive:
        is_major = proj in inactive_major_projects
        type_str = "[bold green]Major[/bold green]" if is_major else "[bold blue]Short[/bold blue]"
        domain_str = "[cyan]Personal[/cyan]" if proj["domain"] == "personal" else "[orange1]Work[/orange1]"
        
        status_color = "red" if proj["status"] in ["cancelled", "paused"] else "green" if proj["status"] == "completed" else "yellow"
        status_str = f"[{status_color}]{proj['status']}[/{status_color}]"
        
        table.add_row(
            f"+{proj['slug']}",
            domain_str,
            type_str,
            status_str,
            proj["goal"] or "[dim]No goal defined[/dim]"
        )
        
    console.print(table)


@app.command()
def tags():
    """
    Lists all tags and the number of active tasks associated with them.
    """
    all_todos = get_all_todos()
    active_todos = [todo for todo in all_todos if todo.is_active]
    tag_counts = defaultdict(int)
    for todo in active_todos:
        for tag in todo.tags:
            tag_counts[tag.name] += 1
    rendering.render_tags(console, tag_counts)


@app.command(name="@")
def context():
    """
    Lists all contexts with tasks grouped by context, sorted by priority.

    Shows all tasks except completed (x) and cancelled (-).
    """
    all_todos = get_all_todos()

    # Filter out completed and cancelled tasks
    active_todos = [todo for todo in all_todos if not (todo.is_completed or todo.is_cancelled)]

    # Group tasks by context
    context_tasks = defaultdict(list)  # context_name -> list of todos

    for todo in active_todos:
        if todo.contexts:
            for context in todo.contexts:
                context_tasks[context.name].append(todo)

    if not context_tasks:
        console.print("[yellow]No tasks with contexts found.[/yellow]")
        return

    # Priority map for sorting
    priority_map = {
        '!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7,
        'i': 8, '?': 9, 't': 10, 's': 11, 'w': 12, ' ': 13
    }

    # Print header
    console.print("\n" + "═" * 60)
    console.print("[bold]TASKS BY CONTEXT[/bold]")
    console.print("─" * 60 + "\n")

    # Sort contexts alphabetically
    for context_name in sorted(context_tasks.keys()):
        tasks = context_tasks[context_name]

        # Sort tasks by priority
        tasks.sort(key=lambda t: priority_map.get(t.priority, 99))

        # Print context header
        console.print(Text(f"@{context_name}:", style="bold green"))

        # Print tasks
        for task in tasks:
            formatted = rendering.format_line(task)
            console.print(Text("  ") + formatted)

        console.print()  # Blank line between contexts


@app.command()
def help(ctx: typer.Context):
    """
    Show help message.
    """
    print(ctx.parent.get_help())


@app.command()
def colors():
    """
    Displays the color scheme for different items.
    """
    table = Table(title="Color Scheme")
    table.add_column("Item")
    table.add_column("Color")

    table.add_row(Text("Priority A", style="bold magenta"), "bold magenta")
    table.add_row(Text("Priority B", style="bold red"), "bold red")
    table.add_row(Text("Priority C", style="bold yellow"), "bold yellow")
    table.add_row(Text("Priority D", style="bold green"), "bold green")
    table.add_row(Text("Priority E", style="bold cyan"), "bold cyan")
    table.add_row(Text("Priority F", style="bold white"), "bold white")
    table.add_row(Text("Priority i (in-progress)", style="cyan"), "cyan")
    table.add_row(Text("Priority t (tomorrow)", style="red"), "red")
    table.add_row(Text("Priority s (someday)", style="dim"), "dim")
    table.add_row(Text("Priority q (quick task)", style="black on green"), "black on green")
    table.add_row(Text("Priority w (waiting)", style="white"), "white")
    table.add_row(Text("Priority ! (emergency)", style="bold white on red blink"), "bold white on red blink")
    table.add_row(Text("Completed/Cancelled", style="dim"), "dim")
    table.add_row(Text("Project", style="dim yellow"), "dim yellow")
    table.add_row(Text("Tag", style="dim blue"), "dim blue")
    table.add_row(Text("Context", style="dim green"), "dim green")
    table.add_row(Text("Added Date", style="dim"), "dim")
    table.add_row(Text("Completion Date", style="dim"), "dim")
    table.add_row(Text("Due Date", style="dim"), "dim")
    table.add_row(Text("Markdown Link", style="underline blue"), "underline blue")
    table.add_row(Text("Hierarchy Lines", style="dim"), "dim")

    console.print(table)


def add_single_task(task_text: str, priority_char: str, show_output: bool = True):
    """Helper function to add a single task."""
    formatted_task = f"- [{priority_char}] {task_text}"
    project_match = parsing.PROJECT_REGEX.search(task_text)

    if project_match:
        project_name = project_match.group(1)
        try:
            with open(PROJECTS_FILE, "r") as f:
                lines = f.readlines()
            project_header_index = -1
            next_project_header_index = -1
            for i, line in enumerate(lines):
                if line.startswith(f"## +{project_name}"):
                    project_header_index = i
                elif project_header_index != -1 and line.startswith("## +"):
                    next_project_header_index = i
                    break
            if project_header_index == -1:
                if typer.confirm(f"Project [yellow]+{project_name}[/yellow] not found. Create it?"):
                    new_header = f"\n## +{project_name}\n"
                    with open(PROJECTS_FILE, "a") as f:
                        f.write(new_header)
                        f.write(f"{formatted_task}\n")
                    if show_output:
                        console.print(f"✓ Project [yellow]+{project_name}[/yellow] created and task added.")
                    return (True, formatted_task, f"project {project_name}")
                else:
                    console.print("Aborted.")
                    return (False, None, None)

            if next_project_header_index == -1:
                lines.append(f"\n{formatted_task}\n")
            else:
                insertion_point = next_project_header_index
                while insertion_point > project_header_index and not lines[insertion_point - 1].strip():
                    insertion_point -= 1
                lines.insert(insertion_point, f"{formatted_task}\n")

            with open(PROJECTS_FILE, "w") as f:
                f.writelines(lines)

            return (True, formatted_task, f"project {project_name}")

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Could not write to projects file: {e}")
            return (False, None, None)
    else:
        try:
            with open(INBOX_FILE, "a") as f:
                f.write(f"{formatted_task}\n")
            return (True, formatted_task, "inbox")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Could not write to inbox file: {e}")
            return (False, None, None)


@app.command()
def add(
    task_texts: List[str] = typer.Argument(None, help="The text of the task(s) to add."),
):
    """
    Adds one or more new tasks to inbox.

    Tasks can be provided as command-line arguments or piped via stdin.
    When piping, each line becomes a separate task.

    Examples:
      todo add "task one"
      todo add "task one" "task two" "task three"
      printf "quick idea\n" | todo add
      printf "task one\ntask two\n" | todo add
      wl-paste | todo add
      cat tasks.txt | todo add
    """
    tasks = []

    # Check if input is being piped
    if not sys.stdin.isatty():
        stdin_input = sys.stdin.read()
        # Strip markdown todo format (- [X] ) from piped input
        tasks = []
        for line in stdin_input.splitlines():
            line = line.strip()
            if line:
                # Remove markdown todo prefix if present
                cleaned = re.sub(r'^\s*-\s*\[[^\]]*\]\s*', '', line).strip()
                if cleaned:
                    tasks.append(cleaned)
    elif task_texts:
        tasks = task_texts
    else:
        console.print("[red]Error: No tasks provided. Use 'todo add --help' for usage.[/red]")
        raise typer.Exit(1)

    if not tasks:
        console.print("[yellow]No tasks to add (empty input)[/yellow]")
        return

    # Add all tasks and collect results
    added_tasks = []
    destinations = {}

    for task_text in tasks:
        success, formatted_task, destination = add_single_task(task_text, ' ', show_output=False)
        if success:
            added_tasks.append(formatted_task)
            if destination not in destinations:
                destinations[destination] = []
            destinations[destination].append(formatted_task)

    # Print results grouped by destination
    if added_tasks:
        for destination, tasks_list in destinations.items():
            if destination == "inbox":
                console.print(f"✓ Added to [cyan]{os.path.basename(INBOX_FILE)}[/cyan]:")
            else:
                console.print(f"✓ Added to [yellow]{destination}[/yellow]:")
            for task in tasks_list:
                console.print(f"  {task.strip()}")

        regenerate_tasks_md()
        console.print(f"\n[green]✓ Added {len(added_tasks)} task(s) successfully[/green]")
    else:
        console.print("\n[red]Failed to add tasks[/red]")
        raise typer.Exit(1)


@app.command()
def done():
    """
    Interactively mark tasks as done.
    """
    all_todos = get_all_todos()
    active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
    priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, '?': 9}

    table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Active Tasks to Complete")
    console.print(table)

    try:
        index_str = typer.prompt("\nEnter task numbers to complete (e.g. '1-3, 5'), or 'q' to quit")
        if index_str.lower() == 'q':
            console.print("No tasks completed.")
            return

        selected_indices = parse_indices(index_str)
        tasks_to_complete = []
        for i in selected_indices:
            if 1 <= i <= len(all_tasks):
                tasks_to_complete.append(all_tasks[i - 1])

        if not tasks_to_complete:
            console.print("[yellow]No valid task numbers selected.[/yellow]")
            return

        console.print("\nCompleting the following tasks:")
        completed_count = 0
        for task in tasks_to_complete:
            if update_task_in_file(task, "x"):
                console.print(f"  ✓ Completed: [dim strike]{task.text.strip()}[/dim strike]")
                completed_count += 1

        if completed_count > 0:
            console.print(f"\n[green]✓ Completed {completed_count} task(s)[/green]")
            regenerate_tasks_md()
        else:
            console.print("\n[yellow]No tasks were completed.[/yellow]")

    except typer.Abort:
        console.print("\nCancelled.")


@app.command()
def cancel():
    """
    Interactively mark tasks as cancelled.
    """
    all_todos = get_all_todos()
    active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
    priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, '?': 9}

    table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Active Tasks to Cancel")
    console.print(table)

    try:
        index_str = typer.prompt("\nEnter task numbers to cancel (e.g. '1-3, 5'), or 'q' to quit")
        if index_str.lower() == 'q':
            console.print("No tasks cancelled.")
            return

        selected_indices = parse_indices(index_str)
        tasks_to_cancel = []
        for i in selected_indices:
            if 1 <= i <= len(all_tasks):
                tasks_to_cancel.append(all_tasks[i - 1])

        if not tasks_to_cancel:
            console.print("[yellow]No valid task numbers selected.[/yellow]")
            return

        console.print("\nCancelling the following tasks:")
        cancelled_count = 0
        for task in tasks_to_cancel:
            if update_task_in_file(task, "-"):
                console.print(f"  ✗ Cancelled: [dim strike]{task.text.strip()}[/dim strike]")
                cancelled_count += 1

        if cancelled_count > 0:
            console.print(f"\n[yellow]✗ Cancelled {cancelled_count} task(s)[/yellow]")
            regenerate_tasks_md()
        else:
            console.print("\n[yellow]No tasks were cancelled.[/yellow]")

    except typer.Abort:
        console.print("\nAborted.")


def parse_priority_pairs(input_str: str) -> Dict[int, str]:
    """
    Parse number:priority pairs like '2:A 4:q 3,6-8:_'
    Returns a dict mapping task numbers to priorities.
    '_' is converted to ' ' (blank/space priority).
    """
    priority_map = {}
    parts = input_str.split()

    for part in parts:
        if ':' not in part:
            continue

        numbers_part, priority = part.rsplit(':', 1)

        # Convert _ to space
        if priority == '_':
            priority = ' '

        # Parse the numbers part (can be single number, comma-separated, or ranges)
        number_tokens = numbers_part.replace(',', ' ').split()
        for token in number_tokens:
            if '-' in token:
                # Range like 6-8
                try:
                    start, end = token.split('-')
                    if start.isdigit() and end.isdigit():
                        for i in range(int(start), int(end) + 1):
                            priority_map[i] = priority
                except ValueError:
                    pass
            elif token.isdigit():
                # Single number
                priority_map[int(token)] = priority

    return priority_map


def parse_append_commands(input_str: str) -> Dict[int, List[str]]:
    """
    Parse append commands like 'a:@context a:#tag a:someText a:"some more text"'
    Returns a dict mapping task numbers to list of texts to append.
    Supports quoted strings for multi-word text.
    """
    appends = {}

    # Use regex to handle quoted strings
    # Match patterns like: NUMBER:a:"text" or NUMBER:a:text or a:"text" or a:text
    # For the simple case where task number is implicit (just 'a:text'), we'll use 0 as a marker

    i = 0
    while i < len(input_str):
        # Skip whitespace
        while i < len(input_str) and input_str[i].isspace():
            i += 1

        if i >= len(input_str):
            break

        # Try to match NUMBER:a: or just a:
        task_num = None
        if i < len(input_str) and input_str[i].isdigit():
            # Parse task number
            num_str = ''
            while i < len(input_str) and input_str[i].isdigit():
                num_str += input_str[i]
                i += 1

            # Expect :a:
            if i + 2 < len(input_str) and input_str[i:i+3] == ':a:':
                task_num = int(num_str)
                i += 3
            else:
                # Not an append command, skip this token
                while i < len(input_str) and not input_str[i].isspace():
                    i += 1
                continue
        elif i + 1 < len(input_str) and input_str[i:i+2] == 'a:':
            # Default task number (we'll handle this differently - apply to last mentioned or error)
            # For now, skip commands without explicit task numbers
            i += 2
        else:
            # Not an append command, skip this token
            while i < len(input_str) and not input_str[i].isspace():
                i += 1
            continue

        # Now parse the text to append
        text_to_append = ''
        if i < len(input_str) and input_str[i] == '"':
            # Quoted string
            i += 1  # Skip opening quote
            while i < len(input_str) and input_str[i] != '"':
                text_to_append += input_str[i]
                i += 1
            if i < len(input_str):
                i += 1  # Skip closing quote
        else:
            # Unquoted text until next space
            while i < len(input_str) and not input_str[i].isspace():
                text_to_append += input_str[i]
                i += 1

        # Add to appends dict
        if task_num is not None and text_to_append:
            if task_num not in appends:
                appends[task_num] = []
            appends[task_num].append(text_to_append)

    return appends


@app.command()
def edit():
    """
    Interactively edit the priority of tasks (same filter as 'list').

    Allows editing priorities, appending text, deleting tasks, and jumping to tasks in $EDITOR.
    Use syntax like: 1:A 3-5:q go:2 1:a:@context 2:a:"some text" 3:DEL
    Use '_' for blank priority, Enter to quit.
    """
    last_input = "q"
    while True:
        all_todos = get_all_todos()
        # Use the same priority set as list command
        active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
        priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, '?': 9}

        table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Tasks to Edit")
        console.print(table)

        try:
            input_str = typer.prompt("\nEnter edits (e.g., '1:A 3-5:q go:2 1:a:@context 2:a:\"some text\" 3:DEL'), or 'q' to quit", default=last_input)

            # Empty input or 'q' means quit
            if not input_str.strip() or input_str.lower() == 'q':
                break

            # Parse input for priority changes, go commands, append commands, and delete commands
            go_numbers = []
            priority_changes = {}
            append_commands = parse_append_commands(input_str)
            delete_numbers = set()

            parts = input_str.split()
            for part in parts:
                if part.lower().startswith('go:'):
                    # Extract number after 'go:'
                    try:
                        go_num = int(part.split(':', 1)[1])
                        go_numbers.append(go_num)
                    except (ValueError, IndexError):
                        console.print(f"[yellow]Invalid go command: {part}[/yellow]")
                elif ':a:' in part:
                    # Skip append commands, already parsed
                    continue
                elif ':' in part:
                    numbers_part, command_part = part.rsplit(':', 1)

                    # Check for delete command
                    if command_part.lower() == 'del':
                        # Parse numbers (can be ranges or comma-separated)
                        number_tokens = numbers_part.replace(',', ' ').split()
                        for token in number_tokens:
                            if '-' in token:
                                try:
                                    start, end = token.split('-')
                                    if start.isdigit() and end.isdigit():
                                        for i in range(int(start), int(end) + 1):
                                            delete_numbers.add(i)
                                except ValueError:
                                    pass
                            elif token.isdigit():
                                delete_numbers.add(int(token))
                        continue

                    # Check if this looks like a range/number trying to use 'go' as priority
                    if command_part.lower() == 'go':
                        console.print(f"[red]ERROR: Invalid syntax '{part}'. Use 'go:NUMBER' instead of 'NUMBER:go'[/red]")
                        console.print("[yellow]Example: go:3 (not 3:go)[/yellow]")
                        continue

                    # Parse priority change
                    priority_part = command_part
                    if priority_part == '_':
                        priority_part = ' '

                    # Parse numbers (can be ranges or comma-separated)
                    number_tokens = numbers_part.replace(',', ' ').split()
                    for token in number_tokens:
                        if '-' in token:
                            try:
                                start, end = token.split('-')
                                if start.isdigit() and end.isdigit():
                                    for i in range(int(start), int(end) + 1):
                                        priority_changes[i] = priority_part
                            except ValueError:
                                pass
                        elif token.isdigit():
                            priority_changes[int(token)] = priority_part

            # Check for multiple go commands
            if len(go_numbers) > 1:
                console.print(f"[red]ERROR: Only one 'go:' command allowed per line. Found {len(go_numbers)}: go:{', go:'.join(map(str, go_numbers))}[/red]")
                last_input = input_str  # Remember for next iteration
                continue

            # Check for conflicting commands on same task numbers
            conflicts = []

            # Check priority changes vs deletes
            priority_set = set(priority_changes.keys())
            delete_set = set(delete_numbers)
            priority_delete_conflict = priority_set & delete_set
            if priority_delete_conflict:
                conflicts.extend([f"{n}:priority+delete" for n in sorted(priority_delete_conflict)])

            # Check append vs deletes
            append_set = set(append_commands.keys())
            append_delete_conflict = append_set & delete_set
            if append_delete_conflict:
                conflicts.extend([f"{n}:append+delete" for n in sorted(append_delete_conflict)])

            if conflicts:
                console.print(f"[red]ERROR: Conflicting commands on same task(s): {', '.join(conflicts)}[/red]")
                console.print("[yellow]A task cannot have multiple operations (priority/append/delete) in the same command.[/yellow]")
                last_input = input_str  # Remember for next iteration
                continue

            # Commands are valid, reset default for next iteration
            last_input = "q"

            # Apply priority changes FIRST
            if priority_changes:
                changed = False
                for task_num, new_priority in sorted(priority_changes.items()):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        if update_task_in_file(task, new_priority):
                            changed = True
                            priority_display = new_priority if new_priority.strip() else '(blank)'
                            console.print(f"  ✓ [dim]{task.text.strip()}[/dim] -> [bold]{priority_display}[/bold]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply append commands SECOND
            if append_commands:
                changed = False
                for task_num, texts in sorted(append_commands.items()):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        for text in texts:
                            if append_to_todo_line(task, text):
                                changed = True
                                console.print(f"  ✓ [dim]{task.text.strip()}[/dim] + [green]{text}[/green]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply delete commands THIRD
            if delete_numbers:
                todos_to_delete = []
                for task_num in sorted(delete_numbers):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        todos_to_delete.append(task)
                        console.print(f"  ✗ [red]Deleted:[/red] [dim strike]{task.text.strip()}[/dim strike]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if todos_to_delete:
                    delete_todo_lines(todos_to_delete)
                    regenerate_tasks_md()
                    # Refresh the display after deletions
                    continue

            # Handle go command AFTER priority changes, appends, and deletes
            if go_numbers:
                go_num = go_numbers[0]
                if 1 <= go_num <= len(all_tasks):
                    task = all_tasks[go_num - 1]
                    editor = os.environ.get('EDITOR', 'vi')
                    editor_line = task.line_number + 1

                    try:
                        subprocess.run([editor, f"+{editor_line}", task.source_file])
                        console.print(f"[green]✓ Opened {task.source_file}:{editor_line}[/green]")
                        # After editing, refresh the display by continuing the loop
                        continue
                    except Exception as e:
                        console.print(f"[red]Error opening editor:[/red] {e}")
                else:
                    console.print(f"[yellow]Invalid task number for go: {go_num}[/yellow]")

        except typer.Abort:
            break

    console.print("Finished editing.")


@app.command()
def editall():
    """
    Interactively edit the priority of all tasks.

    Allows editing priorities, appending text, deleting tasks, and jumping to tasks in $EDITOR.
    Use syntax like: 1:A 3-5:q go:2 1:a:@context 2:a:"some text" 3:DEL
    Use '_' for blank priority, Enter to quit.
    """
    last_input = "q"
    while True:
        all_todos = get_all_todos()
        # Use the same priority set as done command
        active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?', 'w', 't'}
        priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, 'w': 9, 't': 10, '?': 11}

        table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Tasks to Edit")
        console.print(table)

        try:
            input_str = typer.prompt("\nEnter edits (e.g., '1:A 3-5:q go:2 1:a:@context 2:a:\"some text\" 3:DEL'), or 'q' to quit", default=last_input)

            # Empty input or 'q' means quit
            if not input_str.strip() or input_str.lower() == 'q':
                break

            # Parse input for priority changes, go commands, append commands, and delete commands
            go_numbers = []
            priority_changes = {}
            append_commands = parse_append_commands(input_str)
            delete_numbers = set()

            parts = input_str.split()
            for part in parts:
                if part.lower().startswith('go:'):
                    # Extract number after 'go:'
                    try:
                        go_num = int(part.split(':', 1)[1])
                        go_numbers.append(go_num)
                    except (ValueError, IndexError):
                        console.print(f"[yellow]Invalid go command: {part}[/yellow]")
                elif ':a:' in part:
                    # Skip append commands, already parsed
                    continue
                elif ':' in part:
                    numbers_part, command_part = part.rsplit(':', 1)

                    # Check for delete command
                    if command_part.lower() == 'del':
                        # Parse numbers (can be ranges or comma-separated)
                        number_tokens = numbers_part.replace(',', ' ').split()
                        for token in number_tokens:
                            if '-' in token:
                                try:
                                    start, end = token.split('-')
                                    if start.isdigit() and end.isdigit():
                                        for i in range(int(start), int(end) + 1):
                                            delete_numbers.add(i)
                                except ValueError:
                                    pass
                            elif token.isdigit():
                                delete_numbers.add(int(token))
                        continue

                    # Check if this looks like a range/number trying to use 'go' as priority
                    if command_part.lower() == 'go':
                        console.print(f"[red]ERROR: Invalid syntax '{part}'. Use 'go:NUMBER' instead of 'NUMBER:go'[/red]")
                        console.print("[yellow]Example: go:3 (not 3:go)[/yellow]")
                        continue

                    # Parse priority change
                    priority_part = command_part
                    if priority_part == '_':
                        priority_part = ' '

                    # Parse numbers (can be ranges or comma-separated)
                    number_tokens = numbers_part.replace(',', ' ').split()
                    for token in number_tokens:
                        if '-' in token:
                            try:
                                start, end = token.split('-')
                                if start.isdigit() and end.isdigit():
                                    for i in range(int(start), int(end) + 1):
                                        priority_changes[i] = priority_part
                            except ValueError:
                                pass
                        elif token.isdigit():
                            priority_changes[int(token)] = priority_part

            # Check for multiple go commands
            if len(go_numbers) > 1:
                console.print(f"[red]ERROR: Only one 'go:' command allowed per line. Found {len(go_numbers)}: go:{', go:'.join(map(str, go_numbers))}[/red]")
                last_input = input_str  # Remember for next iteration
                continue

            # Check for conflicting commands on same task numbers
            conflicts = []

            # Check priority changes vs deletes
            priority_set = set(priority_changes.keys())
            delete_set = set(delete_numbers)
            priority_delete_conflict = priority_set & delete_set
            if priority_delete_conflict:
                conflicts.extend([f"{n}:priority+delete" for n in sorted(priority_delete_conflict)])

            # Check append vs deletes
            append_set = set(append_commands.keys())
            append_delete_conflict = append_set & delete_set
            if append_delete_conflict:
                conflicts.extend([f"{n}:append+delete" for n in sorted(append_delete_conflict)])

            if conflicts:
                console.print(f"[red]ERROR: Conflicting commands on same task(s): {', '.join(conflicts)}[/red]")
                console.print("[yellow]A task cannot have multiple operations (priority/append/delete) in the same command.[/yellow]")
                last_input = input_str  # Remember for next iteration
                continue

            # Commands are valid, reset default for next iteration
            last_input = "q"

            # Apply priority changes FIRST
            if priority_changes:
                changed = False
                for task_num, new_priority in sorted(priority_changes.items()):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        if update_task_in_file(task, new_priority):
                            changed = True
                            priority_display = new_priority if new_priority.strip() else '(blank)'
                            console.print(f"  ✓ [dim]{task.text.strip()}[/dim] -> [bold]{priority_display}[/bold]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply append commands SECOND
            if append_commands:
                changed = False
                for task_num, texts in sorted(append_commands.items()):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        for text in texts:
                            if append_to_todo_line(task, text):
                                changed = True
                                console.print(f"  ✓ [dim]{task.text.strip()}[/dim] + [green]{text}[/green]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply delete commands THIRD
            if delete_numbers:
                todos_to_delete = []
                for task_num in sorted(delete_numbers):
                    if 1 <= task_num <= len(all_tasks):
                        task = all_tasks[task_num - 1]
                        todos_to_delete.append(task)
                        console.print(f"  ✗ [red]Deleted:[/red] [dim strike]{task.text.strip()}[/dim strike]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if todos_to_delete:
                    delete_todo_lines(todos_to_delete)
                    regenerate_tasks_md()
                    # Refresh the display after deletions
                    continue

            # Handle go command AFTER priority changes, appends, and deletes
            if go_numbers:
                go_num = go_numbers[0]
                if 1 <= go_num <= len(all_tasks):
                    task = all_tasks[go_num - 1]
                    editor = os.environ.get('EDITOR', 'vi')
                    editor_line = task.line_number + 1

                    try:
                        subprocess.run([editor, f"+{editor_line}", task.source_file])
                        console.print(f"[green]✓ Opened {task.source_file}:{editor_line}[/green]")
                        # After editing, refresh the display by continuing the loop
                        continue
                    except Exception as e:
                        console.print(f"[red]Error opening editor:[/red] {e}")
                else:
                    console.print(f"[yellow]Invalid task number for go: {go_num}[/yellow]")

        except typer.Abort:
            break

    console.print("Finished editing.")


@app.command()
def status():
    """
    Show all projects and parent tasks with their next actions.

    Allows editing priorities, appending text, deleting tasks, and jumping to tasks in $EDITOR.
    Use syntax like: 1:A 3-5:q go:2 1:a:@context 2:a:"some text" 3:DEL
    Use '_' for blank priority, Enter to quit.
    """
    last_input = "q"
    while True:
        # Get all todos
        all_todos = get_all_todos()
        projects = get_all_projects()
        oneoff_todos = get_todos_from_file(ONEOFFS_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f), ONEOFFS_FILE)
        tag_todos = get_todos_from_file(TAGS_FILE, parsing.parse_tags_file, TAGS_FILE)

        # Build flat list of items to display with line numbers
        display_items = []  # List of (display_text, todo_object, is_no_action)

        def has_active_children(todo):
            """Check if a todo has any non-completed/cancelled children."""
            return any(not (st.is_completed or st.is_cancelled) for st in todo.subtasks)

        def get_first_level_active_children(todo):
            """Get first level of active children (not completed/cancelled)."""
            children = []
            for st in todo.subtasks:
                if not (st.is_completed or st.is_cancelled):
                    # Check if this child has a priority or has its own children
                    has_priority = st.priority and st.priority.strip() and st.priority not in ['x', '-']
                    has_children = has_active_children(st)
                    if has_priority or has_children:
                        children.append(st)
            return children

        def format_todo_for_status(todo, indent=0):
            """Format a todo line for status display."""
            indent_str = "  " * indent
            formatted = rendering.format_line(todo)
            return Text(indent_str) + formatted

        # Process projects from projects.md
        for project in projects:
            if isinstance(project, Project):
                # Add project header
                project_header = Text(project.text, style="bold bright_yellow")
                has_actions = False

                # Collect project children to display
                project_children = []
                first_blank_priority_task = None

                for task in project.subtasks:
                    if task.is_completed or task.is_cancelled:
                        continue

                    # Check if this task has a priority or has active children
                    has_priority = task.priority and task.priority.strip() and task.priority not in ['x', '-']
                    has_children = has_active_children(task)

                    if has_priority or has_children:
                        has_actions = True
                        project_children.append(task)
                    elif first_blank_priority_task is None and (not task.priority or task.priority.strip() == ''):
                        # Remember the first blank priority task
                        first_blank_priority_task = task

                # Add to display
                if has_actions:
                    display_items.append((project_header, project, False))
                    for child in project_children:
                        display_items.append((format_todo_for_status(child, 1), child, False))
                        # Add one level of children
                        for subchild in get_first_level_active_children(child):
                            display_items.append((format_todo_for_status(subchild, 2), subchild, False))
                elif first_blank_priority_task:
                    # Show the first blank priority task instead of "no next action"
                    display_items.append((project_header, project, False))
                    display_items.append((format_todo_for_status(first_blank_priority_task, 1), first_blank_priority_task, False))
                else:
                    # Truly no tasks at all
                    display_items.append((project_header, project, False))
                    no_action_text = Text("  no next action", style="black on red")
                    display_items.append((no_action_text, project, True))

        # Process oneoffs
        oneoff_parents = []
        for todo in oneoff_todos:
            if todo.level == 0 and not (todo.is_completed or todo.is_cancelled):
                has_priority = todo.priority and todo.priority.strip() and todo.priority not in ['x', '-']
                has_children = has_active_children(todo)
                if has_priority or has_children:
                    oneoff_parents.append(todo)

        if oneoff_parents:
            # Create a jumpable header for oneoffs.md pointing to line 0
            oneoffs_header_todo = Todo(
                text="oneoffs.md",
                priority=' ',
                source_file=ONEOFFS_FILE,
                line_number=0,
                raw_text="",
                level=0
            )
            display_items.append((Text("oneoffs.md:", style="bold"), oneoffs_header_todo, False))
            for todo in oneoff_parents:
                display_items.append((format_todo_for_status(todo, 1), todo, False))
                for child in get_first_level_active_children(todo):
                    display_items.append((format_todo_for_status(child, 2), child, False))

        # Process tags - group by tag and find tag header line numbers
        tags_dict = {}  # tag_name -> list of todos
        tag_header_lines = {}  # tag_name -> line_number

        # Read tags file to find tag section header line numbers
        try:
            with open(TAGS_FILE, 'r') as f:
                for i, line in enumerate(f):
                    header_match = re.match(r'^\#\#\s+\#(\w+)', line)
                    if header_match:
                        tag_name = header_match.group(1)
                        tag_header_lines[tag_name] = i
        except FileNotFoundError:
            pass

        for todo in tag_todos:
            if todo.level == 0 and not (todo.is_completed or todo.is_cancelled):
                has_priority = todo.priority and todo.priority.strip() and todo.priority not in ['x', '-']
                has_children = has_active_children(todo)
                if has_priority or has_children:
                    for tag in todo.tags:
                        if tag.name not in tags_dict:
                            tags_dict[tag.name] = []
                        tags_dict[tag.name].append(todo)

        for tag_name in sorted(tags_dict.keys()):
            # Create a jumpable header for the tag section
            tag_line_number = tag_header_lines.get(tag_name, 0)
            tag_header_todo = Todo(
                text=f"#{tag_name}",
                priority=' ',
                source_file=TAGS_FILE,
                line_number=tag_line_number,
                raw_text="",
                level=0
            )
            display_items.append((Text(f"#{tag_name}:", style="bold"), tag_header_todo, False))
            for todo in tags_dict[tag_name]:
                display_items.append((format_todo_for_status(todo, 1), todo, False))
                for child in get_first_level_active_children(todo):
                    display_items.append((format_todo_for_status(child, 2), child, False))

        # Display with line numbers
        console.print("\n" + "═" * 60)
        console.print("[bold]PROJECT STATUS[/bold]")
        console.print("─" * 60 + "\n")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("#", style="bold cyan", no_wrap=True)
        table.add_column("Item")

        # Only number items that have todo objects
        numbered_items = []
        for display_text, todo_obj, is_no_action in display_items:
            if todo_obj is not None:
                numbered_items.append(todo_obj)
                line_num = str(len(numbered_items))
                table.add_row(line_num, display_text)
            else:
                table.add_row("", display_text)

        console.print(table)

        # Interactive prompt
        try:
            input_str = typer.prompt("\nEnter edits (e.g., '1:A 3-5:q go:2 1:a:@context 2:a:\"some text\" 3:DEL'), or 'q' to quit", default=last_input)

            # Empty input or 'q' means quit
            if not input_str.strip() or input_str.lower() == 'q':
                break

            # Parse input for priority changes, go commands, append commands, and delete commands
            go_numbers = []
            priority_changes = {}
            append_commands = parse_append_commands(input_str)
            delete_numbers = set()

            parts = input_str.split()
            for part in parts:
                if part.lower().startswith('go:'):
                    # Extract number after 'go:'
                    try:
                        go_num = int(part.split(':', 1)[1])
                        go_numbers.append(go_num)
                    except (ValueError, IndexError):
                        console.print(f"[yellow]Invalid go command: {part}[/yellow]")
                elif ':a:' in part:
                    # Skip append commands, already parsed
                    continue
                elif ':' in part:
                    numbers_part, command_part = part.rsplit(':', 1)

                    # Check for delete command
                    if command_part.lower() == 'del':
                        # Parse numbers (can be ranges or comma-separated)
                        number_tokens = numbers_part.replace(',', ' ').split()
                        for token in number_tokens:
                            if '-' in token:
                                try:
                                    start, end = token.split('-')
                                    if start.isdigit() and end.isdigit():
                                        for i in range(int(start), int(end) + 1):
                                            delete_numbers.add(i)
                                except ValueError:
                                    pass
                            elif token.isdigit():
                                delete_numbers.add(int(token))
                        continue

                    # Check if this looks like a range/number trying to use 'go' as priority
                    if command_part.lower() == 'go':
                        console.print(f"[red]ERROR: Invalid syntax '{part}'. Use 'go:NUMBER' instead of 'NUMBER:go'[/red]")
                        console.print("[yellow]Example: go:3 (not 3:go)[/yellow]")
                        continue

                    # Parse priority change
                    priority_part = command_part
                    if priority_part == '_':
                        priority_part = ' '

                    # Parse numbers (can be ranges or comma-separated)
                    number_tokens = numbers_part.replace(',', ' ').split()
                    for token in number_tokens:
                        if '-' in token:
                            try:
                                start, end = token.split('-')
                                if start.isdigit() and end.isdigit():
                                    for i in range(int(start), int(end) + 1):
                                        priority_changes[i] = priority_part
                            except ValueError:
                                pass
                        elif token.isdigit():
                            priority_changes[int(token)] = priority_part

            # Check for multiple go commands
            if len(go_numbers) > 1:
                console.print(f"[red]ERROR: Only one 'go:' command allowed per line. Found {len(go_numbers)}: go:{', go:'.join(map(str, go_numbers))}[/red]")
                last_input = input_str  # Remember for next iteration
                continue

            # Check for conflicting commands on same task numbers
            conflicts = []

            # Check priority changes vs deletes
            priority_set = set(priority_changes.keys())
            delete_set = set(delete_numbers)
            priority_delete_conflict = priority_set & delete_set
            if priority_delete_conflict:
                conflicts.extend([f"{n}:priority+delete" for n in sorted(priority_delete_conflict)])

            # Check append vs deletes
            append_set = set(append_commands.keys())
            append_delete_conflict = append_set & delete_set
            if append_delete_conflict:
                conflicts.extend([f"{n}:append+delete" for n in sorted(append_delete_conflict)])

            if conflicts:
                console.print(f"[red]ERROR: Conflicting commands on same task(s): {', '.join(conflicts)}[/red]")
                console.print("[yellow]A task cannot have multiple operations (priority/append/delete) in the same command.[/yellow]")
                last_input = input_str  # Remember for next iteration
                continue

            # Commands are valid, reset default for next iteration
            last_input = "q"

            # Apply priority changes FIRST
            if priority_changes:
                changed = False
                for task_num, new_priority in sorted(priority_changes.items()):
                    if 1 <= task_num <= len(numbered_items):
                        task = numbered_items[task_num - 1]
                        if update_task_in_file(task, new_priority):
                            changed = True
                            priority_display = new_priority if new_priority.strip() else '(blank)'
                            console.print(f"  ✓ [dim]{task.text.strip()}[/dim] -> [bold]{priority_display}[/bold]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply append commands SECOND
            if append_commands:
                changed = False
                for task_num, texts in sorted(append_commands.items()):
                    if 1 <= task_num <= len(numbered_items):
                        task = numbered_items[task_num - 1]
                        for text in texts:
                            if append_to_todo_line(task, text):
                                changed = True
                                console.print(f"  ✓ [dim]{task.text.strip()}[/dim] + [green]{text}[/green]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if changed:
                    regenerate_tasks_md()

            # Apply delete commands THIRD
            if delete_numbers:
                todos_to_delete = []
                for task_num in sorted(delete_numbers):
                    if 1 <= task_num <= len(numbered_items):
                        task = numbered_items[task_num - 1]
                        todos_to_delete.append(task)
                        console.print(f"  ✗ [red]Deleted:[/red] [dim strike]{task.text.strip()}[/dim strike]")
                    else:
                        console.print(f"[yellow]Invalid task number: {task_num}[/yellow]")

                if todos_to_delete:
                    delete_todo_lines(todos_to_delete)
                    regenerate_tasks_md()
                    # Refresh the display after deletions
                    continue

            # Handle go command AFTER priority changes, appends, and deletes
            if go_numbers:
                go_num = go_numbers[0]
                if 1 <= go_num <= len(numbered_items):
                    task = numbered_items[go_num - 1]
                    editor = os.environ.get('EDITOR', 'vi')
                    editor_line = task.line_number + 1

                    try:
                        subprocess.run([editor, f"+{editor_line}", task.source_file])
                        console.print(f"[green]✓ Opened {task.source_file}:{editor_line}[/green]")
                        # After editing, refresh the display by continuing the loop
                        continue
                    except Exception as e:
                        console.print(f"[red]Error opening editor:[/red] {e}")
                else:
                    console.print(f"[yellow]Invalid task number for go: {go_num}[/yellow]")

        except typer.Abort:
            break

    console.print("Finished.")


@app.command()
def go():
    """
    Interactively open tasks in $EDITOR to edit the text (same filter as 'list').
    """
    # Display tasks once at the beginning
    all_todos = get_all_todos()
    # Use the same priority set as list command
    active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
    priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, '?': 9}

    table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Tasks to Edit")
    console.print(table)

    # Get editor from environment
    editor = os.environ.get('EDITOR', 'vi')

    while True:
        try:
            index_str = typer.prompt("\nEnter task number to edit, or 'q' to quit")
            if index_str.lower() == 'q':
                break

            # Parse single task number
            try:
                task_num = int(index_str)
                if not (1 <= task_num <= len(all_tasks)):
                    console.print(f"[yellow]Invalid task number. Please enter 1-{len(all_tasks)}[/yellow]")
                    continue
            except ValueError:
                console.print("[yellow]Please enter a valid number or 'q' to quit[/yellow]")
                continue

            task = all_tasks[task_num - 1]

            # Open editor at the task's line
            # +1 because editors are 1-indexed while line_number is 0-indexed
            editor_line = task.line_number + 1

            # Try different editor syntaxes
            try:
                # Most editors (vim, nano, emacs, etc.) support +LINE syntax
                subprocess.run([editor, f"+{editor_line}", task.source_file])
                console.print(f"[green]✓ Edited task in {task.source_file}:{editor_line}[/green]")
            except Exception as e:
                console.print(f"[red]Error opening editor:[/red] {e}")

        except typer.Abort:
            break

    console.print("Finished editing.")


@app.command()
def goall():
    """
    Interactively open tasks in $EDITOR to edit the text (all tasks).
    """
    # Display tasks once at the beginning
    all_todos = get_all_todos()
    active_priorities = {'!', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?', 'w', 't'}
    priority_map = {'!': 0, 'q': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7, 'i': 8, 'w': 9, 't': 10, '?': 11}

    table, all_tasks = build_grouped_task_table(all_todos, active_priorities, priority_map, "Tasks to Edit")
    console.print(table)

    # Get editor from environment
    editor = os.environ.get('EDITOR', 'vi')

    while True:
        try:
            index_str = typer.prompt("\nEnter task number to edit, or 'q' to quit")
            if index_str.lower() == 'q':
                break

            # Parse single task number
            try:
                task_num = int(index_str)
                if not (1 <= task_num <= len(all_tasks)):
                    console.print(f"[yellow]Invalid task number. Please enter 1-{len(all_tasks)}[/yellow]")
                    continue
            except ValueError:
                console.print("[yellow]Please enter a valid number or 'q' to quit[/yellow]")
                continue

            task = all_tasks[task_num - 1]

            # Open editor at the task's line
            # +1 because editors are 1-indexed while line_number is 0-indexed
            editor_line = task.line_number + 1

            # Try different editor syntaxes
            try:
                # Most editors (vim, nano, emacs, etc.) support +LINE syntax
                subprocess.run([editor, f"+{editor_line}", task.source_file])
                console.print(f"[green]✓ Edited task in {task.source_file}:{editor_line}[/green]")
            except Exception as e:
                console.print(f"[red]Error opening editor:[/red] {e}")

        except typer.Abort:
            break

    console.print("Finished editing.")


@app.command()
def inbox():
    """
    Interactively process tasks from the inbox.
    """
    # 1. Get existing data for choices
    all_todos = get_all_todos()
    projects = sorted([p.text.replace('+', '') for p in get_all_projects()])
    tags = sorted({tag.name for todo in all_todos for tag in todo.tags})
    contexts = sorted({context.name for todo in all_todos for context in todo.contexts})

    try:
        with open(INBOX_FILE, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        console.print("[yellow]Inbox file not found.[/yellow]")
        raise typer.Exit()

    if not lines:
        console.print("[green]Inbox is empty![/green]")
        raise typer.Exit()

    remaining_lines = list(lines)
    processed_something = False

    i = 0
    while i < len(remaining_lines):
        line = remaining_lines[i]
        task_text = re.sub(r'^\s*-\s*\[.?\]\s*', '', line).strip()

        console.clear()
        console.print(f"Processing inbox item {i+1} of {len(lines)} ({len(remaining_lines)} remaining):")
        console.print(Panel(f"[cyan]'{task_text}'[/cyan]", title="Task", border_style="blue"))

        # 2. Priority Prompt
        print_inbox_prompt(console)
        action = typer.prompt("> ", default="skip").lower()

        if action == 'copy':
            # Pipe current task to wl-copy
            try:
                subprocess.run(['wl-copy'], input=task_text.encode(), check=True)
                console.print(f"[green]✓ Copied to clipboard:[/green] [cyan]{task_text}[/cyan]")
                time.sleep(0.8)
            except subprocess.CalledProcessError:
                console.print("[red]Failed to copy to clipboard[/red]")
                time.sleep(1)
            except FileNotFoundError:
                console.print("[red]wl-copy not found. Is wl-clipboard installed?[/red]")
                time.sleep(1)
            i += 1
            continue
        if action == 'quit': break
        if action in ('skip', 'i'): i += 1; continue
        if action == 'del':
            if typer.confirm(f"Really delete '[s]{task_text}[/s]'?"):
                remaining_lines.pop(i)
                processed_something = True
            else:
                i += 1 # Only advance if we don't delete
            continue
        if action == 'edit':
            new_text = typer.prompt("Edit task", default=task_text)
            remaining_lines[i] = line.replace(task_text, new_text)
            continue

        # Handle special file-moving priorities
        if action in ('s', 't'):
            destination_file = SOMEDAY_FILE if action == 's' else TOMORROW_FILE
            final_line = f"- [{action}] {task_text}"
            append_to_file(destination_file, final_line)
            console.print(f"✓ Moved to [green]{os.path.basename(destination_file)}[/green]")
            remaining_lines.pop(i)
            processed_something = True
            continue

        # Handle regular priorities that continue to project/tag prompts
        VALID_PRIORITIES = 'abcdfg!qwi?_'
        chosen_priority = ' '
        if action == '_':
            chosen_priority = ' '
        elif action == '!':
            chosen_priority = '!'
        elif action in VALID_PRIORITIES:
            chosen_priority = action.upper() if action in 'abcdfg' else action
        
        # 3. Project, Tag, Context Prompts
        chosen_project = choose_item("Project", projects, allow_new=True)
        chosen_tag = choose_item("Tag", tags, allow_new=True)
        chosen_contexts = choose_item("Context", contexts, allow_new=True, multi=True)

        # 4. Construct new task line
        final_text = task_text
        if chosen_project: final_text += f" +{chosen_project}"
        if chosen_tag: final_text += f" #{chosen_tag}"
        if chosen_contexts: final_text += " " + " ".join([f"@{c}" for c in chosen_contexts])
        
        final_line = f"- [{chosen_priority}] {final_text}"

        # 5. Determine destination and write
        destination_file = ONEOFFS_FILE
        destination_header = None
        if chosen_project:
            destination_file = PROJECTS_FILE
            destination_header = f"## +{chosen_project}"
        elif chosen_tag:
            destination_file = TAGS_FILE
            destination_header = f"## #{chosen_tag}"

        append_to_file(destination_file, final_line, destination_header)
        console.print(f"✓ Moved to [green]{os.path.basename(destination_file)}[/green]")
        
        remaining_lines.pop(i)
        processed_something = True
    
    # 6. Write back remaining lines
    with open(INBOX_FILE, "w") as f:
        if remaining_lines:
            f.write("\n".join(remaining_lines))
            f.write("\n")

    if processed_something:
        console.print("\n[bold green]Inbox processing complete![/bold green]")
        regenerate_tasks_md()
    else:
        console.print("\nNo changes made.")

def print_inbox_prompt(console: Console):
    """Prints the structured prompt for the inbox command."""

    priorities = {
        'A': "High", 'B': "Medium", 'C': "Low", 'E': "E", 'F': "F",
        'q': "Quick", 't': "Tomorrow", 'i': "In Progress", 'w': "Waiting",
        '?': "Maybe", 's': "Someday", '!': "Emergency", '_': "Blank"
    }
    
    actions = {
        'copy': "Copy to clipboard",
        'skip': "Keep in inbox",
        'del': "Delete task",
        'edit': "Edit text",
        'quit': "Save & Quit"
    }

    priority_items = [Text.assemble(Text(f"{key}", style="yellow"), Text(f"({desc})")) for key, desc in priorities.items()]
    action_items = [Text.assemble(Text(f"{key}", style="yellow"), Text(f"({desc})")) for key, desc in actions.items()]

    console.print(Panel(Columns(priority_items, equal=True, column_first=True), title="[bold]Set Priority[/bold]", border_style="green"))
    console.print(Panel(Columns(action_items, equal=True, column_first=True), title="[bold]Actions[/bold]", border_style="red"))


def choose_item(name: str, items: List[str], allow_new: bool, multi: bool = False) -> Optional[Union[str, List[str]]]:
    console.print(f"\n--- Choose {name} ---")
    for i, item in enumerate(items, 1):
        console.print(f"  [cyan]{i}[/cyan]: {item}")
    
    prompt = f"Choose {'numbers' if multi else 'number'}"
    if allow_new: prompt += ", 'n' for new, or press Enter to skip"
    
    choice_str = typer.prompt(prompt, default="")
    if not choice_str: return [] if multi else None

    if choice_str.lower() == 'n' and allow_new:
        new_item = typer.prompt(f"Enter new {name} name")
        return [new_item] if multi else new_item

    if multi:
        try:
            indices = [int(i) - 1 for i in choice_str.split()]
            return [items[i] for i in indices if 0 <= i < len(items)]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            return []
    else:
        try:
            index = int(choice_str) - 1
            if 0 <= index < len(items):
                return items[index]
            else:
                console.print("[red]Invalid selection.[/red]")
                return None
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
            return None

def append_to_file(file_path: str, line_to_add: str, header: Optional[str] = None):
    try:
        with open(file_path, "r+") as f:
            content = f.read()
            lines = content.splitlines()
            
            if header:
                try:
                    header_index = -1
                    # Find header, ignoring case and extra whitespace
                    for i, line in enumerate(lines):
                        if line.strip().lower() == header.strip().lower():
                            header_index = i
                            break
                    if header_index == -1: raise ValueError("Header not found")

                    # Find the end of the section
                    next_header_index = len(lines)
                    for i in range(header_index + 1, len(lines)):
                        if lines[i].strip().startswith("## "):
                            next_header_index = i
                            break
                    
                    # Insert before the next header, or at the end
                    lines.insert(next_header_index, line_to_add)

                except ValueError: # Header not found, so add it
                    if lines and lines[-1].strip() != "": lines.append("")
                    lines.append(header)
                    lines.append(line_to_add)
            else: # No header, just append
                if not content.endswith("\n"):
                    line_to_add = "\n" + line_to_add
                lines.append(line_to_add)
            
            f.seek(0)
            f.truncate()
            f.write("\n".join(lines))
            if not content.endswith("\n\n"):
                 f.write("\n")


    except FileNotFoundError:
        with open(file_path, "w") as f:
            if header: f.write(f"{header}\n")
            f.write(f"{line_to_add}\n")


def append_to_todo_line(todo: Todo, text: str):
    """Append arbitrary text to a todo's line in its source file."""
    try:
        with open(todo.source_file, "r") as f:
            lines = f.readlines()

        if todo.line_number >= len(lines):
            console.print(f"[yellow]Warning: Line {todo.line_number} out of bounds for task: {todo.text.strip()}[/yellow]")
            return False

        target_line = lines[todo.line_number].rstrip()

        # Append text before newline
        updated_line = f"{target_line} {text}\n"
        lines[todo.line_number] = updated_line

        with open(todo.source_file, "w") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        console.print(f"[bold red]Error appending to task '{todo.text.strip()}':[/bold red] {e}")
        return False


def delete_todo_lines(todos_to_delete: List[Todo]):
    """Delete multiple todo lines from their source files."""
    # Group todos by file
    todos_by_file = defaultdict(list)
    for todo in todos_to_delete:
        todos_by_file[todo.source_file].append(todo)

    for file_path, todos in todos_by_file.items():
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()

            # Sort by line number descending to avoid index shifting
            todos_sorted = sorted(todos, key=lambda t: t.line_number, reverse=True)

            # Delete each line
            for todo in todos_sorted:
                if todo.line_number < len(lines):
                    del lines[todo.line_number]

            with open(file_path, "w") as f:
                f.writelines(lines)

            return True
        except Exception as e:
            console.print(f"[bold red]Error deleting tasks:[/bold red] {e}")
            return False

    return True


def append_tag_to_todo(todo: Todo, tag: str):
    """Append a tag to a todo's line in its source file."""
    try:
        with open(todo.source_file, "r") as f:
            lines = f.readlines()

        if todo.line_number >= len(lines):
            console.print(f"[yellow]Warning: Line {todo.line_number} out of bounds for task: {todo.text.strip()}[/yellow]")
            return False

        target_line = lines[todo.line_number].rstrip()

        # Check if tag already exists
        if tag in target_line:
            return True

        # Append tag before newline
        updated_line = f"{target_line} {tag}\n"
        lines[todo.line_number] = updated_line

        with open(todo.source_file, "w") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        console.print(f"[bold red]Error appending tag to task '{todo.text.strip()}':[/bold red] {e}")
        return False


@app.command()
def jrnl():
    """
    Collects completed and cancelled todos and pipes them to jrnl.

    Includes all completed [x] and cancelled [-] todos, even from incomplete groups.
    Completed/cancelled todos from fully completed groups are deleted after journaling.
    Completed/cancelled todos from incomplete groups are tagged with #jrnld and kept.
    Todos already tagged with #jrnld are skipped.
    """
    def is_group_fully_completed(todo: Todo) -> bool:
        """Check if a todo and all its subtasks are completed or cancelled."""
        if not (todo.is_completed or todo.is_cancelled):
            return False
        if todo.subtasks:
            return all(is_group_fully_completed(st) for st in todo.subtasks)
        return True

    def has_jrnld_tag(todo: Todo) -> bool:
        """Check if a todo has the #jrnld tag."""
        return any(tag.name == 'jrnld' for tag in todo.tags)

    def collect_completed_subtasks(todo: Todo, collected: List[Todo]):
        """Recursively collect all completed and cancelled subtasks."""
        if (todo.is_completed or todo.is_cancelled) and not has_jrnld_tag(todo):
            collected.append(todo)
        for subtask in todo.subtasks:
            collect_completed_subtasks(subtask, collected)

    # Collect completed and cancelled items
    # completed_for_jrnl: todos to write to journal (both [x] and [-])
    # todos_to_delete: fully completed/cancelled groups to delete
    # todos_to_tag: partial group todos to tag with #jrnld
    completed_for_jrnl: List[Todo] = []
    todos_to_delete: Dict[str, List[Todo]] = defaultdict(list)
    todos_to_tag: List[Todo] = []
    processed_raw_texts: Set[str] = set()

    def collect_todo_lines_to_delete(todo: Todo):
        """Recursively collect line numbers for a todo and all its subtasks."""
        todos_to_delete[todo.source_file].append(todo)
        for subtask in todo.subtasks:
            collect_todo_lines_to_delete(subtask)

    # Process projects from projects.md
    projects_list = get_all_projects()
    for project in projects_list:
        if isinstance(project, Project):
            if not project.subtasks:
                continue

            # Check if ALL tasks in the project are fully completed
            all_completed = all(is_group_fully_completed(task) for task in project.subtasks)

            if all_completed:
                # Fully completed project: add all tasks and mark for deletion
                for task in project.subtasks:
                    collect_completed_subtasks(task, completed_for_jrnl)
                    processed_raw_texts.add(task.raw_text)
                    for subtask in task.subtasks:
                        processed_raw_texts.add(subtask.raw_text)
                    collect_todo_lines_to_delete(task)
            else:
                # Partially completed project: add completed tasks and mark for tagging
                for task in project.subtasks:
                    partial_completed: List[Todo] = []
                    collect_completed_subtasks(task, partial_completed)
                    for completed_task in partial_completed:
                        if completed_task.raw_text not in processed_raw_texts:
                            completed_for_jrnl.append(completed_task)
                            todos_to_tag.append(completed_task)
                            processed_raw_texts.add(completed_task.raw_text)

    # Process todos from all other files
    files_to_process = [
        (ONEOFFS_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f)),
        (INBOX_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f)),
        (SOMEDAY_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f)),
        (TOMORROW_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f)),
        (TWOMINUTES_FILE, lambda c, f: parsing.parse_todos_from_lines(list(enumerate(c.splitlines())), f)),
        (TAGS_FILE, parsing.parse_tags_file),
    ]

    for file_path, parser_func in files_to_process:
        todos = get_todos_from_file(file_path, parser_func, file_path)
        for todo in todos:
            if todo.raw_text in processed_raw_texts:
                continue
            if todo.level == 0 and is_group_fully_completed(todo):
                # Fully completed top-level todo
                collect_completed_subtasks(todo, completed_for_jrnl)
                processed_raw_texts.add(todo.raw_text)
                for subtask in todo.subtasks:
                    processed_raw_texts.add(subtask.raw_text)
                collect_todo_lines_to_delete(todo)
            elif todo.level == 0 and todo.subtasks:
                # Partially completed group
                partial_completed: List[Todo] = []
                collect_completed_subtasks(todo, partial_completed)
                for completed_task in partial_completed:
                    if completed_task.raw_text not in processed_raw_texts:
                        completed_for_jrnl.append(completed_task)
                        todos_to_tag.append(completed_task)
                        processed_raw_texts.add(completed_task.raw_text)

    if not completed_for_jrnl:
        console.print("[yellow]No completed or cancelled todos to journal.[/yellow]")
        return

    # Format output
    output_lines = ["Completed and Cancelled Todos", ""]

    def format_task(t: Todo) -> str:
        """Format a task for jrnl output (remove metadata)."""
        match = parsing.TASK_REGEX.match(t.raw_text.strip())
        if match:
            text = match.group(3).strip()
        else:
            text = t.text.strip()

        # Append project name if task has a project and it's not already in the text
        if t.project and t.project.text not in text:
            text += f" {t.project.text}"

        return text

    # Output all completed and cancelled tasks
    for task in completed_for_jrnl:
        formatted_text = format_task(task)
        status = '-' if task.is_cancelled else 'x'
        output_lines.append(f"- [{status}] {formatted_text}")

    output_lines.append("")

    # Join and pipe to jrnl
    output_text = "\n".join(output_lines)

    # Print what will be sent to jrnl
    console.print("[bold cyan]Sending to jrnl:[/bold cyan]")
    console.print("─" * 60)
    # Print raw text to avoid any formatting issues
    print(output_text)
    console.print("─" * 60)

    try:
        # Pipe to jrnl
        result = subprocess.run(
            ["jrnl"],
            input=output_text,
            text=True,
            capture_output=True
        )

        if result.returncode == 0:
            console.print("[green]✓ Completed and cancelled todos sent to jrnl[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Tag todos from incomplete groups with #jrnld
            if todos_to_tag:
                for todo in todos_to_tag:
                    append_tag_to_todo(todo, "#jrnld")
                console.print(f"[cyan]✓ Tagged {len(todos_to_tag)} todo(s) with #jrnld[/cyan]")

            # Delete completed/cancelled todos from fully completed groups
            if todos_to_delete:
                delete_todos_from_files(todos_to_delete)
                console.print("[green]✓ Removed completed/cancelled todos from fully completed groups[/green]")
        else:
            console.print(f"[red]Error piping to jrnl:[/red]")
            if result.stderr:
                console.print(result.stderr)
    except FileNotFoundError:
        console.print("[red]Error: jrnl command not found. Is it installed?[/red]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def delete_todos_from_files(todos_by_file: Dict[str, List[Todo]]):
    """Delete completed todos from their source files."""
    for file_path, todos in todos_by_file.items():
        if not todos:
            continue

        try:
            with open(file_path, "r") as f:
                lines = f.readlines()

            # Sort todos by line number in descending order to delete from bottom to top
            # This prevents line number shifting issues
            todos_sorted = sorted(todos, key=lambda t: t.line_number, reverse=True)

            # Delete each todo line
            for todo in todos_sorted:
                if todo.line_number < len(lines):
                    lines[todo.line_number] = None  # Mark for deletion

            # Remove marked lines and clean up extra blank lines
            new_lines = []
            blank_count = 0
            for line in lines:
                if line is None:
                    continue
                if line.strip() == "":
                    blank_count += 1
                    # Keep max 2 consecutive blank lines
                    if blank_count <= 2:
                        new_lines.append(line)
                else:
                    blank_count = 0
                    new_lines.append(line)

            # Write back to file
            with open(file_path, "w") as f:
                f.writelines(new_lines)

        except Exception as e:
            console.print(f"[yellow]Warning: Could not delete todos from {file_path}: {e}[/yellow]")


@app.command(name="goproj")
def go_project(project_name: Optional[str] = typer.Argument(None, help="The project name (with or without the leading +)")):
    """
    Open a project's tasks file in $EDITOR.
    If no project name is provided, lists active and inactive projects for selection.
    """
    # Load all projects from projects.md
    all_registry_projects = get_todos_from_file(PROJECTS_FILE, parsing.parse_projects_file, PROJECTS_FILE)
    
    # Also find major projects in projects/ directories
    projects_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.normpath(BASE_DIR)), "projects"))
    all_projects = []
    seen_paths = set()
    
    # Process registry projects first
    for p in all_registry_projects:
        slug = p.text.lstrip("+")
        ext_path = None
        if p.external_file:
            ext_path = os.path.normpath(os.path.join(BASE_DIR, p.external_file))
            seen_paths.add(ext_path)
            
        all_projects.append({
            "slug": slug,
            "path": ext_path or PROJECTS_FILE,
            "line": p.line_number
        })
        
    # Scan projects/ directories for any major projects not in the registry
    for domain in ["personal", "work"]:
        domain_dir = os.path.join(projects_dir, domain)
        if not os.path.isdir(domain_dir):
            continue
        for item in os.listdir(domain_dir):
            item_path = os.path.join(domain_dir, item)
            if not os.path.isdir(item_path) or item.startswith('.'):
                continue
            tasks_path = os.path.join(item_path, "tasks.md")
            norm_path = os.path.normpath(tasks_path)
            if norm_path not in seen_paths:
                seen_paths.add(norm_path)
                all_projects.append({
                    "slug": item,
                    "path": norm_path,
                    "line": 0
                })
                
    # If a project name was provided, find it
    if project_name:
        clean_name = project_name.lstrip("+").lower()
        target = None
        for p in all_projects:
            if p["slug"].lower() == clean_name:
                target = p
                break
        if not target:
            console.print(f"[red]Project not found: {project_name}[/red]")
            return
        
        # Open editor
        editor = os.environ.get('EDITOR', 'vi')
        try:
            line_arg = f"+{target['line'] + 1}" if target['line'] > 0 else "1"
            subprocess.run([editor, line_arg, target['path']])
            console.print(f"[green]✓ Opened project tasks file: {target['path']}[/green]")
        except Exception as e:
            console.print(f"[red]Error opening editor:[/red] {e}")
        return
        
    # Otherwise, display list for selection
    all_projects.sort(key=lambda x: x["slug"])
    
    console.print("\n[bold]Select a project to open:[/bold]\n")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", width=5)
    table.add_column("Project", style="bold yellow")
    table.add_column("Tasks File Path", style="white")
    
    workspace_root = os.path.abspath(os.path.join(BASE_DIR, '..'))
    for idx, p in enumerate(all_projects, 1):
        rel_path = os.path.relpath(p["path"], workspace_root)
        table.add_row(str(idx), f"+{p['slug']}", rel_path)
        
    console.print(table)
    
    editor = os.environ.get('EDITOR', 'vi')
    while True:
        try:
            index_str = typer.prompt(f"\nEnter project number to open (1-{len(all_projects)}), or 'q' to quit")
            if index_str.lower() == 'q':
                break
            try:
                p_num = int(index_str)
                if not (1 <= p_num <= len(all_projects)):
                    console.print(f"[yellow]Invalid number. Please enter 1-{len(all_projects)}[/yellow]")
                    continue
            except ValueError:
                console.print("[yellow]Please enter a valid number or 'q' to quit[/yellow]")
                continue
                
            target = all_projects[p_num - 1]
            line_arg = f"+{target['line'] + 1}" if target['line'] > 0 else "1"
            subprocess.run([editor, line_arg, target['path']])
            console.print(f"[green]✓ Opened project tasks file: {target['path']}[/green]")
            break
        except typer.Abort:
            break


if __name__ == "__main__":
    app()








