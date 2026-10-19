import re
from typing import List, Tuple

from .models import Todo, Tag, Project, Context

# All regexes remain the same
TASK_REGEX = re.compile(r"^(\s*)- \[(.?)\] (.*)")
TAG_REGEX = re.compile(r"#(\w+)")
CONTEXT_REGEX = re.compile(r"@(\w+)")
PROJECT_REGEX = re.compile(r"\+([\w-]+)")
ADDED_DATE_REGEX = re.compile(r"\(added ([\d\-]+)\)")
PROJECT_HEADER_REGEX = re.compile(r"^\#\#\s*(?:\[([xX\-\shHpP])\])?\s*\+([\w-]+)")
TAG_HEADER_REGEX = re.compile(r"^\#\#\s+\#?(\w+)")
PROJECT_FILE_REGEX = re.compile(r"\[.*\]\(([^)]+)\)")


def parse_todos_from_lines(lines_with_numbers: List[Tuple[int, str]], source_file: str) -> List[Todo]:
    """
    Parses a list of (line_number, line_text) tuples into a list of Todo objects.
    """
    todos: List[Todo] = []
    parent_stack: List[Tuple[Todo, int]] = []

    for line_num, line in lines_with_numbers:
        match = TASK_REGEX.match(line)
        if not match:
            if parent_stack and line.strip():
                parent_stack[-1][0].notes.append(line.strip())
            continue

        indentation, priority, text = match.groups()
        indent_level = len(indentation)
        
        tags = [Tag(name=tag_name) for tag_name in TAG_REGEX.findall(text)]
        contexts = [Context(name=ctx_name) for ctx_name in CONTEXT_REGEX.findall(text)]
        project_match = PROJECT_REGEX.search(text)
        date_match = ADDED_DATE_REGEX.search(text)
        
        clean_text = TAG_REGEX.sub("", text).strip()
        clean_text = CONTEXT_REGEX.sub("", clean_text).strip()
        clean_text = PROJECT_REGEX.sub("", clean_text).strip()
        clean_text = ADDED_DATE_REGEX.sub("", clean_text).strip()

        todo = Todo(
            text=clean_text,
            priority=priority,
            tags=tags,
            contexts=contexts,
            added_date=date_match.group(1) if date_match else None,
            is_completed=(priority.lower() == 'x'),
            is_cancelled=(priority == '-'),
            is_on_hold=(priority.lower() in ['h', 'p']),
            raw_text=line,
            level=indent_level,
            source_file=source_file,
            line_number=line_num
        )

        if project_match:
            project_name = project_match.group(1)
            todo.project = Project(text=f"+{project_name}")

        while parent_stack and parent_stack[-1][1] >= indent_level:
            parent_stack.pop()

        if not parent_stack:
            todos.append(todo)
        else:
            parent_todo = parent_stack[-1][0]
            parent_todo.subtasks.append(todo)

        parent_stack.append((todo, indent_level))

    return todos


def parse_projects_file(content: str, source_file: str) -> List[Project]:
    """
    Parses a project file by splitting it into sections for each top-level project.
    """
    projects: List[Project] = []

    # Parse line by line to maintain accurate line numbers
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        header_match = PROJECT_HEADER_REGEX.match(line)

        if not header_match:
            i += 1
            continue

        status, slug = header_match.groups()
        project_start_line = i

        # Collect all lines until the next project header or end of file
        content_lines_with_nums = []
        i += 1
        while i < len(lines):
            if PROJECT_HEADER_REGEX.match(lines[i]):
                break
            content_lines_with_nums.append((i, lines[i]))
            i += 1

        # Parse tasks from the content lines
        tasks = parse_todos_from_lines(content_lines_with_nums, source_file)

        project = Project(text=f"+{slug}", subtasks=tasks, source_file=source_file, line_number=project_start_line, raw_text=line, is_cancelled=(status == '-'), is_on_hold=(status.lower() in ['h', 'p']) if status else False)

        # Check for external file reference on header line or content lines
        file_match = PROJECT_FILE_REGEX.search(line)
        if file_match:
            project.external_file = file_match.group(1)
        else:
            for line_num, line_text in content_lines_with_nums:
                file_match = PROJECT_FILE_REGEX.search(line_text)
                if file_match:
                    project.external_file = file_match.group(1)
                    break

        projects.append(project)

    return projects


def parse_tags_file(content: str, source_file: str) -> List[Todo]:
    """
    Parses a string containing a tags file into a list of Todo objects.
    """
    all_todos: List[Todo] = []
    lines = content.splitlines()
    
    current_tag_lines_with_nums: List[Tuple[int, str]] = []
    current_tag_name: str = ""

    def process_current_tag():
        nonlocal all_todos, current_tag_lines_with_nums, current_tag_name
        if current_tag_name:
            tag_todos = parse_todos_from_lines(current_tag_lines_with_nums, source_file)
            for todo in tag_todos:
                if not any(t.name == current_tag_name for t in todo.tags):
                    todo.tags.append(Tag(name=current_tag_name))
            all_todos.extend(tag_todos)

    for i, line in enumerate(lines):
        header_match = TAG_HEADER_REGEX.match(line)
        if header_match:
            process_current_tag()
            current_tag_name = header_match.group(1)
            current_tag_lines_with_nums = []
        elif current_tag_name:
            current_tag_lines_with_nums.append((i, line))

    process_current_tag()
        
    return all_todos