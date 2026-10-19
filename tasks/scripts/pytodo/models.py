from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Tag:
    """Represents a tag (e.g., #home, #work)."""
    name: str
    def __str__(self):
        return f"#{self.name}"

@dataclass
class Context:
    """Represents a context (e.g., @phone, @computer)."""
    name: str
    def __str__(self):
        return f"@{self.name}"

@dataclass
class Todo:
    """Represents a single todo item."""
    text: str
    priority: str = ""
    tags: List[Tag] = field(default_factory=list)
    contexts: List[Context] = field(default_factory=list)
    project: Optional['Project'] = None
    subtasks: List['Todo'] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    added_date: Optional[str] = None
    is_completed: bool = False
    is_cancelled: bool = False
    is_on_hold: bool = False
    raw_text: str = ""
    level: int = 0
    source_file: str = "" # The absolute path to the file this task came from
    line_number: int = 0 # The original line number in the source file

    @property
    def is_active(self) -> bool:
        """A task is active if it's not completed, cancelled, or on hold."""
        return not self.is_completed and not self.is_cancelled and not self.is_on_hold

    @property
    def is_active_for_list(self) -> bool:
        """A task is active for the new 'list' command if its priority is one of e, q, A-F, i, or ?."""
        active_priorities = {'e', 'q', 'A', 'B', 'C', 'D', 'E', 'F', 'i', '?'}
        return self.priority in active_priorities

    def __str__(self):
        return f"[{self.priority or ' '}] {self.text}"

@dataclass
class Project(Todo):
    """Represents a project, which is a special Todo with sub-tasks."""
    
    external_file: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        """A project is complete if all its subtasks are complete."""
        if self._is_explicitly_completed():
            return True
        if not self.subtasks:
            return False
        return all(not task.is_active for task in self.subtasks)

    @is_completed.setter
    def is_completed(self, value):
        pass

    def _is_explicitly_completed(self) -> bool:
        return self.raw_text.lstrip().startswith("- [x]") or \
               self.raw_text.lstrip().startswith("## [x]")

    @property
    def active_task_count(self) -> int:
        """Returns the number of active tasks in the project."""
        return len([task for task in self.subtasks if task.is_active])

    @property
    def completed_task_count(self) -> int:
        """Returns the number of completed tasks in the project."""
        return len([task for task in self.subtasks if not task.is_active])

    def get_all_tags(self) -> List[Tag]:
        """Returns the project's own tags plus tags from all its subtasks."""
        all_tags = set(self.tags)
        for task in self.subtasks:
            all_tags.update(task.tags)
        return sorted(list(all_tags), key=lambda t: t.name)

    def __str__(self):
        return f"Project: {self.text}"
