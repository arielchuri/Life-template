from typing import List, Dict, Union
import re
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.style import Style
from rich.padding import Padding
from rich.table import Table

from .models import Todo, Project
from .parsing import CONTEXT_REGEX, ADDED_DATE_REGEX, PROJECT_REGEX, TAG_REGEX, TASK_REGEX

# (All regexes and style functions remain the same)
MARKDOWN_LINK_REGEX = re.compile(r"[^\]]+\]\(([^)]+)\)")
def get_priority_content_style(priority: str) -> str:
    if priority == '!': return "bold white on red blink"  # Emergency
    if priority.upper() == 'A': return "bold magenta"
    if priority.upper() == 'B': return "bold red"
    if priority.upper() == 'C': return "bold yellow"
    if priority.upper() == 'D': return "bold green"
    if priority.upper() == 'E': return "bold cyan"
    if priority.upper() == 'F': return "bold white"
    if priority == 'i': return "cyan"
    if priority == 't': return "red"
    if priority == 's': return "dim"
    if priority == 'q': return "black on green"
    if priority == 'w': return "white"
    if priority in ['x', '-', 'h', 'p']: return "dim"
    return "white"

def format_line(item: Union[Todo, Project]) -> Text:
    if isinstance(item, Project):
        text = item.text
    else:
        match = TASK_REGEX.match(item.raw_text)
        if match:
            text = match.group(3)
        else:
            text = item.text

    if item.is_completed:
        priority_char = 'x'
    elif item.is_cancelled:
        priority_char = '-'
    elif getattr(item, 'is_on_hold', False):
        priority_char = item.priority or 'h'
    else:
        priority_char = item.priority or ' '
    
    content_style = get_priority_content_style(priority_char)

    display_char = priority_char
    # Handle special cases first
    if priority_char == '!':
        display_char = '!'  # Emergency: keep as !
    elif priority_char.upper() in 'ITSQW':
        display_char = priority_char.lower()
    elif priority_char.upper() in 'ABCDEF':
        display_char = priority_char.upper()

    if display_char == 's':
        checkbox = Text.assemble(
            Text("[", style="white"),
            Text(display_char, style=content_style),
            Text("]", style="white")
        )
    else:
        checkbox = Text(f"[{display_char}]", style=content_style)

    # Get the raw text of the line
    if isinstance(item, Project):
        raw_line_text = item.text
    else:
        match = TASK_REGEX.match(item.raw_text)
        if match:
            raw_line_text = match.group(3)
        else:
            raw_line_text = item.text

    # Define entity styles (using strings now)
    entity_style_strings = {
        PROJECT_REGEX: "dark_goldenrod",
        TAG_REGEX: "bright_blue",
        CONTEXT_REGEX: "dark_green",
        ADDED_DATE_REGEX: "dark_grey",
        MARKDOWN_LINK_REGEX: "blue underline",
    }

    # Find all matches and sort them by start position
    matches = []
    for regex, style_string in entity_style_strings.items():
        for match in regex.finditer(raw_line_text):
            matches.append((match.start(), match.end(), style_string, match.group(0)))
    matches.sort()

    # Determine text style based on priority
    # Grey out text for low-priority todos: no priority, E, F, ?, w, s
    plain_text_style = "dim" if priority_char in [' ', 'E', 'F', '?', 'w', 's'] else None

    # Build the list of Text objects
    text_segments = []
    current_pos = 0
    for start, end, style_string, matched_text in matches:
        # Add plain text before the match
        if start > current_pos:
            text_segments.append(Text(raw_line_text[current_pos:start], style=plain_text_style))
        # Add styled entity text
        text_segments.append(Text(matched_text, style=style_string))
        current_pos = end

    # Add any remaining plain text
    if current_pos < len(raw_line_text):
        text_segments.append(Text(raw_line_text[current_pos:], style=plain_text_style))

    final_line_text = Text.assemble(*text_segments)

    # Apply cancelled/completed styles
    if item.is_cancelled:
        final_line_text.stylize("strike dark_grey")
    elif item.is_completed:
        final_line_text.stylize("dark_grey")
    elif getattr(item, 'is_on_hold', False):
        final_line_text.stylize("dark_grey")

    # Append project or tag association at the end (if not already in the text)
    if item.project:
        project_name = item.project.text.strip().lstrip('+')
        project_tag = f"+{project_name}"
        # Only append if not already in the text
        if project_tag not in raw_line_text:
            final_line_text.append(Text(f" {project_tag}", style="dark_goldenrod"))
    elif item.tags:
        tag_name = item.tags[0].name
        tag_text = f"#{tag_name}"
        # Only append if not already in the text
        if tag_text not in raw_line_text:
            final_line_text.append(Text(f" {tag_text}", style="bright_blue"))

    return checkbox + Text(" ") + final_line_text


def format_note(note: str) -> Text:
    # Define entity styles (using strings now)
    entity_style_strings = {
        PROJECT_REGEX: "dark_goldenrod",
        TAG_REGEX: "bright_blue",
        CONTEXT_REGEX: "dark_green",
    }

    # Find all matches and sort them by start position
    matches = []
    for regex, style_string in entity_style_strings.items():
        for match in regex.finditer(note):
            matches.append((match.start(), match.end(), style_string, match.group(0)))
    matches.sort()

    # Build the list of Text objects
    text_segments = []
    current_pos = 0
    for start, end, style_string, matched_text in matches:
        # Add plain text before the match
        if start > current_pos:
            text_segments.append(Text(note[current_pos:start]))
        # Add styled entity text
        text_segments.append(Text(matched_text, style=style_string))
        current_pos = end
    
    # Add any remaining plain text
    if current_pos < len(note):
        text_segments.append(Text(note[current_pos:]))
            
    return Text.assemble(*text_segments)

def add_todo_to_tree(todo: Todo, tree: Tree, filter_subtasks: bool = False, filter_completed: bool = False):
    label = format_line(todo)

    if todo.notes:
        notes_label = Text("")
        for note in todo.notes:
            if note.strip():
                notes_label.append("\n  ")
                notes_label.append(format_note(note))
        notes_label.stylize("dim")
        label.append(notes_label)

    subtasks_to_show = todo.subtasks
    if filter_subtasks:
        subtasks_to_show = [subtask for subtask in todo.subtasks if subtask.is_active_for_list]
    elif filter_completed:
        subtasks_to_show = [subtask for subtask in todo.subtasks if subtask.is_active]

    # Special handling for priority 'i': don't print parent, but do print children
    if todo.priority == 'i' and subtasks_to_show:
        for subtask in subtasks_to_show:
            add_todo_to_tree(subtask, tree, filter_subtasks, filter_completed)
    elif subtasks_to_show:
        branch = tree.add(label)
        for subtask in subtasks_to_show:
            add_todo_to_tree(subtask, branch, filter_subtasks, filter_completed)
    else:
        tree.add(label)


def format_project_header(project: Project) -> Text:
    """Format a project header with bright yellow bold styling."""
    return Text(project.text, style="bold bright_yellow")

def add_project_to_tree(project: Project, tree: Tree, filter_completed: bool = False):
    label = format_project_header(project)
    branch = tree.add(label)

    # Filter subtasks if requested
    subtasks = project.subtasks
    if filter_completed:
        subtasks = [t for t in subtasks if t.is_active]

    for subtask in subtasks:
        if isinstance(subtask, Project):
            add_project_to_tree(subtask, branch, filter_completed)
        else:
            add_todo_to_tree(subtask, branch, filter_completed=filter_completed)


def render_todos(console: Console, todos: List[Todo], title: str = "Todos", filter_subtasks: bool = False):
    if not todos:
        console.print(f"No todos found in {title}.")
        return
    
    tree = Tree(f"[bold underline]{title}[/bold underline]", hide_root=True, guide_style="dim")
    for todo in todos:
        add_todo_to_tree(todo, tree, filter_subtasks)
    
    console.print(Padding(tree, 1))

def render_projects(console: Console, projects: List[Project]):
    if not projects:
        console.print("No projects found.")
        return

    for project in projects:
        tree = Tree("", hide_root=True, guide_style="dim")
        add_project_to_tree(project, tree, filter_completed=True)
        console.print(tree)

def render_tags(console: Console, tags: Dict[str, int]):
    if not tags:
        console.print("No tags found.")
        return
    table = Table(title="[bold]Tags Overview[/bold]")
    table.add_column("Tag Name", style="dim", no_wrap=True)
    table.add_column("Active Task Count", justify="right", style="yellow")
    for tag_name, count in sorted(tags.items()):
        table.add_row(f"#{tag_name}", str(count))
    console.print(table)

def render_todos_to_markdown(todos: List[Todo]) -> str:
    """Renders a list of todos to a plain markdown string."""
    lines = []
    
    def add_task_to_lines(task: Todo, indent_level: int = 0):
        # Use the raw_text to preserve the original line perfectly
        indent = "  " * indent_level
        lines.append(f"{indent}{task.raw_text.strip()}")
        for subtask in task.subtasks:
            add_task_to_lines(subtask, indent_level + 1)

    for todo in todos:
        add_task_to_lines(todo)
        
    return "\n".join(lines)
